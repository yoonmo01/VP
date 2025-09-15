from mcp.server import Server, tool
from typing import List, Dict, Any, Optional
from ..schemas import SimulationInput, SimulationResult, Turn
from ..llm.providers import AttackerLLM, VictimLLM
from ..db.base import SessionLocal
from ..db.models import Conversation, TurnLog
from ..utils.end_rules import attacker_declared_end, VICTIM_END_LINE

# 하드캡(안전장치). env로 뺄 수 있음
MAX_OFFENDER_TURNS = 60
MAX_VICTIM_TURNS = 60

def register_simulate_dialogue_tool(server: Server):
    @tool(server=server, name="sim.simulate_dialogue",
          description="공격자/피해자 LLM 교대턴 시뮬레이션 실행 후 로그 반환 및 DB 저장")
    def simulate_dialogue(input: SimulationInput) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            # 1) 대화 컨테이너
            meta = {
                "offender_id": input.offender_id,
                "victim_id": input.victim_id,
                "round_no": input.round_no or 1,
                "guidance": input.guidance or {},
                "scenario": input.scenario,
            }
            conv = Conversation.create(db, meta=meta)

            # 2) LLM 준비
            atk = AttackerLLM(model=input.models["attacker"], system=input.attacker.system, temperature=input.temperature)
            vic = VictimLLM(model=input.models["victim"],   system=input.victim.system,   temperature=input.temperature)

            # 3) 상태
            turns: List[Turn] = []
            history_attacker: list = []
            history_victim: list = []
            turn_index = 0
            attacks = replies = 0
            last_victim_text = ""
            last_offender_text = ""
            guidance_text = (input.guidance or {}).get("text") or ""
            guidance_type = (input.guidance or {}).get("type") or ""
            max_turns = input.max_turns

            # 4) 루프 (티키타카 기준)
            for _ in range(max_turns):
                # 공격자
                if attacks >= MAX_OFFENDER_TURNS: break
                attacker_text = atk.next(
                    history=history_attacker,
                    last_victim=last_victim_text,
                    current_step="",               # step-lock이 필요하면 input.scenario에서 파생
                    guidance=guidance_text,
                    guidance_type=guidance_type
                )
                # 저장
                TurnLog(conversation_id=conv.id, idx=turn_index, role="offender", text=attacker_text)
                db.add(TurnLog(conversation_id=conv.id, idx=turn_index, role="offender", text=attacker_text))
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
                        db.add(TurnLog(conversation_id=conv.id, idx=turn_index, role="victim", text=victim_text)); db.commit()
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
                    conv.ended_by = ended_by
                    db.add(conv); db.commit()
                    break

                # 피해자
                if replies >= MAX_VICTIM_TURNS: break
                victim_meta = input.victim_profile.get("meta")
                victim_knowledge = input.victim_profile.get("knowledge")
                victim_traits = input.victim_profile.get("traits")
                victim_text = vic.next(
                    history=history_victim,
                    last_offender=last_offender_text,
                    meta=victim_meta,
                    knowledge=victim_knowledge,
                    traits=victim_traits,
                    guidance=guidance_text,
                    guidance_type=guidance_type
                )
                db.add(TurnLog(conversation_id=conv.id, idx=turn_index, role="victim", text=victim_text)); db.commit()
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

            result = SimulationResult(
                conversation_id=conv.id,
                turns=turns,
                ended_by=conv.ended_by or "",
                stats={"half_turns": turn_index, "turns": turn_index // 2},
                meta=meta
            )
            return {"result": result.model_dump()}
        finally:
            db.close()
