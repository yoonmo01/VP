# app/services/agent/orchestrator_react.py

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import json
import re
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks.base import BaseCallbackHandler

from app.services.llm_providers import agent_chat
from app.services.agent.tools_sim import make_sim_tools
from app.services.agent.tools_admin import make_admin_tools
from app.services.agent.tools_mcp import make_mcp_tools
from app.services.agent.tools_tavily import make_tavily_tools
from app.services.agent.graph import should_continue_rounds
from app.services.agent.guideline_repo_db import GuidelineRepoDB
from app.core.logging import get_logger

# 새 추가
from app.schemas.simulation_request import SimulationStartRequest
from app.services.prompt_integrator_db import build_prompt_package_from_payload

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────
# 헬퍼들
# ─────────────────────────────────────────────────────────
def _extract_case_id(from_obj: Any) -> str:
    s = str(from_obj)
    m = re.search(
        r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        s,
        flags=re.I,
    )
    return m.group(1) if m else ""


def _truncate(obj: Any, max_len: int = 800) -> Any:
    """긴 문자열을 로그용으로 안전하게 자르기"""
    try:
        if isinstance(obj, str):
            return (obj[:max_len] + "…") if len(obj) > max_len else obj
        if isinstance(obj, list):
            return [_truncate(x, max_len) for x in obj]
        if isinstance(obj, dict):
            return {k: _truncate(v, max_len) for k, v in obj.items()}
    except Exception:
        pass
    return obj


def _log_prompt_snapshot(round_no: int, sim_payload: Dict[str, Any]) -> None:
    """실제 시뮬레이터에 들어가는 입력 스냅샷을 로그로 남김"""
    snapshot = {
        "round_no": round_no,
        "offender_id": sim_payload.get("offender_id"),
        "victim_id": sim_payload.get("victim_id"),
        "case_id_override": sim_payload.get("case_id_override"),
        "round_no_field": sim_payload.get("round_no"),
        "guidance": sim_payload.get("guidance"),
        "scenario": sim_payload.get("scenario"),
        "victim_profile": sim_payload.get("victim_profile"),
        "templates": {
            "attacker": sim_payload.get("templates", {}).get("attacker", ""),
            "victim": sim_payload.get("templates", {}).get("victim", ""),
        },
        "max_turns": sim_payload.get("max_turns"),
    }
    logger.info(
        "[PromptSnapshot] %s", json.dumps(_truncate(snapshot), ensure_ascii=False)
    )


# ─────────────────────────────────────────────────────────
# 판정/지침 추출 유틸
# ─────────────────────────────────────────────────────────
def _extract_json_block(agent_result: Any) -> Dict[str, Any]:
    """툴 Observation에서 JSON 객체를 최대한 안전하게 추출."""
    try:
        if isinstance(agent_result, dict):
            # AgentExecutor가 {"output": "..."} 형태일 수 있음
            maybe = agent_result.get("output") if "output" in agent_result else agent_result
            if isinstance(maybe, str) and maybe.strip().startswith("{"):
                return json.loads(maybe)
            if isinstance(maybe, dict):
                return maybe
        s = str(agent_result)
        m = re.search(r"\{.*\"phishing\".*\}", s, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    return {}


def _extract_phishing_from_judgement(obj: Dict[str, Any]) -> bool:
    return bool(obj.get("phishing"))


def _extract_reason_from_judgement(obj: Dict[str, Any]) -> str:
    # reason 우선, 없으면 evidence 사용
    return (obj.get("reason") or obj.get("evidence") or "").strip()


def _extract_guidance_text(agent_result: Any) -> str:
    """pick_guidance Observation에서 text 회수"""
    try:
        obj = _extract_json_block(agent_result)
        if isinstance(obj, dict):
            txt = obj.get("text") or (obj.get("guidance") or {}).get("text")
            if isinstance(txt, str):
                return txt.strip()
    except Exception:
        pass
    # fallback: 정규식
    try:
        s = str(agent_result)
        m = re.search(r"\{.*\"type\".*\"text\".*\}", s, re.S)
        if m:
            o = json.loads(m.group(0))
            return (o.get("text") or "").strip()
    except Exception:
        pass
    m2 = re.search(r"text['\"]\s*:\s*['\"]([^'\"]+)['\"]", str(agent_result))
    return m2.group(1).strip() if m2 else ""


# ─────────────────────────────────────────────────────────
# LangChain 콜백: Thought/Action/Observation 캡처
# ─────────────────────────────────────────────────────────
@dataclass
class ThoughtCapture(BaseCallbackHandler):
    last_tool: Optional[str] = None
    last_tool_input: Optional[Any] = None
    events: list = field(default_factory=list)

    def on_agent_action(self, action, **kwargs):
        rec = {
            "type": "action",
            "tool": getattr(action, "tool", "?"),
            "tool_input": getattr(action, "tool_input", None),
        }
        self.last_tool = rec["tool"]
        self.last_tool_input = rec["tool_input"]
        self.events.append(rec)
        logger.info(
            "[AgentThought] Tool=%s | Input=%s",
            rec["tool"],
            _truncate(rec["tool_input"]),
        )

    def on_agent_finish(self, finish, **kwargs):
        self.events.append({"type": "finish", "log": finish.log})
        logger.info("[AgentFinish] %s", _truncate(finish.log, 1200))


# ─────────────────────────────────────────────────────────
# ReAct 시스템 프롬프트 (강한 레일가드 / JSON 예시 이스케이프)
# ─────────────────────────────────────────────────────────
REACT_SYS = (
    "당신은 보이스피싱 시뮬레이션 오케스트레이터입니다.\n"
    "오직 제공된 도구만 사용하여 작업하세요. (직접 결과를 쓰거나 요약으로 때우지 말 것)\n"
    "\n"
    "▼ 전체 사이클 규칙\n"
    "  [라운드1]\n"
    "    1) sim.fetch_entities 로 시나리오/피해자 정보를 확보한다.\n"
    "    2) sim.compose_prompts 를 호출한다. (★ guidance 금지)\n"
    "    3) mcp.simulator_run 을 실행한다. (★ guidance 금지)\n"
    "    4) admin.make_judgement 를 호출해 **판정/리스크/취약성/계속여부**를 생성·저장한다.\n"
    "    5) admin.judge 로 방금 저장된 판정을 조회한다.\n"
    "    6) admin.save_prevention 으로 라운드 요약과 권고 스텝을 저장한다.\n"
    "  [라운드2~N]\n"
    "    7) admin.pick_guidance 로 다음 라운드에 쓸 지침을 고른다. (type='P' 또는 'A')\n"
    "       └ 매핑 규칙: 직전 판정에서 phishing==true → 'P'(Protect), phishing==false → 'A'(Attack)\n"
    "    8) mcp.simulator_run 을 다시 실행하되 아래 조건을 반드시 지킨다:\n"
    "       • case_id_override = (라운드1에서 획득한 case_id)\n"
    "       • round_no = 현재 라운드 번호 (정수)\n"
    "       • guidance = {{\"type\": \"P\"|\"A\", \"text\": \"...\"}} 만 포함\n"
    "    9) admin.make_judgement → admin.judge → admin.save_prevention 순으로 반복한다.\n"
    "\n"
    "▼ 하드 제약 (어기면 안 됨)\n"
    "  • 1라운드에는 guidance를 어느 도구에도 넣지 않는다.\n"
    "  • 2라운드부터 guidance는 오직 mcp.simulator_run.arguments.guidance 로만 전달한다.\n"
    "  • offender_id / victim_id / scenario / victim_profile / templates 는 라운드 간 불변. (값 변경 금지)\n"
    "  • 동일 case_id 유지: 라운드1에서 받은 case_id 를 2라운드부터 case_id_override 로 반드시 넣는다.\n"
    "  • round_no 는 2부터 1씩 증가하는 정수로 설정한다.\n"
    "  • 도구 Action Input 은 한 줄 JSON 이고, 최상위 키는 반드시 \"data\" 여야 한다.\n"
    "  • mcp.simulator_run 의 허용 키는 다음만 가능하다:\n"
    "      offender_id, victim_id, scenario, victim_profile, templates, max_turns,\n"
    "      case_id_override, round_no, guidance(type/text)\n"
    "    (그 외 임의의 키 추가 금지)\n"
    "  • 도구 호출 전/후에 비JSON 텍스트, 코드펜스, 주석을 덧붙이지 말 것. (Action Input 에는 순수 JSON 한 줄만)\n"
    "  • 절대 도구를 호출하지 않고 결과를 직접 생성/요약하지 말 것.\n"
    "\n"
    "▼ 오류/예외 복구 규칙\n"
    "  • 라운드1에서 case_id 추출에 실패하면 mcp.latest_case(offender_id, victim_id) 를 호출해 최신 case_id 를 복구한다.\n"
    "  • 도구가 JSON 파싱 오류를 반환하면, 같은 JSON을 수정 없이 재시도하지 말고 스키마(최상위 'data', 허용 키)를 점검한 뒤 올바른 형식으로 재호출한다.\n"
    "  • 동일 (case_id, run, turn_index) 중복 오류가 발생하면 round_no 설정을 점검한다. (현재 라운드 번호를 정확히 넣을 것)\n"
    "\n"
    "▼ 출력 포맷(반드시 준수)\n"
    "  Thought: 현재 판단/계획(간결히)\n"
    "  Action: [사용할_도구_이름]\n"
    "  Action Input: {{\"data\": {{...}}}}  # JSON 한 줄, 최상위 'data'\n"
    "  Observation: 도구 결과\n"
    "  ... 필요시 반복 ...\n"
    "  Final Answer: 최종 요약(최종 case_id, 총 라운드 수, 각 라운드 판정 요약 포함)\n"
)


def build_agent_and_tools(db: Session, use_tavily: bool) -> Tuple[AgentExecutor, Any]:
    llm = agent_chat(temperature=0.2)

    tools: List = []
    tools += make_sim_tools(db)
    
    mcp_res = make_mcp_tools()
    if isinstance(mcp_res, tuple):
        mcp_tools, mcp_manager = mcp_res
    else:
        mcp_tools, mcp_manager = mcp_res, None
    tools += mcp_tools
    
    tools += make_admin_tools(db, GuidelineRepoDB(db))
    if use_tavily:
        tools += make_tavily_tools()

    logger.info("[Agent] TOOLS REGISTERED: %s", [t.name for t in tools])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", REACT_SYS),
            (
                "human",
                "사용 가능한 도구들:\n{tools}\n\n"
                "도구 이름 목록: {tool_names}\n\n"
                "아래 포맷을 정확히 따르세요. 포맷 외 임의 텍스트/코드펜스/주석 금지.\n"
                "Thought: 한 줄\n"
                "Action: 도구이름  (예: mcp.simulator_run)\n"
                "Action Input: {{\"data\": {{...}}}}  \n"
                "Observation: (도구 출력)\n"
                "... 반복 ...\n"
                "Final Answer: 결론\n\n"
                "입력:\n{input}\n\n"
                "{agent_scratchpad}",
            ),
        ]
    )

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    ex = AgentExecutor(
        agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=30
    )
    return ex, mcp_manager


# ─────────────────────────────────────────────────────────
# 메인 오케스트레이션
# ─────────────────────────────────────────────────────────
def run_orchestrated(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = SimulationStartRequest(**payload)
    ex, mcp_manager = build_agent_and_tools(db, use_tavily=req.use_tavily)

    cap = ThoughtCapture()
    used_tools: List[str] = []
    tavily_used = False
    rounds_done = 0
    case_id = ""

    try:
        # 1) 프롬프트 패키지 (DB 조립)
        pkg = build_prompt_package_from_payload(
            db, req, tavily_result=None, is_first_run=True, skip_catalog_write=True
        )
        scenario = pkg["scenario"]
        victim_profile = pkg["victim_profile"]
        templates = pkg["templates"]

        # 입력/패키지 스냅샷
        logger.info("[InitialInput] %s", json.dumps(_truncate(payload), ensure_ascii=False))
        logger.info(
            "[ComposedPromptPackage] %s", json.dumps(_truncate(pkg), ensure_ascii=False)
        )

        offender_id = int(req.offender_id or 0)
        victim_id = int(req.victim_id or 0)
        max_rounds = max(2, min(req.round_limit or 3, 5))  # 2~5

        guidance_kind: Optional[str] = None
        guidance_text: Optional[str] = None

        for round_no in range(1, max_rounds + 1):
            # ── (A) 시뮬레이션 실행 ────────────────────────────
            sim_payload: Dict[str, Any] = {
                "offender_id": offender_id,
                "victim_id": victim_id,
                "scenario": scenario,
                "victim_profile": victim_profile,
                "templates": templates,
                "max_turns": req.max_turns,
            }
            if round_no >= 2:
                sim_payload["case_id_override"] = case_id
                sim_payload["round_no"] = round_no
                if guidance_kind and guidance_text:
                    sim_payload["guidance"] = {"type": guidance_kind, "text": guidance_text}

            _log_prompt_snapshot(round_no, sim_payload)

            llm_call = {
                "input": (
                    "다음 JSON 블록을 **수정하지 말고 그대로** mcp.simulator_run의 Action Input으로 사용하라.\n"
                    "DO NOT MODIFY. USE EXACTLY AS-IS.\n"
                    f"{json.dumps({'data': sim_payload}, ensure_ascii=False)}"
                )
            }
            res_run = ex.invoke(llm_call, callbacks=[cap])
            used_tools.append("mcp.simulator_run")

            # 실제 에이전트가 넘긴 입력과 우리가 의도한 입력을 비교 (경고 로그)
            if cap.last_tool == "mcp.simulator_run":
                try:
                    agent_input = cap.last_tool_input
                    if isinstance(agent_input, str):
                        from json import JSONDecoder
                        agent_input = JSONDecoder().raw_decode(agent_input.strip())[0]
                    intended = {"data": sim_payload}
                    if agent_input != intended:
                        logger.warning(
                            "[ToolInputMismatch] intended!=actual | intended=%s | actual=%s",
                            json.dumps(_truncate(intended), ensure_ascii=False),
                            json.dumps(_truncate(agent_input), ensure_ascii=False),
                        )
                except Exception as e:
                    logger.warning("[ToolInputCheckError] %s", e)

            # 라운드1: case_id 확정
            if round_no == 1:
                case_id = _extract_case_id(res_run)
                if not case_id and isinstance(res_run, dict):
                    case_id = str(res_run.get("case_id") or "")
                if not case_id and cap.events:
                    case_id = _extract_case_id(cap.events)
                if not case_id:
                    logger.error(
                        "[CaseID] 라운드1 case_id 추출 실패 | res_run=%s",
                        _truncate(res_run),
                    )
                    raise HTTPException(status_code=500, detail="case_id 추출 실패(라운드1)")
            else:
                # 서버가 다른 case_id를 돌려주면 경고만
                got = _extract_case_id(res_run)
                if got and got != case_id:
                    logger.warning(
                        "[CaseID] 이어달리기 불일치 감지: expected=%s, got=%s", case_id, got
                    )

            rounds_done += 1

            # ── (B) 판정 생성 → 저장 → 조회 ────────────────────
            make_payload = {"data": {"case_id": case_id, "run_no": round_no}}
            res_make = ex.invoke(
                {
                    "input": "admin.make_judgement 호출.\n"
                    + json.dumps(make_payload, ensure_ascii=False)
                },
                callbacks=[cap],
            )
            used_tools.append("admin.make_judgement")

            res_judge = ex.invoke(
                {
                    "input": "admin.judge 호출.\n"
                    + json.dumps(
                        {"data": {"case_id": case_id, "run_no": round_no}},
                        ensure_ascii=False,
                    )
                },
                callbacks=[cap],
            )
            used_tools.append("admin.judge")

            judgement = _extract_json_block(res_judge)
            phishing = _extract_phishing_from_judgement(judgement)
            reason = _extract_reason_from_judgement(judgement)
            risk_obj = judgement.get("risk") or {}
            risk_lvl = (risk_obj.get("level") or "").lower()  # low|medium|high|critical
            risk_scr = int(risk_obj.get("score") or 0)
            cont_obj = judgement.get("continue") or {}
            cont_rec = (cont_obj.get("recommendation") or "").lower()  # continue|stop
            cont_msg = cont_obj.get("reason") or ""

            logger.info(
                "[Judgement] round=%s | phishing=%s | risk=%s(%s) | continue=%s (%s)",
                round_no,
                phishing,
                risk_lvl,
                risk_scr,
                cont_rec,
                _truncate(cont_msg, 200),
            )

            # ── (C) 라운드별 예방책 저장 ────────────────────────
            save_payload = {
                "case_id": case_id,
                "offender_id": offender_id,
                "victim_id": victim_id,
                "run_no": round_no,
                "summary": (
                    f"Round {round_no}: "
                    f"{'PHISHING' if phishing else 'NOT PHISHING'} / "
                    f"Risk={risk_lvl.upper() if risk_lvl else 'N/A'}({risk_scr}) / "
                    f"Reason: {reason or '(no evidence)'}"
                )[:980],
                "steps": [
                    "낯선 연락의 긴급 요구는 의심한다.",
                    "공식 채널로 재확인한다(콜백/앱/웹).",
                    "개인·금융정보를 전화/메신저로 제공하지 않는다.",
                ],
            }
            ex.invoke(
                {
                    "input": "admin.save_prevention 호출.\n"
                    + json.dumps({"data": save_payload}, ensure_ascii=False)
                },
                callbacks=[cap],
            )
            used_tools.append("admin.save_prevention")

            # ── (D) 다음 라운드를 위한 지침 선택 ────────────────
            if round_no < max_rounds:
                # 매핑 규칙: 피싱 성공(True)→ 'P'(Protect), 실패(False)→ 'A'(Attack)
                guidance_kind = "P" if phishing else "A"
                logger.info(
                    "[GuidanceKind] round=%s | phishing=%s → kind=%s",
                    round_no,
                    phishing,
                    guidance_kind,
                )

                pick_payload = {"data": {"kind": guidance_kind}}
                res_pick = ex.invoke(
                    {
                        "input": (
                            "아래 JSON을 **수정하지 말고 그대로** admin.pick_guidance의 Action Input으로 사용하라.\n"
                            "DO NOT MODIFY. USE EXACTLY AS-IS.\n"
                            + json.dumps(pick_payload, ensure_ascii=False)
                        )
                    },
                    callbacks=[cap],
                )
                used_tools.append("admin.pick_guidance")

                # 실제 Tool Input 검증(변형 시 경고)
                if cap.last_tool == "admin.pick_guidance":
                    try:
                        agent_input = cap.last_tool_input
                        if isinstance(agent_input, str):
                            from json import JSONDecoder
                            agent_input = JSONDecoder().raw_decode(agent_input.strip())[0]
                        if agent_input != pick_payload:
                            logger.warning(
                                "[ToolInputMismatch] admin.pick_guidance intended!=actual | intended=%s | actual=%s",
                                json.dumps(pick_payload, ensure_ascii=False),
                                json.dumps(_truncate(agent_input), ensure_ascii=False),
                            )
                    except Exception as e:
                        logger.warning("[ToolInputCheckError/pick_guidance] %s", e)

                guidance_text = _extract_guidance_text(res_pick) or "기본 예방 수칙을 따르세요."
                logger.info(
                    "[GuidancePicked] round=%s | kind=%s | text=%s",
                    round_no,
                    guidance_kind,
                    _truncate(guidance_text, 300),
                )

            # ── (E) 종료 조건 ───────────────────────────────────
            stop_from_model = cont_rec == "stop"
            if stop_from_model or (not should_continue_rounds({"phishing": phishing}, round_no)):
                logger.info(
                    "[StopCondition] 종료 | model_continue=%s | round=%s",
                    cont_rec or "n/a",
                    round_no,
                )
                break

        return {
            "status": "success",
            "case_id": case_id,
            "rounds": rounds_done,
            "turns_per_round": req.max_turns,
            "timestamp": datetime.now().isoformat(),
            "used_tools": used_tools,
            "mcp_used": True,
            "tavily_used": tavily_used,
        }
    finally:
        try:
            if mcp_manager and getattr(mcp_manager, "is_running", False):
                mcp_manager.stop_mcp_server()
        except Exception:
            pass
