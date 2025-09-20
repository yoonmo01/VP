# app/services/agent/tools_admin.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import json

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.agent.guideline_repo_db import GuidelineRepoDB
from app.core.logging import get_logger
from app.utils.ids import safe_uuid   # ★ 추가


from app.services.admin_summary import summarize_run_full
from app.services.llm_providers import agent_chat

import json, ast, re, os, httpx
from fastapi import HTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://127.0.0.1:5177")
# ─────────────────────────────────────────────────────────
# 입력 스키마 & 공통 언래퍼
# ─────────────────────────────────────────────────────────

class _JudgeReadInput(BaseModel):
    case_id: UUID
    run_no: int = Field(1, ge=1)

class _JudgeMakeInput(BaseModel):
    case_id: UUID
    run_no: int = Field(1, ge=1)
    # 오케스트레이터가 바로 턴을 넘겨줄 수 있게 허용
    turns: Optional[List[Dict[str, Any]]] = None
    log: Optional[Dict[str, Any]] = None

class _GuidanceInput(BaseModel):
    kind: str = Field(..., pattern="^(P|A)$", description="지침 종류: 'P'(피해자) | 'A'(공격자)")

class _SavePreventionInput(BaseModel):
    case_id: UUID
    offender_id: int
    victim_id: int
    run_no: int = Field(1, ge=1)
    summary: str
    steps: List[str] = Field(default_factory=list)

# ★ 추가: 최종예방책 생성 입력
class _MakePreventionInput(BaseModel):
    case_id: UUID
    rounds: int = Field(..., ge=1)
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    judgements: List[Dict[str, Any]] = Field(default_factory=list)
    guidances: List[Dict[str, Any]] = Field(default_factory=list)
    # 포맷은 고정적으로 personalized_prevention을 기대
    format: str = Field("personalized_prevention")


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """코드펜스/설명 섞여도 JSON만 뽑아 파싱 시도."""
    text = text.strip()
    # ```json ... ``` 제거
    fence = re.compile(r"^```(?:json)?\s*(\{.*\})\s*```$", re.S)
    m = fence.match(text)
    if m:
        text = m.group(1).strip()
    # 최외곽 { ... } 추출
    if not (text.startswith("{") and text.endswith("}")):
        m2 = re.search(r"\{.*\}$", text, re.S)
        if m2:
            text = m2.group(0)
    try:
        return json.loads(text)
    except Exception:
        try:
            obj = ast.literal_eval(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None

def _fetch_turns_from_mcp(case_id: UUID, run_no: int) -> List[Dict[str, Any]]:
    """
    MCP가 제공하는 대화로그(JSON) 엔드포인트에서 특정 라운드의 전체 턴을 받아온다.
    기대 형식: [{"role": "attacker"|"victim"|"system", "text": "...", "meta": {...}}, ...]
    기본 엔드포인트 가정: GET {MCP_BASE_URL}/api/cases/{case_id}/turns?run={run_no}
    """
    url = f"{MCP_BASE_URL}/api/cases/{case_id}/turns"
    params = {"run": run_no}
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"[MCP] 대화 로그 조회 실패: {e}")
        raise HTTPException(status_code=502, detail=f"MCP 대화로그 조회 실패: {e}")

    # 서버 스키마에 맞게 정규화
    turns: Any = None
    if isinstance(data, dict):
        # 흔한 케이스들 대응
        if "turns" in data:
            turns = data["turns"]
        elif "result" in data and isinstance(data["result"], dict) and "turns" in data["result"]:
            turns = data["result"]["turns"]
        else:
            # 루트에 라운드별 묶음이 있을 수도 있음: {"run":1,"turns":[...]} 등
            if all(isinstance(v, list) for v in data.values()):
                # 첫 번째 리스트를 turns로 가정
                turns = next(iter(data.values()))
    elif isinstance(data, list):
        turns = data

    if not isinstance(turns, list):
        raise HTTPException(status_code=502, detail="MCP 응답에서 turns 배열을 찾을 수 없습니다.")
    return turns  # type: ignore[return-value]


class SingleData(BaseModel):
    data: Any  # ★ 문자열/딕셔너리 모두 허용

def _unwrap(obj: Any) -> Dict[str, Any]:
    """LangChain Action Input 견고 언래핑."""
    try:
        if hasattr(obj, 'model_dump'):
            obj = obj.model_dump()

        if isinstance(obj, dict):
            return obj.get("data", obj)

        if isinstance(obj, str):
            try:
                parsed = json.loads(obj)
                return parsed.get("data", parsed) if isinstance(parsed, dict) else {"raw": parsed}
            except json.JSONDecodeError:
                return {"raw": obj}

        return {"raw": str(obj)}
    except Exception as e:
        logger.error(f"[_unwrap] 오류: {e}")
        return {"error": str(e)}

def _persist_verdict(
    db: Session,
    *,
    case_id: UUID,
    run_no: int,
    verdict: Dict[str, Any],
) -> bool:
    """
    verdict 예:
      {
        "phishing": False,
        "evidence": "...",
        "risk": {"score": 10, "level": "low", "rationale": "..."},
        "victim_vulnerabilities": [...],
        "continue": {"recommendation": "continue", "reason": "..."}
      }
    """
    success = False

    # 1) AdminCaseSummary가 있으면 라운드별로 저장/업서트
    try:
        if hasattr(m, "AdminCaseSummary"):
            Model = m.AdminCaseSummary
            row = (
                db.query(Model)
                  .filter(Model.case_id == case_id, Model.run == run_no)
                  .first()
            )
            if not row:
                row = Model(case_id=case_id, run=run_no)
                db.add(row)

            row.phishing = bool(verdict.get("phishing", False))

            if hasattr(Model, "evidence"):
                setattr(row, "evidence", str(verdict.get("evidence", ""))[:4000])

            risk = verdict.get("risk") or {}
            if hasattr(Model, "risk_score"):
                setattr(row, "risk_score", int(risk.get("score", 0) or 0))
            if hasattr(Model, "risk_level"):
                setattr(row, "risk_level", str(risk.get("level", "") or ""))
            if hasattr(Model, "risk_rationale"):
                setattr(row, "risk_rationale", str(risk.get("rationale", "") or "")[:2000])

            if hasattr(Model, "vulnerabilities"):
                setattr(row, "vulnerabilities", verdict.get("victim_vulnerabilities", []))
            if hasattr(Model, "verdict_json"):
                setattr(row, "verdict_json", verdict)

            success = True
    except Exception as e:
        logger.warning(f"[admin.make_judgement] AdminCaseSummary 저장/업데이트 실패: {e}")

    # 2) 항상 AdminCase에 최신 요약 + 히스토리 라인 누적
    try:
        case = db.get(m.AdminCase, case_id)
        if not case:
            if success:
                db.commit()
            return success

        # 케이스 단위 phishing은 OR
        case.phishing = bool(getattr(case, "phishing", False) or verdict.get("phishing", False))

        # 최신 요약 컬럼이 존재할 경우에만 세팅(없어도 동작)
        risk = verdict.get("risk") or {}
        cont = verdict.get("continue") or {}

        if hasattr(case, "last_run_no"):
            case.last_run_no = run_no
        if hasattr(case, "last_risk_score"):
            case.last_risk_score = int(risk.get("score", 0) or 0)
        if hasattr(case, "last_risk_level"):
            case.last_risk_level = str(risk.get("level", "") or "")
        if hasattr(case, "last_risk_rationale"):
            case.last_risk_rationale = str(risk.get("rationale", "") or "")
        if hasattr(case, "last_vulnerabilities"):
            case.last_vulnerabilities = verdict.get("victim_vulnerabilities", [])
        if hasattr(case, "last_recommendation"):
            case.last_recommendation = str(cont.get("recommendation", "") or "")
        if hasattr(case, "last_recommendation_reason"):
            case.last_recommendation_reason = str(cont.get("reason", "") or "")

        # 라운드 히스토리 라인 누적 (run 포함)
        prev = (case.evidence or "").strip()
        piece = json.dumps({"run": run_no, "verdict": verdict}, ensure_ascii=False)
        case.evidence = (prev + ("\n" if prev else "") + piece)[:8000]

        success = True
        db.commit()
        return success

    except Exception as e:
        logger.warning(f"[admin.make_judgement] AdminCase 저장 실패: {e}")
        try:
            db.commit()
        except Exception:
            pass
        return success
    

def _format_evidence_text(*, turns: List[Dict[str, Any]], verdict: Dict[str, Any]) -> str:
    """판단 결과를 읽기 쉬운 한국어 텍스트로 정리."""
    # 안전 추출
    risk = verdict.get("risk") or {}
    level = str((risk.get("level") or "")).lower()
    score = int(risk.get("score", 0) or 0)
    rationale = (risk.get("rationale") or "").strip()

    vulns = verdict.get("victim_vulnerabilities") or []
    cont  = verdict.get("continue") or {}
    reco  = (cont.get("recommendation") or "").strip()
    reco_reason = (cont.get("reason") or "").strip()

    # 간단 턴 스니펫(앞/뒤 몇 개만)
    def _clean(t: str) -> str:
        return (t or "").replace("\n", " ").strip()

    head = ""
    tail = ""
    try:
        first_attacker = next((t for t in turns if t.get("role") in ("attacker","offender")), None)
        first_victim   = next((t for t in turns if t.get("role") == "victim"), None)
        last_attacker  = next((t for t in reversed(turns) if t.get("role") in ("attacker","offender")), None)
        last_victim    = next((t for t in reversed(turns) if t.get("role") == "victim"), None)
        head = f"초기 제안: 공격자='{_clean(first_attacker.get('text') if first_attacker else '')}', 피해자='{_clean(first_victim.get('text') if first_victim else '')}'"
        tail = f"최종 응답: 공격자='{_clean(last_attacker.get('text') if last_attacker else '')}', 피해자='{_clean(last_victim.get('text') if last_victim else '')}'"
    except Exception:
        pass

    vulns_str = " / ".join(map(str, vulns)) if isinstance(vulns, list) else str(vulns)

    lines = [
        "※ 보이스피싱 라운드 판정 요약",
        f"- 위험도: level={level or 'n/a'}, score={score}",
        f"- 근거: {rationale or '근거 서술 없음'}",
        f"- 피해자 취약점: {vulns_str or '표기 없음'}",
        f"- 권고: {reco or 'n/a'} — {reco_reason or ''}".strip(),
    ]
    if head: lines.append(f"- {head}")
    if tail: lines.append(f"- {tail}")

    return " | ".join(lines)

# ─────────────────────────────────────────────────────────
# 동적 지침 생성 도구
# ─────────────────────────────────────────────────────────
def make_guidance_generation_tool(db: Session):
    """동적 지침 생성 도구를 생성합니다."""
    from app.services.agent.guidance_generator import DynamicGuidanceGenerator
    generator = DynamicGuidanceGenerator()

    @tool(
        "admin.generate_guidance",
        description="시나리오/피해자/이전판정을 바탕으로 공격자용 맞춤 지침을 생성합니다."
    )
    def generate_guidance(input_data: Any) -> Dict[str, Any]:
        try:
            # 문자열이면 JSON 파싱 시도
            if isinstance(input_data, str):
                try:
                    parsed_data = json.loads(input_data)
                except json.JSONDecodeError:
                    parsed_data = {"raw": input_data}
            elif isinstance(input_data, dict):
                parsed_data = input_data
            else:
                parsed_data = {"raw": str(input_data)}

            # 파라미터 추출(문자열로 들어온 경우까지 방어)
            case_id          = parsed_data.get("case_id")
            round_no         = int(parsed_data.get("round_no", 2) or 2)
            scenario         = parsed_data.get("scenario") or {}
            victim_profile   = parsed_data.get("victim_profile") or {}
            previous_judgments = parsed_data.get("previous_judgments") or []

            # JSON 문자열일 수 있는 값들 파싱
            if isinstance(scenario, str):
                try: scenario = json.loads(scenario)
                except json.JSONDecodeError: scenario = {}
            if isinstance(victim_profile, str):
                try: victim_profile = json.loads(victim_profile)
                except json.JSONDecodeError: victim_profile = {}
            if isinstance(previous_judgments, str):
                try: previous_judgments = json.loads(previous_judgments)
                except json.JSONDecodeError: previous_judgments = []

            # case_id 안전화
            u = safe_uuid(case_id) if case_id else None
            if not u:
                logger.warning("[generate_guidance] case_id 누락/형식오류 → 임시값 사용")
                case_id = "temp_case_id"
            else:
                case_id = str(u)

            result = generator.generate_guidance(
                db=db,
                case_id=case_id,
                round_no=round_no,
                scenario=scenario,
                victim_profile=victim_profile,
                previous_judgments=previous_judgments,
            )

            return {
                "ok": True,
                "type": "A",
                "text": result.get("guidance_text", ""),
                "categories": result.get("selected_categories", []),
                "reasoning": result.get("reasoning", ""),
                "expected_effect": result.get("expected_effect", ""),
                "generation_method": "dynamic_analysis",
            }

        except Exception as e:
            logger.exception("[admin.generate_guidance] 실패")
            return {
                "ok": False,
                "error": str(e),
                "type": "A",
                "text": "긴급성을 강조하고 피해자의 불안감을 자극해 반응을 유도하세요.",
                "generation_method": "fallback",
            }

    return generate_guidance

# ─────────────────────────────────────────────────────────
# 기존 도구들
# ─────────────────────────────────────────────────────────
def make_admin_tools(db: Session, repo: GuidelineRepoDB) -> List:

    @tool(
    "admin.make_judgement",
    args_schema=SingleData,
    description="(case_id, run_no)의 전체 대화를 MCP JSON 또는 전달받은 turns로 판정한다. DB는 결과 저장에만 사용한다."
)
    def make_judgement(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)
        try:
            ji = _JudgeMakeInput(**payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"JudgeMakeInput 검증 실패: {e}")

        # 1) Action Input으로 턴이 오면 그대로 사용
        turns: Optional[List[Dict[str, Any]]] = ji.turns

        # 2) 없으면 MCP에서 가져오기 (DB 접근 금지)
        if turns is None and ji.log and isinstance(ji.log, dict):
            maybe = ji.log.get("turns")
            if isinstance(maybe, list):
                turns = maybe
        if turns is None:
            turns = _fetch_turns_from_mcp(ji.case_id, ji.run_no)

        # 3) 턴 기반 요약/판정
        try:
            verdict = summarize_run_full(turns=turns)  # 반드시 turns-only 시그니처
        except TypeError as te:
            logger.error("[admin.make_judgement] summarize_run_full가 turns 기반 시그니처를 지원해야 합니다.")
            raise HTTPException(
                status_code=500,
                detail="summarize_run_full이 'turns' 인자를 지원하도록 업데이트해 주세요."
            ) from te

        # ── 정책 오버라이드: critical일 때만 stop, 그 외는 continue ──
        risk = verdict.get("risk") or {}
        score = int(risk.get("score", 0) or 0)
        score = 0 if score < 0 else (100 if score > 100 else score)
        risk["score"] = score

        level = str((risk.get("level") or "").lower())
        if level not in {"low", "medium", "high", "critical"}:
            level = ("critical" if score >= 75 else
                    "high"     if score >= 50 else
                    "medium"   if score >= 25 else
                    "low")
        risk["level"] = level
        verdict["risk"] = risk

        if level == "critical":
            verdict["continue"] = {
                "recommendation": "stop",
                "reason": "위험도가 critical로 판정되어 시뮬레이션을 종료합니다."
            }
        else:
            verdict["continue"] = {
                "recommendation": "continue",
                "reason": "위험도가 critical이 아니므로 다음 라운드를 진행합니다."
            }

        # DB에는 결과만 저장
        evidence_text = _format_evidence_text(turns=turns, verdict=verdict)
        verdict["evidence"] = evidence_text  # 항상 텍스트로 저장되도록 강제

        # DB 저장은 동일
        persisted = _persist_verdict(db, case_id=ji.case_id, run_no=ji.run_no, verdict=verdict)

        # 로그도 텍스트 evidence 기준으로 출력
        logger.info(
            "[Judgement][case:%s][run:%s] phishing=%s | risk(score=%s, level=%s) | continue=%s",
            str(ji.case_id), ji.run_no, bool(verdict.get("phishing")),
            verdict["risk"]["score"], verdict["risk"]["level"],
            verdict["continue"]["recommendation"],
        )
        logger.info("[Judgement][case:%s][run:%s][evidence] %s", str(ji.case_id), ji.run_no, evidence_text)

        return {
            "ok": True,
            "persisted": persisted,
            "case_id": str(ji.case_id),
            "run_no": ji.run_no,
            **verdict,
        }

    @tool("admin.judge", args_schema=SingleData,
          description="특정 케이스의 특정 라운드에 대해 보이스피싱 성공 여부를 판정합니다.")
    def judge_simulation(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        u = safe_uuid(payload.get("case_id", ""))
        if not u:
            return {"ok": False, "error": "invalid case_id"}
        case_id = u

        run_no = payload.get("run_no") or payload.get("round_no")
        if run_no is None:
            return {"ok": False, "error": "run_no 또는 round_no가 필요합니다."}
        run_no = int(run_no)

        try:
            logs = (
                db.query(m.ConversationLog)
                  .filter(m.ConversationLog.case_id == case_id,
                          m.ConversationLog.run == run_no)
                  .order_by(m.ConversationLog.turn_index.asc())
                  .all()
            )
            if not logs:
                return {"ok": False, "error": "해당 라운드의 로그가 없습니다."}

            # ★ 대화로그 터미널에 찍기
            logger.info(f"[admin.judge] case:{case_id} run:{run_no} 대화로그 ↓↓↓")
            for l in logs:
                logger.info(f"[{l.turn_index:02d}][{l.role}] {l.content}")

            victim_responses = [ (log.content or "").lower()
                                 for log in logs if log.role == "victim" ]

            success_indicators = ["계좌번호","비밀번호","카드번호","주민번호","otp","인증번호",
                                  "이체하겠습니다","송금하겠습니다","앱을 설치하겠습니다","알겠습니다",
                                  "네 알겠어요","그렇게 하겠습니다"]
            failure_indicators = ["사기","보이스피싱","의심","신고","경찰","확인하겠습니다",
                                  "끊겠습니다","거부","안 하겠습니다","믿을 수 없습니다"]

            success_score = sum(ind in r for r in victim_responses for ind in success_indicators)
            failure_score = sum(ind in r for r in victim_responses for ind in failure_indicators)

            last_offender = next((log for log in reversed(logs) if log.role == "offender"), None)
            forced_termination = bool(last_offender and "여기서 마무리하겠습니다" in (last_offender.content or ""))

            phishing = success_score > failure_score and not forced_termination
            confidence = abs(success_score - failure_score) / max(len(victim_responses), 1)

            return {
                "ok": True,
                "phishing": phishing,
                "reason": f"성공신호:{success_score}, 실패신호:{failure_score}, 강제종료:{forced_termination}",
                "confidence": confidence,
                "success_indicators_found": success_score,
                "failure_indicators_found": failure_score,
                "forced_termination": forced_termination,
                "total_turns": len(logs),
                "analysis_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("[admin.judge] 판정 실패")
            return {"ok": False, "error": str(e)}
        
    @tool(
    "admin.make_prevention",
    args_schema=SingleData,
    description=(
        "대화(turns)+판단(judgements)+지침(guidances)로 최종 예방책(personalized_prevention) JSON을 생성한다. "
        "Action Input 예: {'data': {'case_id':UUID,'rounds':int,'turns':[...],'judgements':[...],'guidances':[...],'format':'personalized_prevention'}}"
    )
)    
    def make_prevention(data: Any) -> Dict[str, Any]:
        raw = _unwrap(data)

        # ① 문자열로 왔을 때: 본문에서 JSON 객체만 추출 → data 키 벗겨내기
        if "raw" in raw and isinstance(raw["raw"], str):
            parsed = _safe_json_parse(raw["raw"]) or {}
            if isinstance(parsed, dict):
                raw = parsed.get("data", parsed)

        # ② 이미 {"data": {...}} 형태면 data만 꺼내기
        if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
            raw = raw["data"]

        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail="잘못된 입력 형식입니다.")

        # ③ case_id 확보 (없으면 최근 로그에서 복구)
        u = safe_uuid(raw.get("case_id", ""))
        if not u:
            try:
                last = (
                    db.query(m.ConversationLog)
                    .order_by(m.ConversationLog.created_at.desc())
                    .first()
                )
                if last and last.case_id:
                    u = last.case_id
                    logger.warning("[admin.make_prevention] 입력에 case_id 없음 → 최근 로그로 복구: %s", str(u))
            except Exception:
                pass
        if not u:
            raise HTTPException(status_code=422, detail="case_id가 필요합니다.")
        raw["case_id"] = u  # UUID 객체 그대로 넣어도 Pydantic에서 처리됨

        # ④ 필수/옵션 필드 보강
        raw.setdefault("turns", [])
        raw.setdefault("judgements", [])
        raw.setdefault("guidances", [])
        raw.setdefault("format", "personalized_prevention")

        # rounds 누락 시 보강: judgements 길이 또는 최소 1
        if "rounds" not in raw or not isinstance(raw["rounds"], int):
            raw["rounds"] = max(1, len(raw.get("judgements") or []))

        try:
            pi = _MakePreventionInput(**raw)
        except Exception as e:
            logger.exception("[admin.make_prevention] 입력 검증 실패: %s", e)
            raise HTTPException(status_code=422, detail=f"MakePreventionInput 검증 실패: {e}")

        llm = agent_chat(temperature=0.2)

        # 스키마 힌트
        schema_hint = {
            "personalized_prevention": {
                "summary": "string (2~3문장)",
                "analysis": {
                    "outcome": "success|fail",
                    "reasons": ["string", "string", "string"],
                    "risk_level": "low|medium|high|critical"
                },
                "steps": ["명령형 한국어 단계 5~9개"],
                "tips": ["체크리스트형 팁 3~6개"]
            }
        }

        system = (
            "너는 보이스피싱 예방 전문가다. 입력된 대화/판단/지침을 바탕으로, "
            "아래 스키마에 '정확히' 맞춘 JSON만 출력하라. "
            "코드블럭/주석/설명/자유문 금지. 오직 JSON 하나만.\n"
            "- summary: 2~3문장 한국어 요약\n"
            "- analysis.outcome: 'success' 또는 'fail'\n"
            "- analysis.reasons: 한국어 문자열 최소 3개\n"
            "- analysis.risk_level: 'low'|'medium'|'high'|'critical'\n"
            "- steps: 명령형 한국어 5~9개 (불릿/번호/마침표 없이 간결하게)\n"
            "- tips: 체크리스트형 3~6개 (간결한 문장)\n"
            "출력은 최상위 키 'personalized_prevention' 하나만 가지는 JSON 객체여야 한다."
        )

        user = {
            "case_id": str(pi.case_id),
            "rounds": pi.rounds,
            "guidances": pi.guidances,
            "judgements": pi.judgements,
            "turns": pi.turns,
            "format": pi.format,
            "schema": schema_hint
        }

        messages = [
            ("system", system),
            ("human", "다음 입력을 바탕으로 'personalized_prevention' 키 하나만 있는 JSON을 출력하라.\n"
                    + json.dumps(user, ensure_ascii=False))
        ]

        try:
            res = llm.invoke(messages)
            text = getattr(res, "content", str(res))
            parsed = _safe_json_parse(text) or {}
            if "personalized_prevention" not in parsed:
                logger.warning("[Prevention][case:%s] LLM 응답에 personalized_prevention 누락. raw: %.300s",
                            str(pi.case_id), text)
                return {
                    "ok": False,
                    "error": "missing_key_personalized_prevention",
                    "raw": text[:1200]
                }

            result = {
                "ok": True,
                "case_id": str(pi.case_id),
                "personalized_prevention": parsed["personalized_prevention"]
            }

            # ▶ 로그: 예방책 요약/스텝 간단 출력
            pp = result["personalized_prevention"]
            logger.info("[Prevention][case:%s] summary: %s", str(pi.case_id), pp.get("summary", "")[:200])
            steps = pp.get("steps") or []
            if isinstance(steps, list):
                logger.info("[Prevention][case:%s] steps(%d): %s", str(pi.case_id), len(steps), "; ".join(map(str, steps[:6])))

            return result

        except Exception as e:
            logger.exception("[Prevention] LLM 호출 실패")
            return {"ok": False, "error": f"llm_error: {e!s}"}

    @tool("admin.save_prevention", args_schema=SingleData,
      description="시뮬레이션 결과를 바탕으로 예방책을 저장합니다.")
    def save_prevention(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        case_uuid = safe_uuid(payload.get("case_id", ""))
        if not case_uuid:
            return {"ok": False, "error": "invalid case_id"}

        try:
            # 1) run 번호 정규화
            run_no = payload.get("run_no") or payload.get("round_no") or payload.get("run") or 1
            try:
                run_no = int(run_no)
            except Exception:
                run_no = 1

            # 2) summary / steps 정규화 (steps는 문자열도 리스트로 승격)
            summary = (
                payload.get("summary")
                or (payload.get("content") or {}).get("summary")
                or ""
            )
            raw_steps = (
                payload.get("steps")
                or payload.get("recommendation_steps")
                or payload.get("recommendations")
                or (payload.get("content") or {}).get("recommendation_steps")
                or []
            )
            if isinstance(raw_steps, dict):
                # 가장 의도한 필드
                extracted = (
                    raw_steps.get("prevention_steps")
                    or raw_steps.get("steps")
                    or raw_steps.get("recommendation_steps")
                    or raw_steps.get("recommendations")
                    or []
                )
                raw_steps = extracted

            # 리스트/문자열/기타 타입 정규화
            if isinstance(raw_steps, str):
                steps = [raw_steps]
            elif isinstance(raw_steps, list):
                # 각 요소를 문자열로 통일 + 공백 제거 + 빈 값 제거
                steps = [str(s).strip() for s in raw_steps if str(s).strip()]
            else:
                # dict가 아니고 list/str도 아니면 문자열로 감싸서 1개짜리 리스트
                steps = [str(raw_steps).strip()] if str(raw_steps).strip() else []

            # 3) offender_id / victim_id 보강 (없으면 최근 대화로그에서 추론)
            offender_id = payload.get("offender_id")
            victim_id   = payload.get("victim_id")
            if offender_id is None or victim_id is None:
                last = (
                    db.query(m.ConversationLog)
                    .filter(m.ConversationLog.case_id == case_uuid)
                    .order_by(m.ConversationLog.created_at.desc())
                    .first()
                )
                if last:
                    if offender_id is None: offender_id = last.offender_id
                    if victim_id   is None: victim_id   = last.victim_id
                    
            # 이후 그대로 저장
            prevention = m.PersonalizedPrevention(
                case_id=case_uuid,
                offender_id=offender_id,
                victim_id=victim_id,
                run=run_no,
                content={"summary": summary, "recommendation_steps": steps},
                note=payload.get("note"),
                is_active=True,
            )

            db.add(prevention)
            db.commit()
            db.refresh(prevention)

            out = {
                "ok": True,
                "prevention_id": str(prevention.id),
                "case_id": str(case_uuid),
                "run_no": run_no,
                "summary_length": len(summary),
                "steps_count": len(steps),
            }


            # ★ 예방책 생성 결과도 터미널에 찍기
            logger.info(f"[admin.save_prevention] case:{case_uuid} run:{run_no} 예방책 ↓↓↓")
            logger.info(f"요약: {summary}")
            for idx, s in enumerate(steps, 1):
                logger.info(f"  {idx}. {s}")
            return out

        except Exception as e:
            logger.exception("[admin.save_prevention] 저장 실패")
            db.rollback()
            return {"ok": False, "error": str(e)}

    @tool("admin.pick_guidance", args_schema=SingleData,
          description="(DEPRECATED) 기존 DB에서 지침을 선택합니다. 새 시스템에서는 admin.generate_guidance 사용.")
    def pick_guidance(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)
        kind = (payload.get("kind") or "A").upper()
        fallback = {
            "A": "긴급성을 강조하고 피해자의 불안감을 자극하여 빠른 대응을 유도하세요.",
            "P": "의심스러운 연락은 공식 채널로 재확인하세요.",
        }
        return {"ok": True, "type": kind, "text": fallback.get(kind, "기본 지침을 따르세요."),
                "source": "legacy_fallback", "deprecation_warning": "admin.generate_guidance 사용 권장"}

    guidance_tool = make_guidance_generation_tool(db)
    return [make_judgement, judge_simulation, make_prevention, save_prevention, pick_guidance, guidance_tool]

