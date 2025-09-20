# app/services/agent/orchestrator_react.py (수정된 버전)

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
from app.services.agent.guidance_generator import make_guidance_generation_tool  # 새로 추가
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
        flags=re.I)
    return m.group(1) if m else ""


def _extract_phishing(agent_result: Any) -> bool:
    s = str(agent_result).lower()
    return '"phishing": true' in s or "phishing': true" in s or "phishing = true" in s


def _extract_reason(agent_result: Any) -> str:
    m = re.search(r"'reason':\s*'([^']*)'|\"reason\":\s*\"([^\"]*)\"",
                  str(agent_result))
    return (m.group(1) or m.group(2)) if m else ""


def _extract_guidance_text(agent_result: Any) -> str:
    try:
        s = str(agent_result)
        m = re.search(r"\{.*\"type\".*\"text\".*\}", s, re.S)
        if m:
            obj = json.loads(m.group(0))
            return obj.get("text", "").strip()
    except Exception:
        pass
    m2 = re.search(r"text['\"]\s*:\s*['\"]([^'\"]+)['\"]", str(agent_result))
    return m2.group(1).strip() if m2 else ""


def _extract_guidance_info(agent_result: Any) -> Dict[str, Any]:
    """동적 생성된 지침 정보를 추출합니다."""
    try:
        s = str(agent_result)
        # JSON 객체 찾기
        import re
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, s)

        for match in matches:
            try:
                data = json.loads(match)
                if 'text' in data and any(
                        key in data for key in
                    ['reasoning', 'categories', 'expected_effect']):
                    return {
                        "text":
                        data.get("text", ""),
                        "categories":
                        data.get("categories", []),
                        "reasoning":
                        data.get("reasoning", ""),
                        "expected_effect":
                        data.get("expected_effect", ""),
                        "generation_method":
                        data.get("generation_method", "dynamic_analysis")
                    }
            except json.JSONDecodeError:
                continue

        # 폴백: text 필드만 추출
        text_match = re.search(r'"text":\s*"([^"]*)"', s)
        return {
            "text": text_match.group(1) if text_match else "",
            "categories": [],
            "reasoning": "추출 실패",
            "expected_effect": "미확인",
            "generation_method": "fallback_extraction"
        }
    except Exception:
        return {
            "text": "",
            "categories": [],
            "reasoning": "파싱 오류",
            "expected_effect": "미확인",
            "generation_method": "error_fallback"
        }


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
    logger.info("[PromptSnapshot] %s",
                json.dumps(_truncate(snapshot), ensure_ascii=False))


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
        logger.info("[AgentThought] Tool=%s | Input=%s", rec["tool"],
                    _truncate(rec["tool_input"]))

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
    "    4) admin.judge 로 판정하고 phishing/이유를 기록한다.\n"
    "    5) admin.save_prevention 으로 라운드 요약과 권고 스텝을 저장한다.\n"
    "  [라운드2~N]\n"
    "    6) admin.generate_guidance 로 현재 상황을 분석하여 맞춤형 지침을 생성한다.\n"
    "       • 시나리오, 피해자 프로필, 이전 판정 결과, 대화 로그를 종합 분석\n"
    "       • 10가지 지침 카테고리 중에서 적절한 것들을 선택하여 구체적인 지침 생성\n"
    "       • 지침 선택 근거와 예상 효과도 함께 제공\n"
    "    7) mcp.simulator_run 을 다시 실행하되 아래 조건을 반드시 지킨다:\n"
    "       • case_id_override = (라운드1에서 획득한 case_id)\n"
    "       • round_no = 현재 라운드 번호 (정수)\n"
    "       • guidance = {{\"type\": \"A\", \"text\": \"생성된 지침 텍스트\"}} 만 포함\n"
    "    8) admin.judge → admin.save_prevention 순으로 반복한다.\n"
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
    "  • admin.generate_guidance 실패 시 기본 지침을 사용하되 로그에 실패 사유를 기록한다.\n"
    "\n"
    "▼ 출력 포맷(반드시 준수)\n"
    "  Thought: 현재 판단/계획(간결히)\n"
    "  Action: [사용할_도구_이름]\n"
    "  Action Input: 한 줄 JSON (예: {{\"data\": {{...}}}})\n"
    "  Observation: 도구 결과\n"
    "  ... 필요시 반복 ...\n"
    "  Final Answer: 최종 요약(최종 case_id, 총 라운드 수, 각 라운드 판정 요약 포함)\n")


def build_agent_and_tools(db: Session,
                          use_tavily: bool) -> Tuple[AgentExecutor, Any]:
    llm = agent_chat(temperature=0.2)

    tools: List = []

    # 각 도구를 안전하게 추가
    try:
        sim_tools = make_sim_tools(db)
        if sim_tools:
            tools.extend([t for t in sim_tools if t is not None])
            logger.info(
                f"[Agent] sim_tools 추가됨: {len([t for t in sim_tools if t is not None])}개"
            )
    except Exception as e:
        logger.error(f"[Agent] sim_tools 로딩 실패: {e}")

    try:
        mcp_tools, mcp_manager = make_mcp_tools()
        if mcp_tools:
            tools.extend([t for t in mcp_tools if t is not None])
            logger.info(
                f"[Agent] mcp_tools 추가됨: {len([t for t in mcp_tools if t is not None])}개"
            )
    except Exception as e:
        logger.error(f"[Agent] mcp_tools 로딩 실패: {e}")
        mcp_manager = None

    try:
        admin_tools = make_admin_tools(db, GuidelineRepoDB(db))
        if admin_tools:
            tools.extend([t for t in admin_tools if t is not None])
            logger.info(
                f"[Agent] admin_tools 추가됨: {len([t for t in admin_tools if t is not None])}개"
            )
    except Exception as e:
        logger.error(f"[Agent] admin_tools 로딩 실패: {e}")

    # guidance_tool은 이미 admin_tools에 포함되어 있으므로 별도 추가하지 않음
    # 다만 확인용 로그 추가
    logger.info(f"[Agent] 전체 도구 수: {len(tools)}개")

    if use_tavily:
        try:
            tavily_tools = make_tavily_tools()
            if tavily_tools:
                tools.extend([t for t in tavily_tools if t is not None])
                logger.info(
                    f"[Agent] tavily_tools 추가됨: {len([t for t in tavily_tools if t is not None])}개"
                )
        except Exception as e:
            logger.error(f"[Agent] tavily_tools 로딩 실패: {e}")

    # None 값 필터링 및 도구 이름 확인
    tools = [t for t in tools if t is not None and hasattr(t, 'name')]
    tool_names = [t.name for t in tools]

    logger.info("[Agent] TOOLS REGISTERED: %s", tool_names)

    # admin.generate_guidance가 등록되었는지 확인
    if 'admin.generate_guidance' not in tool_names:
        logger.error("[Agent] admin.generate_guidance 도구가 등록되지 않음!")
        logger.info("[Agent] 사용 가능한 admin 도구들: %s",
                    [name for name in tool_names if name.startswith('admin.')])

    prompt = ChatPromptTemplate.from_messages([
        ("system", REACT_SYS),
        ("human", "사용 가능한 도구들:\n{tools}\n\n"
         "도구 이름 목록: {tool_names}\n\n"
         "아래 포맷을 정확히 따르세요. 포맷 외 임의 텍스트/코드펜스/주석 금지.\n"
         "Thought: 한 줄\n"
         "Action: 도구이름  (예: mcp.simulator_run)\n"
         "Action Input: {{\"data\": {{...}}}}  # JSON 한 줄, 최상위 'data'\n"
         "Observation: (도구 출력)\n"
         "... 반복 ...\n"
         "Final Answer: 결론\n\n"
         "입력:\n{input}\n\n"
         "{agent_scratchpad}"),
    ])

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    ex = AgentExecutor(agent=agent,
                       tools=tools,
                       verbose=True,
                       handle_parsing_errors=True,
                       max_iterations=30)
    return ex, mcp_manager


# 메인 오케스트레이션 함수는 동일하므로 생략...
def run_orchestrated(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = SimulationStartRequest(**payload)
    ex, mcp_manager = build_agent_and_tools(db, use_tavily=req.use_tavily)

    cap = ThoughtCapture()
    used_tools: List[str] = []
    guidance_history: List[Dict[str, Any]] = []
    tavily_used = False
    rounds_done = 0
    case_id = ""

    try:
        # 1) 프롬프트 패키지 (DB 조립)
        pkg = build_prompt_package_from_payload(
            db,
            req,
            tavily_result=None,
            is_first_run=True,
            skip_catalog_write=True,
            enable_scenario_enhancement=True)

        scenario = pkg["scenario"]
        victim_profile = pkg["victim_profile"]
        templates = pkg["templates"]

        # 시나리오가 개선되었는지 로깅
        if "enhancement_info" in scenario:
            logger.info("[Enhanced] 개선된 시나리오 사용: %s",
                        scenario["enhancement_info"]["applied_guidance"][:100])
            guidance_history.append({
                "round": 0,  # 시나리오 빌드 단계
                "type": "scenario_enhancement",
                "guidance": scenario["enhancement_info"],
                "timestamp": datetime.now().isoformat()
            })

        logger.info("[InitialInput] %s",
                    json.dumps(_truncate(payload), ensure_ascii=False))
        logger.info("[ComposedPromptPackage] %s",
                    json.dumps(_truncate(pkg), ensure_ascii=False))

        offender_id = int(req.offender_id or 0)
        victim_id = int(req.victim_id or 0)
        max_rounds = max(2, min(req.round_limit or 3, 5))

        previous_judgments = []

        for round_no in range(1, max_rounds + 1):
            guidance_info = None

            # ── (A) 시뮬레이션 실행 ──────────────────────────────────────
            sim_payload: Dict[str, Any] = {
                "offender_id": offender_id,
                "victim_id": victim_id,
                "scenario": scenario,
                "victim_profile": victim_profile,
                "templates": templates,
                "max_turns": req.max_turns
            }

            if round_no >= 2:
                sim_payload["case_id_override"] = case_id
                sim_payload["round_no"] = round_no
                if guidance_info and guidance_info.get("text"):
                    sim_payload["guidance"] = {
                        "type": "A",
                        "text": guidance_info["text"]
                    }

            _log_prompt_snapshot(round_no, sim_payload)

            # LLM에게 "절대 수정하지 말고 그대로" 전달하도록 강하게 지시
            llm_call = {
                "input":
                ("다음 JSON 블록을 **수정하지 말고 그대로** mcp.simulator_run의 Action Input으로 사용하라.\n"
                 "DO NOT MODIFY. USE EXACTLY AS-IS.\n"
                 f"{json.dumps({'data': sim_payload}, ensure_ascii=False)}")
            }
            res_run = ex.invoke(llm_call, callbacks=[cap])
            used_tools.append("mcp.simulator_run")

            # 1라운드에서 case_id 추출
            if round_no == 1:
                case_id = _extract_case_id(res_run)
                if not case_id:
                    raise HTTPException(status_code=500,
                                        detail="case_id 추출 실패")

            rounds_done += 1

            # ── (B) 판정 ────────────────────────────────────────
            res_judge = ex.invoke(
                {
                    "input":
                    "admin.judge 호출.\n" + json.dumps(
                        {"data": {
                            "case_id": case_id,
                            "run_no": round_no
                        }},
                        ensure_ascii=False)
                },
                callbacks=[cap])
            used_tools.append("admin.judge")

            phishing = _extract_phishing(res_judge)
            reason = _extract_reason(res_judge)

            # 판정 결과 누적
            judgment_result = {
                "round":
                round_no,
                "phishing":
                phishing,
                "reason":
                reason,
                "guidance_used":
                guidance_info.get("text", "") if guidance_info else "",
                "guidance_categories":
                guidance_info.get("categories", []) if guidance_info else [],
                "timestamp":
                datetime.now().isoformat()
            }
            previous_judgments.append(judgment_result)

            # ── (C) 다음 라운드를 위한 지침 생성 ──
            if round_no < max_rounds:
                logger.info(
                    "[GuidanceGeneration] round=%s | case_id=%s | next_round=%s",
                    round_no, case_id, round_no + 1)

                guidance_input_text = f"""admin.generate_guidance를 다음 파라미터로 호출하세요:
                - case_id: {case_id}
                - round_no: {round_no + 1}
                - scenario: {json.dumps(scenario, ensure_ascii=False)}
                - victim_profile: {json.dumps(victim_profile, ensure_ascii=False)}
                - previous_judgments: {json.dumps(previous_judgments, ensure_ascii=False)}"""

                logger.info(
                    "[GuidanceGeneration] round=%s | case_id=%s | next_round=%s",
                    round_no, case_id, round_no + 1)

                res_guidance = ex.invoke({"input": guidance_input_text},
                                         callbacks=[cap])

                guidance_info = _extract_guidance_info(res_guidance)
                guidance_history.append({
                    "round": round_no + 1,
                    "guidance": guidance_info,
                    "timestamp": datetime.now().isoformat()
                })

            # ── (D) 라운드별 예방책 저장 ─────────────────────────
            save_payload = {
                "case_id": case_id,
                "offender_id": offender_id,
                "victim_id": victim_id,
                "run_no": round_no,
                "summary":
                f"Round {round_no} judgement: {'PHISHING' if phishing else 'NOT PHISHING'}. Reason: {reason}",
                "steps": {  # 리스트가 아닌 딕셔너리로 변경 (JSONB 필드에 맞춤)
                    "prevention_steps": [
                        "낯선 연락의 긴급 요구는 의심한다.", "공식 채널로 재확인한다(콜백/앱/웹).",
                        "개인·금융정보를 전화/메신저로 제공하지 않는다.",
                        "가족·지인 사칭 시 직접 연락으로 확인한다.",
                        "의심스러우면 즉시 경찰서나 금융감독원에 신고한다."
                    ],
                    "round_analysis": {
                        "success_indicators":
                        judgment_result.get("success_indicators_found", 0),
                        "failure_indicators":
                        judgment_result.get("failure_indicators_found", 0),
                        "confidence":
                        judgment_result.get("confidence", 0.0)
                    }
                }
            }

            # 🔥 시나리오 개선 정보와 런타임 지침 정보 모두 포함
            enhancement_info = scenario.get("enhancement_info")
            if enhancement_info:
                save_payload["steps"]["scenario_enhancement"] = {
                    "applied_guidance": enhancement_info["applied_guidance"],
                    "categories": enhancement_info["categories"]
                }

            # 지침 사용 정보도 추가
            if guidance_info:
                save_payload["steps"]["guidance_applied"] = {
                    "categories": guidance_info.get("categories", []),
                    "text": guidance_info.get("text", ""),
                    "reasoning": guidance_info.get("reasoning", ""),
                    "expected_effect":
                    guidance_info.get("expected_effect", "")
                }
            ex.invoke(
                {
                    "input":
                    "admin.save_prevention 호출.\n" +
                    json.dumps({"data": save_payload}, ensure_ascii=False)
                },
                callbacks=[cap])
            used_tools.append("admin.save_prevention")

            # ── (E) 종료 조건 ───────────────────────────────────
            if not should_continue_rounds({"phishing": phishing}, round_no):
                logger.info("[StopCondition] 종료 신호 수신 | round=%s", round_no)
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
            "guidance_generation": {
                "enabled":
                True,
                "scenario_enhanced":
                "enhancement_info" in scenario,
                "history":
                guidance_history,
                "total_generated":
                len([
                    h for h in guidance_history
                    if h["type"] == "runtime_guidance"
                ])
            }
        }
    finally:
        try:
            if getattr(mcp_manager, "is_running", False):
                mcp_manager.stop_mcp_server()
        except Exception:
            pass
