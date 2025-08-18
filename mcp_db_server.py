# mcp_db_server.py  — FastMCP 버전
import os, json, psycopg2
from typing import Any, Tuple, Optional

from mcp.server.fastmcp import FastMCP

DSN = os.getenv("DATABASE_URL", "")
# SQLAlchemy-style URL을 psycopg2가 이해하는 형태로 보정
if DSN.startswith("postgresql+psycopg://"):
    DSN = DSN.replace("postgresql+psycopg://", "postgresql://", 1)
if DSN.startswith("postgresql+psycopg2://"):
    DSN = DSN.replace("postgresql+psycopg2://", "postgresql://", 1)
if not DSN:
    raise RuntimeError("DATABASE_URL이 비어 있습니다. 예) postgresql://user:pass@localhost:5432/voicephish")

mcp = FastMCP("vp-db")

def q(sql: str, params: Tuple = (), one: bool = False) -> Any:
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

def _looks_like_uuid(s: str) -> bool:
    return isinstance(s, str) and s.count("-") == 4 and len(s) >= 36

# --------------------------
# 로그 / 판정 (admincase 또는 vp.* 둘 다 지원)
# --------------------------

@mcp.tool(name="logs.get")
def logs_get(convo_id: str) -> dict:
    """
    대화 로그/메타 조회.
    - admincase(기존 시뮬) UUID면 admincase.evidence를 transcript로 반환
    - 숫자면 vp.convo(transcript, meta)에서 조회
    """
    if _looks_like_uuid(convo_id):
        row = q("""
            SELECT id, evidence AS transcript,
                   json_build_object('source','admincase') AS meta
            FROM admincase WHERE id=%s
        """, (convo_id,), one=True)
    else:
        row = q("""
            SELECT id, round_id, transcript, meta
            FROM vp.convo WHERE id=%s
        """, (int(convo_id),), one=True)
    return row or {}

@mcp.tool(name="outcome.get")
def outcome_get(convo_id: str) -> dict:
    """
    대화의 피싱 판정 조회.
    - admincase: phishing(boolean), evidence(reason) 사용
    - vp.outcome: is_phished/ confidence/ reason 사용
    """
    if _looks_like_uuid(convo_id):
        row = q("""
            SELECT phishing AS is_phished,
                   NULL::numeric AS confidence,
                   evidence AS reason
            FROM admincase WHERE id=%s
        """, (convo_id,), one=True)
    else:
        row = q("""
            SELECT is_phished, confidence, reason
            FROM vp.outcome WHERE convo_id=%s
        """, (int(convo_id),), one=True)
    return row or {}

# --------------------------
# 전술 태그
# --------------------------

@mcp.tool(name="tactic.list")
def tactic_list(convo_id: int) -> list[dict]:
    rows = q("""
        SELECT tactic_code, score
        FROM vp.convo_tactic
        WHERE convo_id=%s
        ORDER BY score DESC
    """, (convo_id,))
    return rows

@mcp.tool(name="tactic.upsert_bulk")
def tactic_upsert_bulk(convo_id: int, items: list[dict]) -> dict:
    """
    items: [{ "tactic_code": str, "score": float }, ...]
    """
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        for it in items:
            cur.execute(
                """
                INSERT INTO vp.convo_tactic (convo_id, tactic_code, score)
                VALUES (%s, %s, %s)
                ON CONFLICT (convo_id, tactic_code)
                DO UPDATE SET score=EXCLUDED.score
                """,
                (convo_id, it["tactic_code"], it["score"]),
            )
        conn.commit()
    return {"upserted": len(items)}

# --------------------------
# 모듈 검색
# --------------------------

@mcp.tool(name="prevention.search")
def prevention_search(tactic_code: Optional[str]=None, level: Optional[str]=None) -> list[dict]:
    if tactic_code and level:
        rows = q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
            ORDER BY id ASC
        """, (tactic_code, level))
    elif tactic_code:
        rows = q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
            ORDER BY id ASC
        """, (tactic_code,))
    else:
        rows = q("""
            SELECT id, tactic_code, title, summary_md, script_md, level
            FROM vp.prevention_module
            WHERE is_active
            ORDER BY id ASC
        """)
    return rows

@mcp.tool(name="attack.search")
def attack_search(tactic_code: Optional[str]=None, level: Optional[str]=None) -> list[dict]:
    if tactic_code and level:
        rows = q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
            ORDER BY id ASC
        """, (tactic_code, level))
    elif tactic_code:
        rows = q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
            ORDER BY id ASC
        """, (tactic_code,))
    else:
        rows = q("""
            SELECT id, tactic_code, title, playbook_md, cues_md, level
            FROM vp.attack_module
            WHERE is_active
            ORDER BY id ASC
        """)
    return rows

# --------------------------
# 할당/감사
# --------------------------

@mcp.tool(name="guidance.assign")
def guidance_assign(convo_id: int, target_role: str, module_table: str, module_id: int, notes: str = "") -> dict:
    """
    target_role: 'VICTIM' | 'ATTACKER'
    module_table: 'prevention' | 'attack'
    """
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO vp.guidance_assignment (convo_id, target_role, module_table, module_id, notes)
            VALUES (%s,%s,%s,%s,%s) RETURNING id
        """, (convo_id, target_role, module_table, module_id, notes))
        new_id = cur.fetchone()[0]
        conn.commit()
    return {"assignment_id": new_id}

@mcp.tool(name="audit.write")
def audit_write(action: str, who: str = "orchestrator", detail: Optional[dict] = None) -> dict:
    detail_json = json.dumps(detail or {}, ensure_ascii=False)
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO vp.audit_log (who, action, detail)
            VALUES (%s,%s,%s) RETURNING id
        """, (who, action, detail_json))
        new_id = cur.fetchone()[0]
        conn.commit()
    return {"audit_id": new_id}

if __name__ == "__main__":
    # stdio 전송으로 실행 (오케스트레이터 StdioClient가 붙음)
    mcp.run()
