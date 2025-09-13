# app/services/agent/orchestrator_react.py

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Any
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

REACT_SYS = (
    "당신은 보이스피싱 시뮬레이션 오케스트레이터입니다. "
    "피해자/시나리오를 바탕으로 ➊시뮬 실행(MCP), ➋판정/지침, ➌예방책을 사이클로 수행합니다. "
    "한 사이클은 최대 15턴(공+피=1)이며, 최소 2회~최대 5회 반복합니다. "
    "각 단계는 반드시 제공된 툴들만 사용해 진행하세요."
)

def _esc(s: str) -> str:
    # ChatPromptTemplate가 { } 를 변수로 해석하지 않도록 이스케이프
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

    # 예시 JSON은 반드시 이스케이프해서 넣는다
    ex1 = _esc('{"data": {"offender_id": 1, "victim_id": 1, "scenario": {"type": "generic_test"}}}')
    ex2 = _esc('{"data": {"case_id": "UUID", "run_no": 1}}')
    ex3 = _esc('{"data": {"kind": "A"}}')
    ex4 = _esc('{"data": {"case_id": "UUID", "offender_id": 1, "victim_id": 1, "run_no": 1, "summary": "…", "steps": ["…"]}}')

    prompt = ChatPromptTemplate.from_messages([
        ("system", REACT_SYS),
        ("human",
         "사용 가능한 도구들:\n{tools}\n\n"
         "도구 이름 목록: {tool_names}\n\n"
         "아래 형식을 엄수:\n"
         "Thought: 문제에 대한 당신의 생각\n"
         "Action: [{tool_names} 중 하나의 정확한 이름]\n"
         "Action Input: JSON 한 줄 (줄바꿈 없이), 반드시 'data' 키를 최상위로 둔 객체\n"
         f"예시1: {ex1}\n"
         f"예시2: {ex2}\n"
         f"예시3: {ex3}\n"
         f"예시4: {ex4}\n"
         "Observation: 도구 실행 결과\n"
         "... 필요하면 반복 ...\n"
         "Final Answer: 최종 요약/권고\n\n"
         "규칙:\n"
         "- Action Input은 순수 JSON 객체 한 줄이며, 문자열(JSON 텍스트)로 이중 포장하지 말 것.\n"
         "- guidance.kind 값은 'P' 또는 'A' 스칼라(문자 한 글자)로 전달.\n\n"
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
    ex, mcp_manager = build_agent_and_tools(db, use_tavily=bool(payload.get("use_tavily")))
    try:
        # ---- 입력 정규화/검증 ----
        try:
            offender_id = int(payload["offender_id"])
            victim_id   = int(payload["victim_id"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=422, detail="offender_id, victim_id는 필수 정수입니다.")

        scenario_obj = payload.get("scenario") or {}
        if not isinstance(scenario_obj, dict):
            raise HTTPException(status_code=422, detail="scenario는 객체(JSON)여야 합니다.")

        def _one_line(obj: Any) -> str:
            return json.dumps(obj, ensure_ascii=False)

        # 1) 엔터티 로드 & 프롬프트 합성
        ex.invoke({
            "input": (
                "sim.fetch_entities 를 호출한 뒤 sim.compose_prompts 로 프롬프트를 구성하라.\n"
                + _one_line({"data": {
                    "offender_id": offender_id,
                    "victim_id": victim_id,
                    "scenario": scenario_obj
                }})
            )
        })

        # 2) 1라운드 실행 (MCP)
        res_run1 = ex.invoke({
            "input": (
                "mcp.simulator_run 을 호출해 시뮬레이션을 실행하고, 반환된 case_id를 기록하라.\n"
                + _one_line({"data": {
                    "offender_id": offender_id,
                    "victim_id": victim_id,
                    "scenario": scenario_obj,
                    "max_turns": 15
                }})
            )
        })
        case_id = _extract_case_id(res_run1)
        if not case_id:
            raise HTTPException(status_code=500, detail="case_id 추출 실패")

        round_idx = 0
        last_judgement = {}
        while True:
            # 3) 판정
            res_judge = ex.invoke({
                "input": (
                    "admin.judge 를 호출하여 판정(case_id, run_no=현재 라운드)을 수행하라.\n"
                    + _one_line({"data": {
                        "case_id": case_id,
                        "run_no": round_idx + 1
                    }})
                )
            })
            last_judgement = {"phishing": _extract_phishing(res_judge)}

            # 3-1) 지침 선택
            kind = "P" if last_judgement.get("phishing") else "A"
            ex.invoke({
                "input": (
                    "admin.pick_guidance 를 호출하여 지침을 선택하라.\n"
                    + _one_line({"data": {"kind": kind}})
                )
            })

            # 3-2) 예방책 저장
            ex.invoke({
                "input": (
                    "admin.save_prevention 을 호출하여 요약/steps를 저장하라. "
                    "지금까지의 Observation을 바탕으로 summary(문단 1-2개)와 steps(3-6개)를 생성해 넣어라.\n"
                    + _one_line({"data": {
                        "case_id": case_id,
                        "offender_id": offender_id,
                        "victim_id": victim_id,
                        "run_no": round_idx + 1,
                        "summary": "판정/대화 로그 기반 요약을 여기에 작성",
                        "steps": ["핵심 예방 단계 1", "핵심 예방 단계 2"]
                    }})
                )
            })

            # 4) 반복 여부
            if not should_continue_rounds(last_judgement, round_idx):
                break
            round_idx += 1
            if round_idx >= 5:
                break

            # 5) 다음 라운드
            gtype = "P" if last_judgement.get("phishing") else "A"
            ex.invoke({
                "input": (
                    "직전 단계에서 선택된 지침(type, text)을 scenario.guideline에 주입하고 "
                    "mcp.simulator_run 을 다시 호출하여 다음 라운드를 수행하라. "
                    "case_id는 유지하고 max_turns=15로 고정한다. "
                    "필요 시 sim.fetch_entities/compose_prompts 를 재활용하라.\n"
                    + _one_line({"data": {
                        "case_id": case_id,
                        "offender_id": offender_id,
                        "victim_id": victim_id,
                        "scenario": scenario_obj,
                        "gtype": gtype,
                        "max_turns": 15
                    }})
                )
            })

        return {
            "status": "success",
            "case_id": case_id,
            "rounds": round_idx + 1,
            "timestamp": datetime.now().isoformat(),
        }
    finally:
        try:
            if getattr(mcp_manager, "is_running", False):
                mcp_manager.stop_mcp_server()
        except Exception:
            pass

def _extract_case_id(agent_result: Dict[str, Any]) -> str:
    import re
    if isinstance(agent_result, dict) and "output" in agent_result:
        text = str(agent_result["output"])
        m = re.search(r'"case_id"\s*:\s*"([0-9a-f\-]{36})"', text, flags=re.I)
        if m:
            return m.group(1)
    out = str(agent_result)
    m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', out, flags=re.I)
    return m.group(1) if m else ""

def _extract_phishing(agent_result: Dict[str, Any]) -> bool:
    s = str(agent_result).lower()
    return '"phishing": true' in s or "phishing': true" in s or "phishing = true" in s
