# app/routers/simulator.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
import os, json

# DB / Models
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import models as m
from app.db.session import try_get_db

# (선택) 기존 OpenAI 더미 호출 그대로 사용
from openai import OpenAI

_openai_api_key = os.getenv("OPENAI_API_KEY")
_client = OpenAI(api_key=_openai_api_key) if _openai_api_key else None

router = APIRouter(tags=["simulator"])


# ---------- I/O Schemas ----------
class TickInject(BaseModel):
    target: Optional[str] = Field(None, description="'VICTIM' or 'ATTACKER'")
    message: Optional[str] = None


class SeedIn(BaseModel):
    case_id: Optional[UUID] = None
    offender_id: int
    victim_id: int
    case_scenario: Optional[Dict[str, Any]] = None


class SeedOut(BaseModel):
    case_id: UUID


class TickIn(BaseModel):
    case_id: Optional[UUID] = None
    offender_id: Optional[int] = None
    victim_id: Optional[int] = None
    case_scenario: Optional[Dict[str, Any]] = None  # ← 시나리오 인라인/최초 시드용
    inject: Optional[TickInject] = None
    meta: Optional[Dict[str, Any]] = None


class LogItem(BaseModel):
    role: str  # "offender" | "victim"
    content: str
    label: Optional[str] = None


class TickOut(BaseModel):
    case_id: UUID
    logs: List[LogItem]
    meta: Optional[Dict[str, Any]] = None


# ---------- helpers ----------
def _next_turn_index(db: Session, case_id: UUID) -> int:
    last = (db.query(m.ConversationLog.turn_index).filter(
        m.ConversationLog.case_id == case_id).order_by(
            m.ConversationLog.turn_index.desc()).first())
    return (last[0] + 1) if last else 0


def _assert_turn_role(turn_index: int, role: str):
    expected = "offender" if turn_index % 2 == 0 else "victim"
    if role != expected:
        raise HTTPException(
            500, f"Turn {turn_index} must be {expected}, got {role}")


def _call_llm_system_prompt() -> str:
    return ("역할: 보이스피싱 시뮬레이터.\n"
            "규칙: 전부 가상/연구 맥락. 현실의 계좌/전화/링크/식별자/기관명/앱명 언급 금지.\n"
            "규칙: 구체 실행 지시/우회요령 금지. 추상/상황 서술 위주.\n"
            "규칙: 출력은 JSON 딕셔너리 형태로만, keys=['offender','victim'].")


def _build_user_prompt(target: str, inject_msg: str, context_text: str) -> str:
    tgt = (target or "ATTACKER").upper()
    goal = ("ATTACKER: 연구/가상 전술을 요약적으로 시도하고, 상대를 설득하려는 맥락을 1~2문장으로 출력."
            if tgt == "ATTACKER" else
            "VICTIM: 안전한 행동/의심/확인 중심으로 1~2문장 반응. 송금/개인정보 제공 없이 검증 유도.")
    hint = f"가이드라인(오케스트레이터 주입): {inject_msg}" if inject_msg else "가이드라인: (없음)"
    ctx = f"[직전 맥락]\n{context_text}\n" if context_text else "[직전 맥락] (없음)\n"
    return (f"{ctx}[목표]\n{goal}\n[힌트]\n{hint}\n\n"
            "형식 지시: 반드시 아래 JSON 예시처럼만 출력\n"
            '{"offender":"...가상의 공격자 멘트...", "victim":"...가상의 피해자 반응..."}\n'
            "주의: 따옴표/이스케이프 오류 없이 유효 JSON으로만 출력.")


def _ask_llm(target: str, inject_msg: str,
             context_text: str) -> Dict[str, str]:
    if _client is None:
        # 더미
        if (target or "").upper() == "ATTACKER":
            return {"offender": "(가상) 설득 강화 시도", "victim": "(가상) 의심/검증 유도"}
        else:
            return {"offender": "(가상) 압박/정당화 시도", "victim": "(가상) 거절/검증 유도"}

    msgs = [
        {
            "role": "system",
            "content": _call_llm_system_prompt()
        },
        {
            "role": "user",
            "content": _build_user_prompt(target, inject_msg, context_text)
        },
    ]
    resp = _client.chat.completions.create(
        model=os.getenv("SIM_LLM_MODEL", "gpt-4o-mini"),
        messages=msgs,
        temperature=0.6,
        max_tokens=300,
    )
    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
        return {
            "offender": str(data.get("offender", "")).strip() or "(가상) 공격자 멘트",
            "victim": str(data.get("victim", "")).strip() or "(가상) 피해자 멘트",
        }
    except Exception:
        # 포맷 실패 → 안전 기본값
        if (target or "").upper() == "ATTACKER":
            return {"offender": "(가상) 설득 강화 시도", "victim": "(가상) 의심/검증 유도"}
        else:
            return {"offender": "(가상) 압박/정당화 시도", "victim": "(가상) 거절/검증 유도"}


def _context_text(db: Session, case_id: UUID, max_turns: int = 8) -> str:
    rows = (db.query(m.ConversationLog).filter(
        m.ConversationLog.case_id == case_id).order_by(
            m.ConversationLog.turn_index.asc()).all())
    picks = rows[-max_turns:]
    lines = []
    for r in picks:
        lines.append(f"{r.role.upper()}: {r.content}")
    return "\n".join(lines)


# ---------- endpoints ----------
@router.post("/seed", response_model=SeedOut)
def seed(body: SeedIn, db: Session = Depends(get_db)):
    """
    특정 offender/victim과 시나리오로 케이스를 생성만 한다. (턴 생성 X)
    """
    case = m.AdminCase(scenario=body.case_scenario or {})
    db.add(case)
    db.commit()
    db.refresh(case)

    # 0번째 턴 직전 상태로 기록은 안 하지만, case에 offender/victim을 묶어두기 위해
    # 첫 턴을 생성할 때 offender_id/victim_id를 ConversationLog에 함께 저장합니다.
    # (별도 링크 테이블이 없다면 첫 턴 쓰기 시 두 id를 같이 저장하는 방식으로 지속)
    return SeedOut(case_id=case.id)


@router.post("/tick", response_model=TickOut)
def tick(body: TickIn, db: Session = Depends(get_db)):
    # 0) case_id 결정 (DB 없어도 UUID 생성만)
    case_id = body.case_id or uuid4()

    # 1) 이름/프로필: DB 없으면 더미 이름으로
    offender_name = f"공격자#{body.offender_id or 'X'}"
    victim_name = f"피해자#{body.victim_id or 'X'}"

    if db is not None:
        # ✅ DB가 있을 때만 안전하게 조회 (실패해도 전체 흐름은 계속)
        try:
            from app.db import models as m
            if body.offender_id:
                off = db.get(m.PhishingOffender, body.offender_id)
                if off:
                    offender_name = off.name or offender_name
            if body.victim_id:
                vic = db.get(m.Victim, body.victim_id)
                if vic:
                    victim_name = vic.name or victim_name
        except Exception:
            pass  # 조회 실패해도 계속

    # 2) 컨텍스트: DB 없으면 빈 문자열
    context_text = ""
    if db is not None:
        try:
            from app.db import models as m
            rows = (db.query(m.ConversationLog).filter(
                m.ConversationLog.case_id == case_id).order_by(
                    m.ConversationLog.turn_index.asc()).all())
            picks = rows[-8:]
            context_text = "\n".join(f"{r.role.upper()}: {r.content}"
                                     for r in picks)
        except Exception:
            context_text = ""

    # 3) LLM(또는 더미)로 2줄 생성
    inject_msg = (body.inject.message or "").strip() if body.inject else ""
    target = (body.inject.target if body.inject else None) or "ATTACKER"
    gen = _ask_llm(target, inject_msg, context_text)

    # 4) DB가 있으면 저장, 없으면 저장 생략하고 바로 반환
    if db is not None:
        try:
            from app.db import models as m
            # turn_index 계산
            last = (db.query(m.ConversationLog.turn_index).filter(
                m.ConversationLog.case_id == case_id).order_by(
                    m.ConversationLog.turn_index.desc()).first())
            start_idx = (last[0] + 1) if last else 0

            def _save(role: str, content: str, idx: int):
                log = m.ConversationLog(
                    case_id=case_id,
                    offender_id=body.offender_id,
                    victim_id=body.victim_id,
                    turn_index=idx,
                    role=role,
                    content=content,
                )
                db.add(log)

            if target.upper() == "ATTACKER":
                _save("offender", gen["offender"], start_idx)
                _save("victim", gen["victim"], start_idx + 1)
            else:
                _save("victim", gen["victim"], start_idx)
                _save("offender", gen["offender"], start_idx + 1)

            db.commit()
        except Exception:
            # 저장 실패해도 응답은 내보낸다
            pass

    return TickOut(case_id=case_id,
                   logs=[
                       LogItem(role="offender", content=gen["offender"]),
                       LogItem(role="victim", content=gen["victim"]),
                   ],
                   meta={
                       "tick_at": datetime.now(timezone.utc).isoformat(),
                       **(body.meta or {})
                   })
