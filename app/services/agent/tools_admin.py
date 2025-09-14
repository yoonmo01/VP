from __future__ import annotations
from typing import Dict, Any, Optional, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db import models as m

import json, ast

from app.core.logging import get_logger
from app.services.admin_summary import (
    summarize_case,            # 케이스 단위(레거시)
    summarize_run_full,        # ⟵ 라운드별 전체대화 판정 (신규)
)

logger = get_logger(__name__)

# ---- 공통: {"data": {...}} 입력 통일 ----
class SingleData(BaseModel):
    data: Any = Field(..., description="이 안에 실제 페이로드를 담는다")

def _to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        try:
            return json.loads(s)
        except Exception:
            try:
                return ast.literal_eval(s)
            except Exception:
                raise HTTPException(status_code=422, detail="data는 JSON 객체여야 합니다.")
    raise HTTPException(status_code=422, detail="data는 JSON 객체여야 합니다.")

def _unwrap_data(obj: Any) -> Dict[str, Any]:
    d = _to_dict(obj)
    return _to_dict(d.get("data")) if "data" in d else d

def _normalize_kind(val: Any) -> str:
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{"):
            try:
                parsed = json.loads(s)
            except Exception:
                try:
                    parsed = ast.literal_eval(s)
                except Exception:
                    raise HTTPException(status_code=422, detail="kind 형식 오류")
            k = parsed.get("kind") or parsed.get("type")
            if isinstance(k, str):
                return k
        return s
    raise HTTPException(status_code=422, detail="kind는 문자열이어야 합니다.")

# ----- 검증용 내부 스키마 -----
class _JudgeReadInput(BaseModel):
    case_id: UUID
    run_no: int = Field(1, ge=1)

class _JudgeMakeInput(BaseModel):
    case_id: UUID
    run_no: int = Field(1, ge=1)

class _GuidanceInput(BaseModel):
    kind: str = Field(..., pattern="^(P|A)$", description="지침 종류: 'P'(피해자) | 'A'(공격자)")

class _SavePreventionInput(BaseModel):
    case_id: UUID
    offender_id: int
    victim_id: int
    run_no: int = Field(1, ge=1)
    summary: str
    steps: List[str] = Field(default_factory=list)

# ─────────────────────────────────────────────────────────
# 저장/조회(가능 시 AdminCaseSummary, 아니면 AdminCase.evidence에 누적)
# ─────────────────────────────────────────────────────────
def _persist_verdict(
    db: Session,
    *,
    case_id: UUID,
    run_no: int,
    verdict: Dict[str, Any],
) -> bool:
    """
    verdict: {
      phishing: bool,
      evidence: str,
      risk: {score:int, level:str, rationale:str},
      victim_vulnerabilities: [str,...],
      continue: {recommendation:str, reason:str}
    }
    """
    try:
        if hasattr(m, "AdminCaseSummary"):
            Model = m.AdminCaseSummary
            exists = (
                db.query(Model)
                  .filter(Model.case_id == case_id, Model.run == run_no)
                  .first()
            )
            if exists:
                # 멱등
                return True
            row = Model(
                case_id=case_id,
                run=run_no,
                phishing=bool(verdict.get("phishing", False)),
            )
            # 칼럼 존재 시 추가 기입
            if hasattr(Model, "evidence"):
                setattr(row, "evidence", str(verdict.get("evidence", ""))[:4000])
            if hasattr(Model, "reason") and not getattr(row, "evidence", None):
                setattr(row, "reason", str(verdict.get("evidence", ""))[:2000])
            risk = verdict.get("risk") or {}
            if hasattr(Model, "risk_score"):
                setattr(row, "risk_score", int(risk.get("score", 0)))
            if hasattr(Model, "risk_level"):
                setattr(row, "risk_level", str(risk.get("level", "")))
            if hasattr(Model, "risk_rationale"):
                setattr(row, "risk_rationale", str(risk.get("rationale", ""))[:2000])
            if hasattr(Model, "vulnerabilities"):
                setattr(row, "vulnerabilities", verdict.get("victim_vulnerabilities", []))
            if hasattr(Model, "verdict_json"):
                setattr(row, "verdict_json", verdict)
            db.add(row)
            db.commit()
            return True
    except Exception as e:
        logger.warning(f"[admin.make_judgement] AdminCaseSummary 저장 실패: {e}")

    # Fallback: AdminCase.evidence에 JSON 문자열로 누적
    try:
        case = db.get(m.AdminCase, case_id)
        if not case:
            return False
        prev = (case.evidence or "").strip()
        piece = json.dumps({"run": run_no, "verdict": verdict}, ensure_ascii=False)
        case.evidence = (prev + ("\n" if prev else "") + piece)[:8000]
        # 케이스 단위 phishing은 OR
        case.phishing = bool(getattr(case, "phishing", False) or verdict.get("phishing", False))
        db.commit()
        return True
    except Exception as e:
        logger.warning(f"[admin.make_judgement] AdminCase fallback 저장 실패: {e}")
        return False

def _read_persisted_verdict(db: Session, *, case_id: UUID, run_no: int) -> Optional[Dict[str, Any]]:
    # 1) AdminCaseSummary 우선
    try:
        if hasattr(m, "AdminCaseSummary"):
            Model = m.AdminCaseSummary
            row = (
                db.query(Model)
                  .filter(Model.case_id == case_id, Model.run == run_no)
                  .first()
            )
            if row:
                ev = ""
                if hasattr(row, "evidence") and getattr(row, "evidence", None):
                    ev = row.evidence
                elif hasattr(row, "reason") and getattr(row, "reason", None):
                    ev = row.reason
                risk = {}
                if hasattr(row, "risk_score"):
                    risk["score"] = int(getattr(row, "risk_score", 0) or 0)
                if hasattr(row, "risk_level"):
                    risk["level"] = getattr(row, "risk_level", None) or ""
                if hasattr(row, "risk_rationale"):
                    risk["rationale"] = getattr(row, "risk_rationale", None) or ""
                vul = []
                if hasattr(row, "vulnerabilities") and getattr(row, "vulnerabilities", None):
                    vul = list(row.vulnerabilities or [])
                # verdict_json이 있으면 우선
                if hasattr(row, "verdict_json") and getattr(row, "verdict_json", None):
                    vj = dict(row.verdict_json or {})
                    # 최소 필드 보장
                    vj.setdefault("evidence", ev)
                    vj.setdefault("risk", risk or {"score": 0, "level": "", "rationale": ""})
                    vj.setdefault("victim_vulnerabilities", vul)
                    vj.setdefault("phishing", bool(getattr(row, "phishing", False)))
                    vj.setdefault("continue", {"recommendation":"continue","reason":""})
                    return vj
                # 없으면 조립
                return {
                    "phishing": bool(getattr(row, "phishing", False)),
                    "evidence": ev,
                    "risk": risk or {"score": 0, "level": "", "rationale": ""},
                    "victim_vulnerabilities": vul,
                    "continue": {"recommendation":"continue","reason":""},
                }
    except Exception:
        pass

    # 2) Fallback: AdminCase.evidence에서 run별 JSON 찾기
    try:
        case = db.get(m.AdminCase, case_id)
        raw = (getattr(case, "evidence", "") or "")
        # {"run": N, "verdict": {...}} 패턴 라인 검색
        for line in raw.splitlines():
            try:
                obj = json.loads(line)
                if int(obj.get("run", -1)) == run_no and isinstance(obj.get("verdict"), dict):
                    return obj["verdict"]
            except Exception:
                continue
    except Exception:
        pass

    return None

# ─────────────────────────────────────────────────────────
# 툴 팩토리
# ─────────────────────────────────────────────────────────
def make_admin_tools(db: Session, guideline_repo):
    @tool(
        "admin.make_judgement",
        args_schema=SingleData,
        description="(case_id, run_no)의 **전체 대화(공/피)** 를 LLM으로 판정하여 phishing/evidence/risk/vulnerabilities/continue를 생성하고 저장한다."
    )
    def make_judgement(data: Any) -> Dict[str, Any]:
        payload = _unwrap_data(data)
        try:
            ji = _JudgeMakeInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"JudgeMakeInput 검증 실패: {e}")

        verdict = summarize_run_full(db, ji.case_id, ji.run_no)

        # ── 정책 오버라이드: critical일 때만 stop, 그 외는 continue ──
        risk = verdict.get("risk") or {}
        # score 정규화
        score = int(risk.get("score", 0) or 0)
        if score < 0: score = 0
        if score > 100: score = 100
        risk["score"] = score

        level = str((risk.get("level") or "")).lower()
        if level not in {"low", "medium", "high", "critical"}:
            level = ("critical" if score >= 75 else
                     "high"     if score >= 50 else
                     "medium"   if score >= 25 else
                     "low")
        risk["level"] = level
        verdict["risk"] = risk

        rec = "stop" if level == "critical" else "continue"
        cont = verdict.get("continue") or {}
        reason = cont.get("reason") or (
            "위험도가 critical로 판정되어 시나리오를 종료합니다."
            if rec == "stop" else
            "위험도가 critical이 아니므로 수법 고도화/추가 라운드를 권고합니다."
        )
        verdict["continue"] = {"recommendation": rec, "reason": reason}
        # ───────────────────────────────────────────────

        persisted = _persist_verdict(db, case_id=ji.case_id, run_no=ji.run_no, verdict=verdict)

        # 결과 그대로 반환
        return {
            "ok": True,
            "persisted": persisted,
            "case_id": str(ji.case_id),
            "run_no": ji.run_no,
            **verdict,
        }

    @tool(
        "admin.judge",
        args_schema=SingleData,
        description="(case_id, run_no)의 저장된 판정을 조회. 없으면 케이스 전체 로그로 summarize_case를 수행해 evidence만 반환(호환 목적)."
    )
    def judge(data: Any) -> Dict[str, Any]:
        payload = _unwrap_data(data)
        try:
            ji = _JudgeReadInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"JudgeInput 검증 실패: {e}")

        saved = _read_persisted_verdict(db, case_id=ji.case_id, run_no=ji.run_no)
        if saved is not None:
            # 기존 Orchestrator 호환: reason = evidence
            out = {
                "phishing": bool(saved.get("phishing", False)),
                "reason": str(saved.get("evidence", "")),
                "run_no": ji.run_no,
            }
            # 추가 필드도 함께 반환(신규 파이프라인에서 사용)
            out.update({
                "evidence": saved.get("evidence", ""),
                "risk": saved.get("risk", {"score":0,"level":"","rationale":""}),
                "victim_vulnerabilities": saved.get("victim_vulnerabilities", []),
                "continue": saved.get("continue", {"recommendation":"continue","reason":""}),
            })
            return out

        # Fallback: 케이스 전체 로그로 레거시 요약(evidence만)
        res = summarize_case(db, ji.case_id) or {}
        return {
            "phishing": bool(res.get("phishing")),
            "reason": str(res.get("evidence", "")),
            "run_no": ji.run_no,
            "evidence": str(res.get("evidence", "")),
            "risk": {"score": 0, "level": "", "rationale": "저장된 라운드 판정이 없어 케이스 단위 요약 결과만 제공"},
            "victim_vulnerabilities": [],
            "continue": {"recommendation": "continue", "reason": "라운드별 판정 부재"},
        }

    @tool(
        "admin.pick_guidance",
        args_schema=SingleData,
        description="상황에 맞는 지침을 선택한다. Action Input은 {'data': {'kind': 'P'|'A'}}"
    )
    def pick_guidance(data: Any) -> Dict[str, str]:
        payload = _unwrap_data(data)
        if "kind" not in payload:
            raise HTTPException(status_code=422, detail="kind 누락")
        kind = _normalize_kind(payload["kind"])
        try:
            gi = _GuidanceInput(kind=kind)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"GuidanceInput 검증 실패: {e}")

        if gi.kind == "P":
            text, title = guideline_repo.pick_preventive()
        else:
            text, title = guideline_repo.pick_attack()
        return {"type": gi.kind, "title": title, "text": text}

    @tool(
        "admin.save_prevention",
        args_schema=SingleData,
        description="개인화된 예방책을 DB에 저장한다. Action Input은 {'data': {'case_id':UUID,'offender_id':int,'victim_id':int,'run_no':int,'summary':str,'steps':[str,...]}}"
    )
    def save_prevention(data: Any) -> str:
        payload = _unwrap_data(data)
        try:
            spi = _SavePreventionInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"SavePreventionInput 검증 실패: {e}")

        obj = m.PersonalizedPrevention(
            case_id=spi.case_id,
            offender_id=spi.offender_id,
            victim_id=spi.victim_id,
            run=spi.run_no,
            content={"summary": spi.summary, "steps": spi.steps},
            note="agent-generated",
            is_active=True,
        )
        db.add(obj)
        db.commit()
        return str(obj.id)

    return [make_judgement, judge, pick_guidance, save_prevention]
