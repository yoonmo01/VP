# app/services/agent/orchestrator_react.py

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import json
import re
import ast
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


def _extract_json_block(agent_result: Any) -> Dict[str, Any]:
    """툴 Observation에서 JSON 객체를 최대한 안전하게 추출."""
    try:
        if isinstance(agent_result, dict):
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


def _safe_json(obj: Any) -> Dict[str, Any]:
    """dict면 그대로, 정확한 JSON 문자열이면 json.loads, 아니면 빈 dict."""
    if isinstance(obj, dict):
        return obj
    s = str(obj).strip()
    try:
        if s.startswith("{") and s.endswith("}"):
            return json.loads(s)
    except Exception:
        pass
    return {}


def _loose_parse_json(obj: Any) -> Dict[str, Any]:
    """JSON이 아니어도, python dict literal 문자열(작은따옴표) 등 느슨하게 파싱."""
    if isinstance(obj, dict):
        return obj
    s = str(obj).strip()
    # 1) 정확 JSON 시도
    j = _safe_json(s)
    if j:
        return j
    # 2) python literal 시도: {'ok': True, ...}
    try:
        if s.startswith("{") and s.endswith("}"):
            pyobj = ast.literal_eval(s)
            if isinstance(pyobj, dict):
                return pyobj
    except Exception:
        pass
    # 3) 본문 속에 dict가 섞여 있으면 가장 바깥 {} 뽑기
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        sub = m.group(0)
        j = _safe_json(sub)
        if j:
            return j
        try:
            pyobj = ast.literal_eval(sub)
            if isinstance(pyobj, dict):
                return pyobj
        except Exception:
            pass
    return {}


def _last_observation(cap: "ThoughtCapture", tool_name: str) -> Any:
    for ev in reversed(cap.events):
        if ev.get("type") == "observation" and ev.get("tool") == tool_name:
            return ev.get("output")
    return None


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

    def on_tool_end(self, output: Any, **kwargs):
        self.events.append({
            "type": "observation",
            "tool": self.last_tool,
            "output": output,
        })
        logger.info("[ToolObservation] Tool=%s | Output=%s", self.last_tool, _truncate(output, 1200))

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
    "    4) admin.make_judgement 를 호출해 **판정/리스크/취약성/계속여부**를 생성한다.\n"
    "       └ 이때 (case_id, run_no)만 보내지 말고, 반드시 방금 mcp.simulator_run Observation에서 받은\n"
    "          {{\"turns\": [...}}] 또는 {{\"log\": {{...}}}} 를 함께 전달한다.\n"
    "    5) 필요 시 admin.pick_guidance 로 다음 라운드 지침을 고른다.\n"
    "  [라운드2~N]\n"
    "    6) admin.pick_guidance 로 다음 라운드에 쓸 지침을 고른다. (type='P' 또는 'A')\n"
    "       └ 매핑 규칙: 직전 판정에서 phishing==true → 'P'(Protect), phishing==false → 'A'(Attack)\n"
    "    7) mcp.simulator_run 을 다시 실행하되 아래 조건을 반드시 지킨다:\n"
    "       • case_id_override = (라운드1에서 획득한 case_id)\n"
    "       • round_no = 현재 라운드 번호 (정수)\n"
    "       • guidance = {{\"type\": \"P\"|\"A\", \"text\": \"...\"}} 만 포함\n"
    "\n"
    "▼ 하드 제약 (어기면 안 됨)\n"
    "  • 1라운드에는 guidance를 어느 도구에도 넣지 않는다.\n"
    "  • 2라운드부터 guidance는 오직 mcp.simulator_run.arguments.guidance 로만 전달한다.\n"
    "  • offender_id / victim_id / scenario / victim_profile / templates 는 라운드 간 불변. (값 변경 금지)\n"
    "  • 동일 case_id 유지: 라운드1에서 받은 case_id 를 2라운드부터 case_id_override 로 반드시 넣는다.\n"
    "  • round_no 는 2부터 1씩 증가하는 정수로 설정한다.\n"
    "  • 도구 Action Input 은 한 줄 JSON 이고, **최상위 키는 반드시 \"data\" 단 하나만** 존재해야 한다.\n"
    "    **'data' 바깥에 어떤 키도 추가하지 말 것.** (mcp.simulator_run 2라운드부터 case_id_override/round_no/guidance도\n"
    "    반드시 data 내부에 둘 것)\n"
    "  • 절대 도구를 호출하지 않고 결과를 직접 생성/요약하지 말 것.\n"
    "  • 최소 2라운드는 반드시 수행한다.\n"
    "  • 조기 종료는 위험도(level)가 'critical'일 때만 가능하며, 이 경우에도 2라운드 이상 수행한 뒤 종료한다.\n"

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
        logger.info("[ComposedPromptPackage] %s", json.dumps(_truncate(pkg), ensure_ascii=False))

        offender_id = int(req.offender_id or 0)
        victim_id = int(req.victim_id or 0)
        max_rounds = max(2, min(req.round_limit or 3, 5))  # 2~5

        guidance_kind: Optional[str] = None
        guidance_text: Optional[str] = None

        base_payload: Dict[str, Any] = {
            "offender_id": offender_id,
            "victim_id": victim_id,
            "scenario": scenario,
            "victim_profile": victim_profile,
            "templates": templates,
            "max_turns": req.max_turns,
        }

        for round_no in range(1, max_rounds + 1):
            # ---- (A) 시뮬레이션 실행 ----

            sim_payload: Dict[str, Any] = dict(base_payload)

            if round_no >= 2:
                sim_payload.update({
                    "case_id_override": case_id,
                    "round_no": round_no,
                })
                if guidance_kind and guidance_text:
                    sim_payload["guidance"] = {"type": guidance_kind, "text": guidance_text}

            # 스냅샷 로그
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
            logger.info("[PromptSnapshot] %s", json.dumps(_truncate(snapshot), ensure_ascii=False))

            required = ["offender_id","victim_id","scenario","victim_profile","templates","max_turns"]
            missing = [k for k in required if k not in sim_payload]
            if missing:
                logger.error("[mcp.simulator_run] missing base keys: %s | sim_payload=%s",
                            missing, json.dumps(sim_payload, ensure_ascii=False)[:800])
                raise HTTPException(status_code=500, detail=f"sim payload missing: {missing}")

            # 강제 주입 JSON (최상위 data만 존재)
            injected_json = json.dumps({"data": sim_payload}, ensure_ascii=False)

            def _parsed_agent_input(x):
                from json import JSONDecoder
                if isinstance(x, str):
                    try:
                        return JSONDecoder().raw_decode(x.strip())[0]
                    except Exception:
                        pass
                return x

            # 1차 호출: 'data' 바깥 금지 명시
            llm_call = {
                "input": (
                    "아래 JSON이 **Action Input 전체**다. 이 JSON을 그대로 사용하고, "
                    "**'data' 바깥에 어떤 키도 추가하지 말라.** 반드시 아래 JSON 한 줄만 출력하라.\n"
                    "Action: mcp.simulator_run\n"
                    f"Action Input: {injected_json}"
                )
            }
            res_run = ex.invoke(llm_call, callbacks=[cap])
            used_tools.append("mcp.simulator_run")

            # 불일치 시 1회 재시도
            if cap.last_tool == "mcp.simulator_run":
                try:
                    agent_input = _parsed_agent_input(cap.last_tool_input)
                    intended = {"data": sim_payload}
                    if agent_input != intended:
                        logger.warning(
                            "[ToolInputMismatch] intended!=actual | intended=%s | actual=%s",
                            json.dumps(_truncate(intended), ensure_ascii=False),
                            json.dumps(_truncate(agent_input), ensure_ascii=False),
                        )
                        retry_msg = {
                            "input": (
                                "앞선 출력은 잘못되었다. 아래 JSON이 **Action Input 전체**다. "
                                "**'data' 바깥에 키를 추가하지 말라.**\n"
                                "Action: mcp.simulator_run\n"
                                f"Action Input: {injected_json}"
                            )
                        }
                        res_run = ex.invoke(retry_msg, callbacks=[cap])
                        used_tools.append("mcp.simulator_run(retry)")
                except Exception as e:
                    logger.warning("[ToolInputCheckError] %s", e)

            # ---- Observation 파싱부터는 기존 로직 유지 ----
            sim_obs = _last_observation(cap, "mcp.simulator_run")
            sim_dict = _loose_parse_json(sim_obs)
            if not sim_dict.get("ok"):
                raise HTTPException(status_code=500, detail=f"simulator_run failed: {sim_dict.get('error') or 'unknown'}")

            # case_id 확정/검증
            if round_no == 1:
                case_id = str(sim_dict.get("case_id") or "")
                if not case_id:
                    logger.error("[CaseID] 라운드1 case_id 추출 실패 | obs=%s", _truncate(sim_dict))
                    raise HTTPException(status_code=500, detail="case_id 추출 실패(라운드1)")
            else:
                got = str(sim_dict.get("case_id") or "")
                if got and got != case_id:
                    logger.warning("[CaseID] 이어달리기 불일치 감지: expected=%s, got=%s", case_id, got)

            rounds_done += 1

            # 판정용 turns 확보
            turns = sim_dict.get("turns") or (sim_dict.get("log") or {}).get("turns") or []
            logger.info("[SIM] case_id=%s turns=%s ended_by=%s",
                        sim_dict.get("case_id"), len(turns), sim_dict.get("ended_by"))


            # ── (B) 판정 생성: DB 의존 없이, 방금 턴으로 직접 판단 ──
            make_payload = {
                "data": {
                    "case_id": case_id,      # ★ _JudgeMakeInput 스키마 요구
                    "run_no": round_no,
                    "turns": turns           # ★ 핵심: 턴 직접 전달
                    # "log": sim_dict.get("log"),  # (tools_admin이 log 지원하면 추가로 전달해도 OK)
                    # "persist": False             # (스키마에 없으면 빼세요)
                }
            }
            res_make = ex.invoke(
                {"input": "admin.make_judgement 호출.\n" + json.dumps(make_payload, ensure_ascii=False)},
                callbacks=[cap],
            )
            used_tools.append("admin.make_judgement")

            # 방금 호출한 툴의 Observation에서 판단 JSON 확보 (+ fallback)
            judge_obs = _last_observation(cap, "admin.make_judgement")
            judgement = _loose_parse_json(judge_obs) or _loose_parse_json(res_make)
            if not judgement:
                for ev in reversed(cap.events):
                    if ev.get("type") == "observation":
                        cand = _loose_parse_json(ev.get("output"))
                        if isinstance(cand, dict) and ("phishing" in cand or "risk" in cand):
                            judgement = cand
                            break
            if not judgement:
                logger.error(
                    "[JudgementParse] 판정 JSON 추출 실패 | obs=%s | res=%s",
                    _truncate(judge_obs),
                    _truncate(res_make),
                )
                raise HTTPException(status_code=500, detail="판정 JSON 추출 실패(admin.make_judgement)")

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
                round_no, phishing, risk_lvl, risk_scr, cont_rec, _truncate(cont_msg, 200),
            )

            # ── (C) 다음 라운드를 위한 지침 선택 ──
            if round_no < max_rounds:
                guidance_kind = "P" if phishing else "A"
                logger.info("[GuidanceKind] round=%s | phishing=%s → kind=%s", round_no, phishing, guidance_kind)

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

                # 입력 검증(선택)
                if cap.last_tool == "admin.pick_guidance":
                    try:
                        agent_input = cap.last_tool_input
                        if isinstance(agent_input, str):
                            from json import JSONDecoder
                            agent_input = JSONDecoder().raw_decode(agent_input.strip())[0]
                        if agent_input != {"data": {"kind": guidance_kind}}:
                            logger.warning(
                                "[ToolInputMismatch] admin.pick_guidance intended!=actual | intended=%s | actual=%s",
                                json.dumps({"data": {"kind": guidance_kind}}, ensure_ascii=False),
                                json.dumps(_truncate(agent_input), ensure_ascii=False),
                            )
                    except Exception as e:
                        logger.warning("[ToolInputCheckError/pick_guidance] %s", e)

                # Observation 기반으로 지침 텍스트 뽑기(더 견고)
                pick_obs = _last_observation(cap, "admin.pick_guidance")
                guidance_text = _extract_guidance_text(pick_obs) or _extract_guidance_text(res_pick) or "기본 예방 수칙을 따르세요."
                logger.info("[GuidancePicked] round=%s | kind=%s | text=%s", round_no, guidance_kind, _truncate(guidance_text, 300))


            # ── (E) 종료 조건 ───────────────────────────────────
            MIN_ROUNDS = 2
            MAX_ROUNDS = max_rounds  # 위에서 계산한 값 재사용

            stop_on_critical = (risk_lvl == "critical") and (round_no >= MIN_ROUNDS)
            hit_max_rounds   = (round_no >= MAX_ROUNDS)

            if stop_on_critical or hit_max_rounds:
                logger.info(
                    "[StopCondition] 종료 | reason=%s | round=%s",
                    ("critical" if stop_on_critical else "max_rounds"),
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
