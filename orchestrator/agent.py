# orchestrator/agent.py
import os, json, psycopg2
from typing import Optional, Dict, Any, Tuple, List
from .rules import rule_tag
from .prompts import build_victim_action_guidelines, build_attacker_action_guidelines
from .llm_providers import get_llm
import asyncio

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

async def _q_async(sql: str, params: Tuple = (), one: bool = False):
    return await asyncio.to_thread(q, sql, params, one)

def _looks_like_uuid(s: str) -> bool:
    return isinstance(s, str) and s.count("-") == 4 and len(s) >= 36

class Orchestrator:
    def __init__(self):
        self.llm = get_llm()

    async def _get_logs(self, convo_id: str) -> Dict[str, Any]:
        if _looks_like_uuid(convo_id):
            row = await _q_async("""
                SELECT id, evidence AS transcript, json_build_object('source','admincase') AS meta
                FROM admincase WHERE id=%s
            """, (convo_id,), one=True)
        else:
            row = await _q_async("""
                SELECT id, transcript, meta FROM vp.convo WHERE id=%s
            """, (int(convo_id),), one=True)
        return row or {}

    async def _get_outcome(self, convo_id: str) -> Dict[str, Any]:
        if _looks_like_uuid(convo_id):
            row = await _q_async("""
                SELECT phishing AS is_phished,
                       NULL::numeric AS confidence,
                       evidence AS reason
                FROM admincase WHERE id=%s
            """, (convo_id,), one=True)
        else:
            row = await _q_async("""
                SELECT is_phished, confidence, reason
                FROM vp.outcome WHERE convo_id=%s
            """, (int(convo_id),), one=True)
        return row or {}

    async def _get_tactics(self, convo_id: str) -> List[Dict[str, Any]]:
        if _looks_like_uuid(convo_id):
            return []
        return await _q_async("""
            SELECT tactic_code, score
            FROM vp.convo_tactic
            WHERE convo_id=%s
            ORDER BY score DESC
        """, (int(convo_id),))

    async def _upsert_tactics(self, convo_id: str, items: List[Dict[str, Any]]):
        if _looks_like_uuid(convo_id):
            return
        async def _do():
            with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
                for it in items:
                    cur.execute("""
                        INSERT INTO vp.convo_tactic (convo_id, tactic_code, score)
                        VALUES (%s,%s,%s)
                        ON CONFLICT (convo_id, tactic_code) DO UPDATE SET score=EXCLUDED.score
                    """, (int(convo_id), it["tactic_code"], it["score"]))
                conn.commit()
        await asyncio.to_thread(_do)

    async def _search_prevention(self, tactic_code: Optional[str], level: Optional[str]):
        if tactic_code and level:
            return await _q_async("""
                SELECT id, tactic_code, title, summary_md, script_md, level
                FROM vp.prevention_module
                WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
                ORDER BY id ASC
            """, (tactic_code, level))
        elif tactic_code:
            return await _q_async("""
                SELECT id, tactic_code, title, summary_md, script_md, level
                FROM vp.prevention_module
                WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
                ORDER BY id ASC
            """, (tactic_code,))
        else:
            return await _q_async("""
                SELECT id, tactic_code, title, summary_md, script_md, level
                FROM vp.prevention_module
                WHERE is_active
                ORDER BY id ASC
            """)

    async def _search_attack(self, tactic_code: Optional[str], level: Optional[str]):
        if tactic_code and level:
            return await _q_async("""
                SELECT id, tactic_code, title, playbook_md, cues_md, level
                FROM vp.attack_module
                WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s AND level=%s
                ORDER BY id ASC
            """, (tactic_code, level))
        elif tactic_code:
            return await _q_async("""
                SELECT id, tactic_code, title, playbook_md, cues_md, level
                FROM vp.attack_module
                WHERE is_active AND tactic_code IS NOT DISTINCT FROM %s
                ORDER BY id ASC
            """, (tactic_code,))
        else:
            return await _q_async("""
                SELECT id, tactic_code, title, playbook_md, cues_md, level
                FROM vp.attack_module
                WHERE is_active
                ORDER BY id ASC
            """)

    async def _assign_guidance(self, convo_id: str, target_role: str, module_table: str, module_id: int, notes: str):
        # NOTE: 아직 스키마에 case_uuid가 없을 수 있으므로, UUID면 우선 스킵/감사로그만 남김
        if _looks_like_uuid(convo_id):
            await self._audit("guidance.assign.skip_uuid", {
                "case_uuid": convo_id, "target_role": target_role,
                "module_table": module_table, "module_id": module_id, "notes": notes
            })
            return
        await _q_async("""
            INSERT INTO vp.guidance_assignment (convo_id, target_role, module_table, module_id, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (int(convo_id), target_role, module_table, module_id, notes))

    async def _audit(self, action: str, detail: Dict[str, Any]):
        await _q_async("""
            INSERT INTO vp.audit_log (who, action, detail)
            VALUES (%s,%s,%s)
        """, ("orchestrator", action, json.dumps(detail, ensure_ascii=False)))

    def _infer_is_phished_from_logs(self, logs: List[Dict[str, Any]]) -> bool:
        victim_text = " ".join([x.get("content","") for x in logs if x.get("role") in ("victim","피해자")]).lower()
        pos = any(k in victim_text for k in ["보낼게", "입금", "이체", "송금", "보내줄게", "결제할게"])
        neg = any(k in victim_text for k in ["신고", "경찰", "못 도와", "안 보내", "의심", "사기", "보이스피싱"])
        return True if pos and not neg else False

    async def run_once(
        self,
        convo_id: str,
        level: str = "basic",
        victim_id: Optional[int] = None,
        attacker_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        outcome = await self._get_outcome(convo_id)
        is_phished = bool((outcome or {}).get("is_phished"))

        tactics = await self._get_tactics(convo_id)
        if not tactics:
            row = await self._get_logs(convo_id)
            transcript = (row or {}).get("transcript", "") or ""
            tagged = [{"tactic_code": code, "score": float(score)} for code, score in rule_tag(transcript)]
            await self._upsert_tactics(convo_id, tagged)
            tactics = tagged

        tactic_code = (tactics[0]["tactic_code"] if tactics else "generic")

        module = None
        target = None
        message = None

        if is_phished:
            items = await self._search_prevention(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = await self._search_prevention("generic", level) or []
            module = items[0] if items else None
            if module:
                logs_row = await self._get_logs(convo_id)
                transcript_preview = (logs_row or {}).get("transcript","")[:300]
                prompt = build_victim_action_guidelines(
                    tactic_code=tactic_code,
                    summary_md=module.get("summary_md",""),
                    script_md=module.get("script_md",""),
                    transcript_preview=transcript_preview,
                    is_phished=True,
                )
                message = await self.llm(prompt)
                await self._assign_guidance(convo_id, "VICTIM", "prevention", module["id"], "auto: victim education after phishing success")
            target = "VICTIM"
        else:
            items = await self._search_attack(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = await self._search_attack("generic", level) or []
            module = items[0] if items else None
            if module:
                logs_row = await self._get_logs(convo_id)
                transcript_preview = (logs_row or {}).get("transcript","")[:300]
                prompt = build_attacker_action_guidelines(
                    tactic_code=tactic_code,
                    playbook_md=module.get("playbook_md",""),
                    cues_md=module.get("cues_md",""),
                    transcript_preview=(await self._get_logs(convo_id) or {}).get("transcript","")[:300],
                )
                message = await self.llm(prompt)
                await self._assign_guidance(convo_id, "ATTACKER", "attack", module["id"], "auto: attacker playbook after phishing failure")
            target = "ATTACKER"

        await self._audit("orchestrate", {
            "convo_id": convo_id,
            "is_phished": is_phished,
            "tactic_code": tactic_code,
            "target": target,
            "module_used": (module or {}).get("id"),
        })

        return {
            "convo_id": convo_id,
            "is_phished": is_phished,
            "tactic_code": tactic_code,
            "target": target,
            "module": module,
            "message_for_target": message,
        }

    async def run_from_json(self, payload: dict, level: str = "basic", is_phished: Optional[bool] = None, verbose: bool = False) -> Dict[str, Any]:
        """
        시뮬레이터 JSON을 직접 받아 처리. DB 저장 없이: 전술 추정 → 모듈 선택 → LLM 메시지 생성
        """
        logs = payload.get("logs") or []
        lines = []
        for item in logs:
            role = (item.get("role") or "").strip()
            content = (item.get("content") or "").strip()
            if content:
                lines.append(f"{role.upper()}: {content}")
        transcript = "\n".join(lines)

        if is_phished is None:
            is_phished = self._infer_is_phished_from_logs(logs)

        tagged = [{"tactic_code": code, "score": float(score)} for code, score in rule_tag(transcript)]
        tactic_code = (tagged[0]["tactic_code"] if tagged else "generic")

        message = None
        module = None
        if is_phished:
            items = await self._search_prevention(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = await self._search_prevention("generic", level) or []
            module = items[0] if items else None
            if module:
                prompt = build_victim_action_guidelines(
                    tactic_code=tactic_code,
                    summary_md=module.get("summary_md",""),
                    script_md=module.get("script_md",""),
                    transcript_preview=transcript[:300],
                    is_phished=True,
                )
                message = await self.llm(prompt)
            target = "VICTIM"
        else:
            items = await self._search_attack(tactic_code, level) or []
            if not items and tactic_code != "generic":
                items = await self._search_attack("generic", level) or []
            module = items[0] if items else None
            if module:
                prompt = build_attacker_action_guidelines(
                    tactic_code=tactic_code,
                    playbook_md=module.get("playbook_md",""),
                    cues_md=module.get("cues_md",""),
                    transcript_preview=transcript[:300],
                )
                message = await self.llm(prompt)
            target = "ATTACKER"

        return {
            "source": "json",
            "is_phished": is_phished,
            "tactic_candidates": tagged,
            "tactic_code": tactic_code,
            "target": target,
            "module": module,
            "message_for_target": message,
            "verbose": verbose,
        }
