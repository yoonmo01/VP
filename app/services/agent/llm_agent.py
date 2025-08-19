# app/services/agent/llm_agent.py
import json
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import asc
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.llm_providers import agent_chat
from app.services.admin_summary import summarize_case
from app.db import models as m


class SimpleAgent:

    def __init__(self, db: Session):
        self.db = db

    def decide_kind(self, case_id: UUID) -> str:
        try:
            res = summarize_case(self.db, case_id) or {}
            phishing = res.get("phishing")
        except Exception:
            phishing = None
        if phishing is True: return "P"
        if phishing is False: return "A"
        return "P"

    def personalize(self, case_id: UUID, offender_id: int, victim_id: int,
                    run_no: int) -> Dict[str, Any]:
        return {
            "summary":
            "피해자와 상황을 고려한 맞춤형 예방 가이드",
            "steps": [
                "송금·인증 요청은 반드시 다른 채널로 재확인(직접 전화)",
                "출처 불명 URL·QR·APK 클릭/설치 금지, 원격제어 앱 차단",
                "의심 시 112 또는 1332로 즉시 상담 및 지급정지 요청",
            ],
            "meta": {
                "case_id": str(case_id),
                "run": run_no
            }
        }


class LLMAgent:
    """모든 출력은 한국어. JSON만 반환하도록 강제."""

    def __init__(self, db: Session):
        self.db = db
        self.llm = agent_chat()

    def _load_context(self,
                      case_id: UUID,
                      limit: int = 20) -> List[Dict[str, Any]]:
        rows = (self.db.query(m.ConversationLog).filter(
            m.ConversationLog.case_id == case_id).order_by(
                asc(m.ConversationLog.run),
                asc(m.ConversationLog.turn_index)).limit(limit).all())
        return [{"role": r.role, "text": r.content} for r in rows]

    def decide_kind(self, case_id: UUID) -> str:
        turns = self._load_context(case_id, limit=30)
        sys = SystemMessage(content=("너는 보이스피싱 시뮬레이션을 평가하는 한국어 보안 분석 AI다. "
                                     "반드시 JSON만 출력해라."))
        user = HumanMessage(content=(
            "아래 대화 맥락을 읽고 다음 재실행에서 어떤 지침이 더 적절한지 판단해라.\n"
            "- 'P' = 예방 대책(피해자 보호 강화)\n"
            "- 'A' = 공격 시나리오(적대적 스트레스테스트)\n"
            "JSON 스키마(한국어): {\"kind\": \"P\"|\"A\", \"reason\": \"한국어 설명\"}\n"
            f"대화: {json.dumps(turns, ensure_ascii=False)}"))
        out = self.llm.invoke([sys, user]).content.strip()
        try:
            data = json.loads(out)
            kind = data.get("kind")
            return "P" if kind == "P" else ("A" if kind == "A" else "P")
        except Exception:
            return SimpleAgent(self.db).decide_kind(case_id)

    def personalize(self, case_id: UUID, offender_id: int, victim_id: int,
                    run_no: int) -> Dict[str, Any]:
        turns = self._load_context(case_id, limit=40)
        sys = SystemMessage(content=("너는 한국어 사이버 안전 코치다. 반드시 JSON만 출력하라."))
        user = HumanMessage(
            content=("아래 대화를 바탕으로 피해자에게 맞춤형 예방 대책을 한국어로 작성하라.\n"
                     "JSON 스키마: {\n"
                     "  \"summary\": \"요약(한국어)\",\n"
                     "  \"steps\": [\"구체적 실행 단계(한국어)\", ...]\n"
                     "}\n"
                     f"대화: {json.dumps(turns, ensure_ascii=False)}"))
        out = self.llm.invoke([sys, user]).content.strip()
        try:
            data = json.loads(out)
            if not isinstance(
                    data,
                    dict) or "summary" not in data or "steps" not in data:
                raise ValueError("bad schema")
            return data
        except Exception:
            return SimpleAgent(self.db).personalize(case_id, offender_id,
                                                    victim_id, run_no)
