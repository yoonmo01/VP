# VP/mcp_server/mcp_server/tools/simulate_dialogue.py

from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from ..schemas import SimulationInput, SimulationResult, Turn
from ..llm.providers import AttackerLLM, VictimLLM
from ..db.base import SessionLocal
from ..db.models import Conversation, TurnLog
from ..utils.end_rules import attacker_declared_end, VICTIM_END_LINE


# FastMCP 등록용
from mcp.server.fastmcp import FastMCP

# 하드캡(안전장치). 필요 시 .env로 이관
MAX_OFFENDER_TURNS = 60
MAX_VICTIM_TURNS = 60

# ─────────────────────────────────────────────────────────
# FastMCP에 툴 등록 (server.py에서 호출)
# ─────────────────────────────────────────────────────────
def register_simulate_dialogue_tool_fastmcp(mcp: FastMCP):
    print(">> registering sim.simulate_dialogue and system.echo")

    @mcp.tool(name="system.echo", description="Echo back arguments.")
    async def system_echo(arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "echo": arguments}

    @mcp.tool(
        name="sim.simulate_dialogue",
        description="공격자/피해자 LLM 교대턴 시뮬레이션 실행 후 로그 반환 및 DB 저장"
    )
    async def simulate_dialogue(arguments: Dict[str, Any]) -> Dict[str, Any]:
        # 1) 입력 스키마 검증
        try:
            payload = _coerce_input_legacy(arguments)
            data = SimulationInput.model_validate(arguments)
        except ValidationError as ve:
            return {
                "ok": False,
                "error": "validation_error",
                "pydantic_errors": ve.errors(),
                "received": arguments,
            }

        # 2) 실제 실행
        try:
            out = simulate_dialogue_impl(data)
            # out이 Pydantic 모델이면 dump, dict면 그대로
            result = out.model_dump() if hasattr(out, "model_dump") else out
            return {"ok": True, "result": result}
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # ❗여기서 절대 예외를 밖으로 던지지 말고 JSON으로 반환
            return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}




def _coerce_input_legacy(arguments: Dict[str, Any]) -> Dict[str, Any]:
    args = dict(arguments or {})
    attacker = args.get("attacker") or {}
    victim = args.get("victim") or {}

    if not (attacker.get("system") and victim.get("system")):
        tpls = (args.get("templates") or {}) if isinstance(args.get("templates"), dict) else {}
        atk_tpl = tpls.get("attacker") or ""
        vic_tpl = tpls.get("victim") or ""
        if atk_tpl and not attacker.get("system"):
            attacker["system"] = f"[TEMPLATE:{atk_tpl}] 공격자 기본 시스템 프롬프트"
        if vic_tpl and not victim.get("system"):
            victim["system"] = f"[TEMPLATE:{vic_tpl}] 피해자 기본 시스템 프롬프트"
        args["attacker"] = attacker
        args["victim"] = victim

    return args

# ─────────────────────────────────────────────────────────
# 순수 구현 함수 (입력 → 실행 → dict 반환)
# ─────────────────────────────────────────────────────────
def simulate_dialogue_impl(input_obj: SimulationInput) -> Dict[str, Any]:
    """
    핵심 시뮬 엔진: 공격자/피해자 교대턴, MCP DB 저장, JSON 결과 반환.
    FastMCP에서 바로 호출 가능하도록 '순수 함수'로 분리.
    """
    db = SessionLocal()
    try:
        # 1) 대화 컨테이너/ID 결정
        #    - round 1: 새 conversation 생성
        #    - 이어달리기: case_id_override가 있으면 그 ID로 같은 대화에 이어쓰기
        conversation_id: Optional[str] = input_obj.case_id_override

        if conversation_id:
            # 이어달리기: 기존 row가 있으면 ended_by 업데이트만 수행, 없으면 TurnLog에만 이어쓴다.
            conv = db.get(Conversation, conversation_id)
            if conv is None:
                # 없을 수도 있으므로, 없는 경우에도 TurnLog에는 정상 기록되도록 conv는 None으로 둔다.
                conv = None
        else:
            meta = {
                "offender_id": input_obj.offender_id,
                "victim_id": input_obj.victim_id,
                "round_no": input_obj.round_no or 1,
                "guidance": input_obj.guidance or {},
                "scenario": input_obj.scenario,
            }
            conv = Conversation.create(db, meta=meta)
            conversation_id = conv.id

        # 2) LLM 준비
        atk = AttackerLLM(
            model=input_obj.models["attacker"],
            system=input_obj.attacker.system,
            temperature=input_obj.temperature,
        )
        vic = VictimLLM(
            model=input_obj.models["victim"],
            system=input_obj.victim.system,
            temperature=input_obj.temperature,
        )

        # 3) 상태
        turns: List[Turn] = []
        history_attacker: list = []
        history_victim: list = []
        turn_index = 0
        attacks = replies = 0
        last_victim_text = ""
        last_offender_text = ""
        guidance_text = (input_obj.guidance or {}).get("text") or ""
        guidance_type = (input_obj.guidance or {}).get("type") or ""
        max_turns = input_obj.max_turns

        # 4) 루프 (티키타카 기준)
        for _ in range(max_turns):
            # ── 공격자 발화 ─────────────────────────────
            if attacks >= MAX_OFFENDER_TURNS:
                break

            attacker_text = atk.next(
                history=history_attacker,
                last_victim=last_victim_text,
                current_step="",  # step-lock이 필요하면 input_obj.scenario에서 파생 가능
                guidance=guidance_text,
                guidance_type=guidance_type,
            )

            # 저장(반쪽턴: 공격자)
            db.add(
                TurnLog(
                    conversation_id=conversation_id,
                    idx=turn_index,
                    role="offender",
                    text=attacker_text,
                )
            )
            db.commit()
            turns.append(Turn(role="offender", text=attacker_text))

            # 히스토리
            try:
                from langchain_core.messages import AIMessage, HumanMessage
                history_attacker.append(AIMessage(attacker_text))
                history_victim.append(HumanMessage(attacker_text))
            except Exception:
                pass

            last_offender_text = attacker_text
            turn_index += 1
            attacks += 1

            # 공격자 종료 선언 → 피해자 한 줄 후 종료
            if attacker_declared_end(attacker_text):
                if replies < MAX_VICTIM_TURNS:
                    victim_text = VICTIM_END_LINE
                    db.add(
                        TurnLog(
                            conversation_id=conversation_id,
                            idx=turn_index,
                            role="victim",
                            text=victim_text,
                        )
                    )
                    db.commit()
                    turns.append(Turn(role="victim", text=victim_text))
                    try:
                        from langchain_core.messages import AIMessage, HumanMessage
                        history_victim.append(AIMessage(victim_text))
                        history_attacker.append(HumanMessage(victim_text))
                    except Exception:
                        pass
                    turn_index += 1
                    replies += 1

                ended_by = "attacker_end"
                if conv is not None:
                    conv.ended_by = ended_by
                    db.add(conv)
                    db.commit()
                break

            # ── 피해자 발화 ─────────────────────────────
            if replies >= MAX_VICTIM_TURNS:
                break

            victim_meta = input_obj.victim_profile.get("meta")
            victim_knowledge = input_obj.victim_profile.get("knowledge")
            victim_traits = input_obj.victim_profile.get("traits")

            victim_text = vic.next(
                history=history_victim,
                last_offender=last_offender_text,
                meta=victim_meta,
                knowledge=victim_knowledge,
                traits=victim_traits,
                guidance=guidance_text,
                guidance_type=guidance_type,
            )

            db.add(
                TurnLog(
                    conversation_id=conversation_id,
                    idx=turn_index,
                    role="victim",
                    text=victim_text,
                )
            )
            db.commit()
            turns.append(Turn(role="victim", text=victim_text))

            try:
                from langchain_core.messages import AIMessage, HumanMessage
                history_victim.append(AIMessage(victim_text))
                history_attacker.append(HumanMessage(victim_text))
            except Exception:
                pass

            last_victim_text = victim_text
            turn_index += 1
            replies += 1

        # 5) 결과 구성
        meta_out = {
            "offender_id": input_obj.offender_id,
            "victim_id": input_obj.victim_id,
            "round_no": input_obj.round_no or 1,
            "guidance": input_obj.guidance or {},
            "scenario": input_obj.scenario,
        }
        result = SimulationResult(
            conversation_id=conversation_id,
            turns=turns,
            ended_by=(conv.ended_by if conv is not None else "") or "",
            stats={"half_turns": turn_index, "turns": turn_index // 2},
            meta=meta_out,
        )
        return {"result": result.model_dump()}
    finally:
        db.close()


