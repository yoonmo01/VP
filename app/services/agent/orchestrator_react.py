from __future__ import annotations
from typing import Dict, Any, List, Tuple
import json
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_providers import agent_chat
from app.services.agent.tools_sim import make_sim_tools
from app.services.agent.tools_admin import make_admin_tools
from app.services.agent.tools_mcp import make_mcp_tools
from app.services.agent.tools_tavily import make_tavily_tools
from app.services.agent.graph import should_continue_rounds
from app.services.agent.guideline_repo_db import GuidelineRepoDB

# 새 추가
from app.schemas.simulation_request import SimulationStartRequest
from app.services.prompt_integrator_db import build_prompt_package_from_payload

REACT_SYS = (
    "당신은 보이스피싱 시뮬레이션 오케스트레이터입니다. "
    "피해자/시나리오를 바탕으로 ➊시뮬 실행(MCP), ➋판정/지침, ➌예방책을 사이클로 수행합니다. "
    "한 사이클은 최대 15턴(공+피=1)이며, 최소 2회~최대 5회 반복합니다. "
    "각 단계는 반드시 제공된 툴들만 사용해 진행하세요."
)


def _esc(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")


def build_agent_and_tools(db: Session, use_tavily: bool) -> Tuple[AgentExecutor, Any]:
    llm = agent_chat(temperature=0.2)

    tools: List = []
    tools += make_sim_tools(db)
    mcp_tools, mcp_manager = make_mcp_tools()
    tools += mcp_tools
    tools += make_admin_tools(db, GuidelineRepoDB(db))
    if use_tavily:
        tools += make_tavily_tools()

    from app.core.logging import get_logger
    get_logger(__name__).info(f"[Agent] TOOLS REGISTERED: {[t.name for t in tools]}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", REACT_SYS),
        ("human",
         "사용 가능한 도구들:\n{tools}\n\n"
         "도구 이름 목록: {tool_names}\n\n"
         "Thought: 문제에 대한 당신의 생각\n"
         "Action: [{tool_names} 중 하나]\n"
         "Action Input: 반드시 JSON 한 줄, 최상위에 'data'\n"
         "Observation: 도구 실행 결과\n"
         "... 반복 ...\n"
         "Final Answer: 최종 요약\n\n"
         "규칙:\n"
         "- Action Input은 JSON 객체 한 줄.\n"
         "- guidance.kind 값은 'P' 또는 'A'.\n\n"
         "입력:\n{input}\n\n"
         "{agent_scratchpad}"
        ),
    ])

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    ex = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=20,
    )
    return ex, mcp_manager


def run_orchestrated(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = SimulationStartRequest(**payload)
    ex, mcp_manager = build_agent_and_tools(db, use_tavily=req.use_tavily)

    used_tools: List[str] = []
    tavily_used = False

    try:
        # 1) 커스텀 시나리오면 Tavily 검색
        tavily_result = None
        if req.custom_scenario and req.use_tavily:
            tavily_used = True
            q = " ".join(filter(None, [
                req.custom_scenario.type,
                req.custom_scenario.purpose,
                req.custom_scenario.text,
            ]))
            res_tav = ex.invoke({
                "input": "tavily.search 를 호출.\n" +
                         json.dumps({"data": {"query": q, "objectives": req.objectives}}, ensure_ascii=False)
            })
            used_tools.append("tavily.search")
            tavily_result = {
                "description": "...",  # TODO: res_tav에서 추출
                "purpose": req.custom_scenario.purpose,
                "steps": req.objectives,
            }

        # 2) DB 기반 패키지 빌드
        pkg = build_prompt_package_from_payload(db, req, tavily_result = None, is_first_run=False,skip_catalog_write = True)
        scenario = pkg["scenario"]
        victim_profile = pkg["victim_profile"]
        templates = pkg["templates"]

        offender_id = int(req.offender_id or 0)
        victim_id = int(req.victim_id or 0)

        # 3) 1라운드 (guidance 없음)
        res_run1 = ex.invoke({
            "input": "mcp.simulator_run 실행.\n" + json.dumps({"data": {
                "offender_id": offender_id,
                "victim_id": victim_id,
                "scenario": scenario,
                "victim_profile": victim_profile,
                "templates": templates,
                "max_turns": req.max_turns
            }}, ensure_ascii=False)
        })
        used_tools.append("mcp.simulator_run")
        case_id = _extract_case_id(res_run1)
        if not case_id:
            raise HTTPException(status_code=500, detail="case_id 추출 실패")

        # 4) 판정 → 지침
        res_judge = ex.invoke({
            "input": "admin.judge 호출.\n" + json.dumps({"data": {"case_id": case_id, "run_no": 1}}, ensure_ascii=False)
        })
        used_tools.append("admin.judge")
        phishing = _extract_phishing(res_judge)
        kind = "P" if phishing else "A"

        res_pick = ex.invoke({
            "input": "admin.pick_guidance 호출.\n" + json.dumps({"data": {"kind": kind}}, ensure_ascii=False)
        })
        used_tools.append("admin.pick_guidance")
        guidance_text = "..."  # TODO: res_pick에서 추출

        # 5) 이후 라운드 (guidance 주입)
        rounds = 1
        while should_continue_rounds({"phishing": phishing}, rounds - 1) and rounds < 5:
            rounds += 1
            ex.invoke({
                "input": "mcp.simulator_run 재실행.\n" + json.dumps({"data": {
                    "offender_id": offender_id,
                    "victim_id": victim_id,
                    "scenario": scenario,
                    "victim_profile": victim_profile,
                    "templates": templates,
                    "guidance": {"type": kind, "text": guidance_text},
                    "max_turns": req.max_turns
                }}, ensure_ascii=False)
            })
            used_tools.append("mcp.simulator_run")

        return {
            "status": "success",
            "case_id": case_id,
            "rounds": rounds,
            "turns_per_round": req.max_turns,
            "timestamp": datetime.now().isoformat(),
            "used_tools": used_tools,
            "mcp_used": True,
            "tavily_used": tavily_used,
        }
    finally:
        try:
            if getattr(mcp_manager, "is_running", False):
                mcp_manager.stop_mcp_server()
        except Exception:
            pass


def _extract_case_id(agent_result: Dict[str, Any]) -> str:
    import re
    text = str(agent_result)
    m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', text, flags=re.I)
    return m.group(1) if m else ""


def _extract_phishing(agent_result: Dict[str, Any]) -> bool:
    s = str(agent_result).lower()
    return '"phishing": true' in s or "phishing': true" in s or "phishing = true" in s



# # orchestrator_react.py

# from __future__ import annotations
# from typing import Dict, Any, List, Tuple
# import json
# from datetime import datetime
# from sqlalchemy.orm import Session

# from fastapi import HTTPException
# from langchain.agents import create_react_agent, AgentExecutor
# from langchain_core.prompts import ChatPromptTemplate

# from app.services.llm_providers import agent_chat
# from app.services.agent.tools_sim import make_sim_tools
# from app.services.agent.tools_admin import make_admin_tools
# from app.services.agent.tools_mcp import make_mcp_tools
# from app.services.agent.tools_tavily import make_tavily_tools
# from app.services.agent.guideline_repo_db import GuidelineRepoDB

# from app.schemas.simulation_request import SimulationStartRequest
# from app.services.prompt_integrator_db import build_prompt_package_from_payload


# # ─────────────────────────────────────────────────────────
# # ReAct 시스템 프롬프트: 자율성 유지 + 강한 레일가드
# # ─────────────────────────────────────────────────────────
# REACT_SYS = (
#     "당신은 보이스피싱 시뮬레이션 오케스트레이터입니다.\n"
#     "도구들만 사용하여 다음 사이클을 수행하세요:\n"
#     "  1) (필요시) 시나리오/피해자 정보를 확보: sim.fetch_entities → sim.compose_prompts\n"
#     "  2) 1라운드 실행: mcp.simulator_run (절대 guidance 넣지 말 것)\n"
#     "  3) 판정: admin.judge (phishing=True/False, reason 활용)\n"
#     "  4) 2라운드부터 guidance 생성/주입: admin.pick_guidance\n"
#     "     - phishing=True → 피해자(P)에게 도움 (type='P')\n"
#     "     - phishing=False → 공격자(A)에게 도움 (type='A')\n"
#     "  5) case_id 유실 시 mcp.latest_case 로 복구\n"
#     "\n"
#     "라운드 운영 규칙:\n"
#     "- guidance는 **1라운드에 금지**, **2라운드부터** 주입.\n"
#     "- guidance.type 은 'P' 또는 'A'만 허용.\n"
#     "- 최대 5라운드까지 수행. 동일/반복적 결과가 지속되거나 판정 확신이 높으면 조기 종료.\n"
#     "- 동일 offender_id/victim_id 로 라운드 누적. case_id는 첫 실행 결과를 재사용.\n"
#     "- 커스텀 시나리오가 아니면 Tavily/신규 Attack 저장 금지.\n"
#     "\n"
#     "출력 포맷(반드시 준수):\n"
#     "Thought: 현재 판단/계획\n"
#     "Action: [사용할_툴_이름]\n"
#     "Action Input: 한 줄 JSON (최상위에 'data' 키 포함)\n"
#     "Observation: 툴 결과\n"
#     "... 필요시 반복 ...\n"
#     "Final Answer: 최종 요약(최종 case_id, 총 라운드 수, 주요 판단/사유 포함)\n"
# )


# def _esc(s: str) -> str:
#     return s.replace("{", "{{").replace("}", "}}")


# def build_agent_and_tools(db: Session, use_tavily: bool) -> Tuple[AgentExecutor, Any]:
#     llm = agent_chat(temperature=0.2)

#     tools: List = []
#     tools += make_sim_tools(db)
#     mcp_tools, mcp_manager = make_mcp_tools()
#     tools += mcp_tools
#     tools += make_admin_tools(db, GuidelineRepoDB(db))
#     # 커스텀 시나리오일 때만 tavily 추가(여기선 기본 끔)
#     if use_tavily:
#         tools += make_tavily_tools()

#     from app.core.logging import get_logger
#     get_logger(__name__).info(f"[Agent] TOOLS REGISTERED: {[t.name for t in tools]}")

#     prompt = ChatPromptTemplate.from_messages([
#         ("system", REACT_SYS),
#         ("human",
#         "사용 가능한 도구들:\n{tools}\n\n"
#         "도구 이름 목록: {tool_names}\n\n"
#         "출력 포맷(정확히 준수):\n"
#         "Thought: 현재 판단/계획\n"
#         "Action: 도구이름 (괄호/대괄호/인용부호 없이 정확히)  예) Action: mcp.simulator_run\n"
#         "Action Input: 반드시 JSON 한 줄, 최상위에 'data' 키 포함\n"
#         "Observation: 도구 실행 결과\n"
#         "... 필요시 반복 ...\n"
#         "Final Answer: 최종 요약(케이스 id, 라운드 수, 주요 판단 포함)\n\n"
#         "입력 규칙(엄수):\n"
#         "- mcp.simulator_run 의 Action Input에는 오직 다음 키만 포함: "
#         "offender_id, victim_id, scenario, victim_profile, templates, max_turns\n"
#         "- 1라운드 mcp.simulator_run 에 guidance 절대 금지.\n"
#         "- 2라운드부터 guidance를 넣을 때는 guidance: {\"type\": \"P\"|\"A\", \"text\": \"...\"} 만 추가.\n"
#         "- 허용되지 않은 임의 필드(custom_mode, round_limit 등) 절대 넣지 말 것.\n\n"
#         "입력:\n{input}\n\n"
#         "{agent_scratchpad}"
#         ),
#     ])

#     agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
#     ex = AgentExecutor(
#         agent=agent,
#         tools=tools,
#         verbose=True,
#         handle_parsing_errors=True,
#         max_iterations=40,   # 충분 여유
#     )
#     return ex, mcp_manager


# def run_orchestrated(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     에이전트가 자율적으로 라운드 수/지침 대상/종료 시점을 결정한다.
#     우리는 초기 데이터만 제공하고 한 번의 invoke로 끝낸다.
#     """
#     req = SimulationStartRequest(**payload)

#     # 커스텀 시나리오가 아니라면: Tavily 끄고, 신규 Attack 저장 금지
#     pkg = build_prompt_package_from_payload(
#         db, req,
#         tavily_result=None,        # Tavily 기본 끔
#         is_first_run=True,         # 첫 라운드 시작
#         skip_catalog_write=True    # 신규 수법 저장 금지(커스텀 아닐 때)
#     )

#     ex, mcp_manager = build_agent_and_tools(
#         db,
#         use_tavily=bool(req.custom_scenario and req.use_tavily)
#     )

#     initial = {
#         "offender_id": req.offender_id,
#         "victim_id": req.victim_id,
#         "max_turns": req.max_turns,
#         "scenario": pkg["scenario"],
#         "victim_profile": pkg["victim_profile"],
#         "templates": pkg["templates"],
#         "custom_mode": bool(req.custom_scenario),
#         "round_limit": 5
#     }

#     try:
#         # 에이전트가 스스로 1라운드→판정→지침→추가 라운드→종료까지 수행
#         result = ex.invoke({
#             "input": (
#                 "아래 입력으로 시뮬레이션을 시작하세요.\n"
#                 "- 1라운드 mcp.simulator_run에는 guidance를 넣지 마세요.\n"
#                 "- admin.judge 결과에 따라 2라운드부터 guidance 수혜자(P/A)를 선택하세요.\n"
#                 "- 최대 5라운드, 필요 시 조기 종료.\n"
#                 "- case_id는 첫 mcp 결과에서 추출해 재사용. 유실 시 mcp.latest_case로 복구.\n"
#                 f"{json.dumps({'data': initial}, ensure_ascii=False)}"
#             )
#         })

#         # Final Answer만 신뢰해 래핑 반환 (원하면 여기서 case_id/라운드 추출 로직 보강 가능)
#         return {
#             "status": "success",
#             "orchestrated_by": "react_agent",
#             "timestamp": datetime.now().isoformat(),
#             "raw": result,
#         }
#     finally:
#         try:
#             if getattr(mcp_manager, "is_running", False):
#                 mcp_manager.stop_mcp_server()
#         except Exception:
#             pass
