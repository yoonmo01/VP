# orchestrator/dev_router.py
import os, json, psycopg2
from typing import Any, Tuple, Dict, List, Optional
from fastapi import APIRouter, Body, Query
from .llm_providers import get_llm
from .prompts import build_attacker_action_guidelines, build_victim_action_guidelines
from .rules import rule_tag_kor, join_transcript_from_logs, judge_phishing_from_json
import re

router = APIRouter(prefix="/dev", tags=["dev"])

DSN = os.getenv("DATABASE_URL", "")
# SQLAlchemy-style URL을 psycopg2가 이해하는 형태로 보정
if DSN.startswith("postgresql+psycopg://"):
    DSN = DSN.replace("postgresql+psycopg://", "postgresql://", 1)
if DSN.startswith("postgresql+psycopg2://"):
    DSN = DSN.replace("postgresql+psycopg2://", "postgresql://", 1)
if not DSN:
    raise RuntimeError("DATABASE_URL이 비어 있습니다. 예) postgresql://user:pass@localhost:5432/voicephish")


def q(sql: str, params: Tuple = (), one: bool = False):
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                conn.commit()
                return {"ok": True}
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
            data = [dict(zip(cols, r)) for r in rows]
            return (data[0] if one else data)

def _search_prevention(tactic_code: Optional[str], level: Optional[str]):
    if tactic_code and level:
        return q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
            ORDER BY id ASC
        """, (tactic_code, level))
    elif tactic_code:
        return q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
            ORDER BY id ASC
        """, (tactic_code,))
    else:
        return q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active
            ORDER BY id ASC
        """)

def _search_attack(tactic_code: Optional[str], level: Optional[str]):
    if tactic_code and level:
        return q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
            ORDER BY id ASC
        """, (tactic_code, level))
    elif tactic_code:
        return q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
            ORDER BY id ASC
        """, (tactic_code,))
    else:
        return q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active
            ORDER BY id ASC
        """)
    
def _build_query_terms_from_transcript(transcript: str) -> str:
    t = re.sub(r"[\W_]+", " ", (transcript or "").lower())
    tokens = [w for w in t.split() if len(w) >= 2][:64]
    return " ".join(tokens) or ""

def _search_prevention_semantic(query_text: str, level: Optional[str]=None, hint: Optional[str]=None, topk: int=5):
    sql = """
    WITH q AS (
      SELECT %s::text AS qtxt,
             websearch_to_tsquery('simple', %s) AS qts
    )
    SELECT m.id, m.tactic_code, m.title, m.summary_md, m.script_md, m.level,
           GREATEST(similarity(m.title, q.qtxt), similarity(m.summary_md, q.qtxt)) AS s_head,
           similarity(m.script_md, q.qtxt) AS s_body,
           ts_rank(m.search_tsv, q.qts) AS s_tsv,
           CASE WHEN %s IS NOT NULL AND m.tactic_code = %s THEN 1 ELSE 0 END AS s_hint,
           (0.45*GREATEST(similarity(m.title, q.qtxt), similarity(m.summary_md, q.qtxt))
            + 0.45*similarity(m.script_md, q.qtxt)
            + 0.08*ts_rank(m.search_tsv, q.qts)
            + 0.02*CASE WHEN %s IS NOT NULL AND m.tactic_code = %s THEN 1 ELSE 0 END
           ) AS score
    FROM vp.prevention_module m
    CROSS JOIN q
    WHERE m.is_active
      AND (%s IS NULL OR m.level=%s)
      AND m.locale='ko'
    ORDER BY score DESC, m.id ASC
    LIMIT %s;
    """
    params = (query_text, query_text, hint, hint, hint, hint, level, level, topk)
    return q(sql, params)

def _search_attack_semantic(query_text: str, level: Optional[str]=None, hint: Optional[str]=None, topk: int=5):
    sql = """
    WITH q AS (
      SELECT %s::text AS qtxt,
             websearch_to_tsquery('simple', %s) AS qts
    )
    SELECT m.id, m.tactic_code, m.title, m.playbook_md, m.cues_md, m.level,
           GREATEST(similarity(m.title, q.qtxt), similarity(m.playbook_md, q.qtxt)) AS s_head,
           similarity(m.cues_md, q.qtxt) AS s_cues,
           ts_rank(
             setweight(to_tsvector('simple', COALESCE(m.title,'')), 'A') ||
             setweight(to_tsvector('simple', COALESCE(m.playbook_md,'')), 'B') ||
             setweight(to_tsvector('simple', COALESCE(m.cues_md,'')), 'C'), q.qts
           ) AS s_tsv,
           CASE WHEN %s IS NOT NULL AND m.tactic_code = %s THEN 1 ELSE 0 END AS s_hint,
           (0.45*GREATEST(similarity(m.title, q.qtxt), similarity(m.playbook_md, q.qtxt))
            + 0.45*similarity(m.cues_md, q.qtxt)
            + 0.08*ts_rank(
               setweight(to_tsvector('simple', COALESCE(m.title,'')), 'A') ||
               setweight(to_tsvector('simple', COALESCE(m.playbook_md,'')), 'B') ||
               setweight(to_tsvector('simple', COALESCE(m.cues_md,'')), 'C'), q.qts)
            + 0.02*CASE WHEN %s IS NOT NULL AND m.tactic_code = %s THEN 1 ELSE 0 END
           ) AS score
    FROM vp.attack_module m
    CROSS JOIN q
    WHERE m.is_active
      AND (%s IS NULL OR m.level=%s)
      AND m.locale='ko'
    ORDER BY score DESC, m.id ASC
    LIMIT %s;
    """
    params = (query_text, query_text, hint, hint, hint, hint, level, level, topk)
    return q(sql, params)


@router.post("/orchestrate-json")
async def orchestrate_json(
    payload: Dict[str, Any] = Body(..., description="시뮬레이터에서 보낸 원본 JSON"),
    level: str = Query("basic", description="모듈 레벨(basic|intermediate|advanced)"),
    batch_id: Optional[str] = Query(None, description="선택: sim_batch.id (UUID)"),
):
    # 1) 로그 → transcript / 피싱판정 / 전술 태그
    logs: List[Dict[str, Any]] = payload.get("logs") or []
    transcript = join_transcript_from_logs(logs)
    is_phished = judge_phishing_from_json(payload)
    tagged = rule_tag_kor(transcript)
    tactic_code = (tagged[0][0] if tagged else "generic")   # 표시/힌트용
    query_text = _build_query_terms_from_transcript(transcript)  # <-- 추가

    # 2) 인테이크 저장(sim_run_intake)
    case_uuid = payload.get("case_id")
    intake = q("""
        INSERT INTO vp.sim_run_intake (batch_id, case_id, raw_json, is_phished, tactic_code)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        RETURNING id
    """, (batch_id, case_uuid, json.dumps(payload, ensure_ascii=False), is_phished, tactic_code), one=True)
    intake_id = intake["id"]

    # 3) 모듈 선택 + LLM 생성
    llm = get_llm()
    message_for_target = None
    module = None
    target = None


    def pick_prevention():
        # 1차: 시맨틱 + 힌트 + level
        items = _search_prevention_semantic(query_text, level=level, hint=tactic_code, topk=5) or []
        # 2차: 시맨틱 + (힌트X)
        if not items:
            items = _search_prevention_semantic(query_text, level=level, hint=None, topk=5) or []
        # 3차: 시맨틱 + (levelX, 힌트X)
        if not items:
            items = _search_prevention_semantic(query_text, level=None, hint=None, topk=5) or []
        # 4차: 정확 태그 fallback
        if not items:
            items = _search_prevention(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = _search_prevention("generic", level) or []
        return items

    def pick_attack():
        items = _search_attack_semantic(query_text, level=level, hint=tactic_code, topk=5) or []
        if not items:
            items = _search_attack_semantic(query_text, level=level, hint=None, topk=5) or []
        if not items:
            items = _search_attack_semantic(query_text, level=None, hint=None, topk=5) or []
        if not items:
            items = _search_attack(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = _search_attack("generic", level) or []
        return items

    candidates = []
    if is_phished:
        # 피해자 교육 모듈 선택
        items = pick_prevention()
        candidates = items[:5]
        module = (items[0] if items else None)
        if module:
            prompt = build_victim_action_guidelines(
                tactic_code=tactic_code,
                summary_md=module["summary_md"],
                script_md=module["script_md"],
                transcript_preview=transcript[:300],
                is_phished=True,
            )
            message_for_target = await llm(prompt)

            # (선택) 거절성 문구 감지 시 1회 재시도
            refuse_markers = ["도와드릴 수 없습니다", "정책상", "refuse", "cannot help"]
            if any(m in (message_for_target or "") for m in refuse_markers):
                retry_prompt = prompt + """
    [주의/재시도]
    - 거절 없이, 정책 준수 범위에서 '추상적 행동 지침(Do/Don't)'만 제공.
    - 고유명사/식별자/URL/전화번호/앱명/기관명 금지. 신고·확인은 '공식 사이트/대표번호를 직접 검색해 이용'으로만 표현.
    """
                message_for_target = await llm(retry_prompt)

        try:
            q("""
            INSERT INTO vp.guidance_assignment (convo_id, target_role, module_table, module_id, notes, created_at)
            VALUES (%s, 'VICTIM', 'prevention', %s, %s, now())
            """, (None, module["id"], f"dev-json: intake_id={intake_id}"))
        except Exception:
            q("""
            INSERT INTO vp.audit_log(who, action, detail)
            VALUES ('orchestrator','guidance.assign.skip_uuid', %s::jsonb)
            """, (json.dumps({"case_uuid": case_uuid, "module_id": module["id"]}, ensure_ascii=False),))
        target = "VICTIM"

    else:
        # 공격자(연구/가상) 피드백 모듈 선택
        items = pick_attack()
        candidates = items[:5]
        module = (items[0] if items else None)
        if module:
            prompt = build_attacker_action_guidelines(
                tactic_code=tactic_code,
                playbook_md=module["playbook_md"],
                cues_md=module["cues_md"],
                transcript_preview=transcript[:300],
                objective="탐지/교육 목적의 추상화된 행동 기준 도출(실행 가능 디테일·우회요령 금지)"
            )
            message_for_target = await llm(prompt)

            # (선택) 거절성 문구 감지 시 1회 재시도
            refuse_markers = ["도와드릴 수 없습니다", "정책상", "refuse", "cannot help"]
            if any(m in (message_for_target or "") for m in refuse_markers):
                retry_prompt = prompt + """
        [주의/재시도]
        - 거절 없이, 정책 준수 범위에서 '추상적 행동 지침(Do/Don't)'만 제공.
        - 실세계 식별정보·구체 실행 단계·우회요령은 금지. [가상-토큰]만 사용.
        """
                message_for_target = await llm(retry_prompt)
            try:
                q("""
                INSERT INTO vp.guidance_assignment (convo_id, target_role, module_table, module_id, notes, created_at)
                VALUES (%s, 'ATTACKER', 'attack', %s, %s, now())
                """, (None, module["id"], f"dev-json: intake_id={intake_id}"))
            except Exception:
                q("""
                INSERT INTO vp.audit_log(who, action, detail)
                VALUES ('orchestrator','guidance.assign.skip_uuid', %s::jsonb)
                """, (json.dumps({"case_uuid": case_uuid, "module_id": module["id"]}, ensure_ascii=False),))
        target = "ATTACKER"

    # 4) 감사 로그
    q("""
      INSERT INTO vp.audit_log (who, action, detail, created_at)
      VALUES ('orchestrator', 'dev.orchestrate_json',
              %s::jsonb, now())
    """, (json.dumps({
        "intake_id": intake_id,
        "batch_id": batch_id,
        "case_id": case_uuid,
        "is_phished": is_phished,
        "tactic_code": tactic_code,
        "target": target,
        "module_used": (module or {}).get("id"),
    }, ensure_ascii=False),))

    # 5) 응답 (verbose 포함)
    return {
        "ok": True,
        "intake_id": intake_id,
        "case_id": case_uuid,
        "target": target,
        "is_phished": is_phished,
        "tactic_code": tactic_code,
        "module": module,
        "message_for_target": message_for_target,
        "verbose": {
            "tagged_candidates": tagged,          # [('impersonation.acquaintance', 0.4), ...]
            "transcript_preview": transcript[:400],
            "level": level,
            "batch_id": batch_id,
            "query_text": query_text 
        }
    }
