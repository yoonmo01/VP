# orchestrator/main.py
import asyncio, os, json
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import Json as PgJson
from .dev_router import router as dev_router

from .rules import rule_tag_kor, join_transcript_from_logs, judge_phishing_from_json
from .prompts import build_victim_action_guidelines, build_attacker_action_guidelines
from .llm_providers import get_llm
import httpx
from dotenv import load_dotenv

load_dotenv()
DSN = os.getenv("DATABASE_URL", "")
# SQLAlchemy-style URL을 psycopg2가 이해하는 형태로 보정
if DSN.startswith("postgresql+psycopg://"):
    DSN = DSN.replace("postgresql+psycopg://", "postgresql://", 1)
if DSN.startswith("postgresql+psycopg2://"):
    DSN = DSN.replace("postgresql+psycopg2://", "postgresql://", 1)
if not DSN:
    raise RuntimeError("DATABASE_URL이 비어 있습니다. 예) postgresql://user:pass@localhost:5432/voicephish")

app = FastAPI(title="Voicephish Orchestrator (no-MCP)")
app.include_router(dev_router)  

llm = get_llm()

def dbq(sql: str, params=(), one=False):
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description:
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
            data = [dict(zip(cols, r)) for r in rows]
            return (data[0] if one else data)
        else:
            conn.commit()
            return {"ok": True}

class IngestReq(BaseModel):
    batch_id: Optional[str] = None         # 없으면 새 배치 생성
    payload: Dict[str, Any]                # 네가 준 JSON 그대로
    level: str = "basic" 

class FinalizeReq(BaseModel):
    topk: int = 5   # 최근 N회로 플랜 생성

def _ensure_batch(req: IngestReq) -> str:
    if req.batch_id:
        return req.batch_id
    # 새 배치 생성(피해자/공격자/시나리오 스냅샷을 참고)
    p = req.payload
    victim_ref = json.dumps(p.get("victim", {}), ensure_ascii=False)
    offender_ref = json.dumps(p.get("offender", {}), ensure_ascii=False)
    scenario_ref = json.dumps(p.get("scenario", {}), ensure_ascii=False)
    row = dbq("""
        INSERT INTO vp.sim_batch(label, victim_ref, offender_ref, scenario_ref, intended_runs)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
    """, ("auto", victim_ref, offender_ref, scenario_ref, 5), one=True)
    return row["id"]

def _pick_modules(tactic_code: str, is_phished: bool, level: str="basic"):
    if is_phished:
        # 피해자 교육 모듈
        rows = dbq("""
            SELECT id, tactic_code, title, summary_md, script_md
            FROM vp.prevention_module
            WHERE is_active
              AND (level = %s OR %s IS NULL)
              AND (tactic_code IS NULL OR tactic_code = %s OR %s IS NULL)
            ORDER BY (CASE WHEN tactic_code=%s THEN 0 ELSE 1 END), id ASC
            LIMIT 1
        """, (level, level, tactic_code, tactic_code, tactic_code))
        return ("VICTIM", rows[0] if rows else None)
    else:
        # 공격자(연구용 가상) 모듈
        rows = dbq("""
            SELECT id, tactic_code, title, playbook_md, cues_md
            FROM vp.attack_module
            WHERE is_active
              AND (level = %s OR %s IS NULL)
              AND (tactic_code IS NULL OR tactic_code = %s OR %s IS NULL)
            ORDER BY (CASE WHEN tactic_code=%s THEN 0 ELSE 1 END), id ASC
            LIMIT 1
        """, (level, level, tactic_code, tactic_code, tactic_code))
        return ("ATTACKER", rows[0] if rows else None)
    

class LoopReq(BaseModel):
    payload: Dict[str, Any]            # 첫 라운드 JSON
    max_rounds: int = 5
    level: str = "basic"
    sim_endpoint: Optional[str] = None

async def _call_simulator(payload: dict, override_endpoint: Optional[str] = None) -> dict:
    sim_url = override_endpoint or os.getenv("SIM_ENDPOINT")
    if not sim_url:
        raise HTTPException(500, "SIM_ENDPOINT 환경변수가 필요합니다. 예) http://localhost:8001")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{sim_url}/tick", json=payload)
        r.raise_for_status()
        return r.json()

@app.post("/loop", summary="JSON 1건으로 시작해 최대 N회 자동 반복 후 플랜 생성/반환")
async def loop(req: LoopReq):
    try:
        batch_id = _ensure_batch(IngestReq(batch_id=None, payload=req.payload))
        verbose = []
        current = req.payload
        offender_id = req.payload.get("offender_id")
        victim_id = req.payload.get("victim_id")
        case_scenario = req.payload.get("case_scenario") or req.payload.get("scenario")

        for r in range(req.max_rounds):
            res = await ingest(IngestReq(batch_id=batch_id, payload=current, level=req.level))  # ✅ level 전달
            # 최근 인테이크 1건에 의사결정 메모 저장(스키마 ALTER 전이면 생략 가능)
            try:
                dbq("""
                    UPDATE vp.sim_run_intake
                    SET raw_json = raw_json || jsonb_build_object('last_decision', %s::jsonb)
                    WHERE batch_id=%s
                    ORDER BY id DESC LIMIT 1
                """, (json.dumps({
                    "round": r+1,
                    "target": res["target"],
                    "module_used": res["module_used"],
                    "tactic_code": res["tactic_code"]
                }, ensure_ascii=False), batch_id))
            except Exception:
                pass

            verbose.append({
                "round": r+1,
                "is_phished": res["is_phished"],
                "tactic_code": res["tactic_code"],
                "target": res["target"],
                "module_used": res["module_used"],
                "message_for_target": (res["message_for_target"] or "")[:400]
            })

            # 시뮬레이터 호출 → 다음 라운드 JSON
            nxt = await _call_simulator({
                "case_id": current.get("case_id"),
                "offender_id": offender_id,
                "victim_id": victim_id,
                "case_scenario": case_scenario,
                "inject": {
                    "target": res["target"],
                    "message": res["message_for_target"] or ""
                },
                "meta": {
                    "round": r + 1,
                    "end": (r + 1) == req.max_rounds   # 마지막 라운드 표시
                }
            }, override_endpoint=req.sim_endpoint)
            if not nxt or not nxt.get("logs"):
                break
            if nxt.get("case_id"):
                latest_case_id = nxt["case_id"]
            current = nxt

        plan = await finalize(batch_id, FinalizeReq(topk=req.max_rounds))
        return {
            "ok": True,
            "batch_id": batch_id,
            "verbose": verbose,
            "personalized_plan": plan["plan_md"],
            "sim_case_id": latest_case_id
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/ingest", summary="시뮬 1회 로그 JSON 인테이크 + 즉시 가이던스 반환")
async def ingest(req: IngestReq):
    try:
        batch_id = _ensure_batch(req)
        p = req.payload

        # 판정: payload에 명시가 없으면 휴리스틱
        is_phished = p.get("outcome", {}).get("is_phished")
        if is_phished is None:
            is_phished = judge_phishing_from_json(p)

        # 전술 코드 추정(간단)
        transcript = join_transcript_from_logs(p.get("logs", []))
        tactic_code = rule_tag_kor(transcript)[0][0]

        # DB 저장
        dbq("""
            INSERT INTO vp.sim_run_intake(batch_id, case_id, raw_json, is_phished, tactic_code)
            VALUES (%s, %s, %s, %s, %s)
        """, (batch_id, p.get("case_id"), PgJson(p), is_phished, tactic_code))

        # 모듈 선택 & LLM으로 메시지 생성
        target, module = _pick_modules(tactic_code, is_phished, level=req.level)  # ✅ level 반영
        message = None
        if module:
            if target == "VICTIM":
                # 대화 프리뷰 300자 정도 잘라 전달
                prompt = build_victim_action_guidelines(
                    tactic_code=tactic_code,
                    summary_md=module.get("summary_md",""),
                    script_md=module.get("script_md",""),
                    transcript_preview=transcript[:300],
                    is_phished=True,
                )
                message = await llm(prompt)

                # 거절/정책 응답 감지 시 1회 재시도
                refuse_markers = ["도와드릴 수 없습니다", "정책상", "refuse", "cannot help"]
                if any(m in (message or "") for m in refuse_markers):
                    retry_prompt = prompt + """
        [주의/재시도]
        - 거절 없이, 정책 준수 범위에서 '추상적 행동 지침(Do/Don't)'만 제공.
        - 고유명사/식별자/URL/전화번호/앱명/기관명 금지. 신고·확인은 '공식 사이트/대표번호를 직접 검색해 이용'으로만 표현.
        """
                    message = await llm(retry_prompt)

            else:
                # 대화 프리뷰를 300자 정도만 잘라서 컨텍스트로 제공
                prompt = build_attacker_action_guidelines(
                    tactic_code=tactic_code,
                    playbook_md=module.get("playbook_md",""),
                    cues_md=module.get("cues_md",""),
                    transcript_preview=transcript[:300],
                )
                message = await llm(prompt)

                refuse_markers = ["도와드릴 수 없습니다", "정책상", "refuse", "cannot help"]
                if any(m in (message or "") for m in refuse_markers):
                    retry_prompt = prompt + """
        [주의/재시도]
        - 거절 없이, 정책 준수 범위에서 '추상적 행동 지침(Do/Don't)'만 제공.
        - 실세계 식별정보·구체 실행 단계·우회요령 금지. [가상-토큰]만 사용.
        """
                    message = await llm(retry_prompt)

        # 응답(시뮬레이터가 다음 라운드 시스템 프롬프트로 주입)
        return {
            "batch_id": batch_id,
            "case_id": p.get("case_id"),
            "is_phished": is_phished,
            "tactic_code": tactic_code,
            "target": target,                         # "VICTIM" or "ATTACKER"
            "message_for_target": message or "",      # 주입 텍스트
            "module_used": (module or {}).get("id"),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/batch/{batch_id}/finalize", summary="최근 N회 기반 맞춤형 예방 대책 생성/저장")
async def finalize(batch_id: str, body: FinalizeReq):
    try:
        # 최근 N회 러닝 수집
        runs = dbq("""
            SELECT id, raw_json, is_phished, tactic_code, created_at
            FROM vp.sim_run_intake
            WHERE batch_id=%s
            ORDER BY id DESC
            LIMIT %s
        """, (batch_id, body.topk))

        if not runs:
            raise HTTPException(404, "해당 배치에 러닝 데이터가 없습니다.")

        # 컨텍스트 조립
        # - 피해자/공격자/시나리오 스냅샷은 배치에서 가져옴
        batch = dbq("SELECT * FROM vp.sim_batch WHERE id=%s", (batch_id,), one=True)
        victim_ref = batch.get("victim_ref") or {}
        offender_ref = batch.get("offender_ref") or {}
        scenario_ref = batch.get("scenario_ref") or {}

        # 관찰 요약(간단): 성공/실패 카운트, 키워드, 취약요인
        total = len(runs)
        success = sum(1 for r in runs if r.get("is_phished"))
        fail = total - success
        tactics = {}
        for r in runs:
            t = r.get("tactic_code") or "generic"
            tactics[t] = tactics.get(t, 0) + 1

        # 맞춤형 예방 대책 프롬프트(간단)
        prompt = f"""
당신은 보이스피싱 예방 코치입니다. 사용자는 피해자 프로필과 최근 {total}회 시뮬레이션 로그 요약을 제공합니다.
이 정보를 바탕으로 '맞춤형 예방 대책'을 한국어 Markdown으로 작성하세요.

[피해자]
{json.dumps(victim_ref, ensure_ascii=False, indent=2)}

[공격 시나리오 요약]
{json.dumps(scenario_ref, ensure_ascii=False, indent=2)}

[최근 러닝 요약]
- 총 {total}회: 성공(피해) {success} / 실패(차단) {fail}
- 전술 분포: {json.dumps(tactics, ensure_ascii=False)}

요구사항:
1) 관찰 인사이트(취약/강점, 오해 포인트, 감정 트리거) 6~8줄
2) 맞춤형 대응 스크립트(상황별 3가지: 입금 요구/링크·앱/기관 사칭) 각 3~4문장
3) 체크리스트 8줄 (행동-근거 페어)
4) 연습 과제 3개(역할극/셀프 체크)
5) 신고/확인은 '공식 대표번호를 직접 검색해 이용' 표현만 사용. 현실 계좌·전화·링크 금지.
"""
        plan_md = await llm(prompt)
        insights_md = f"- 총 {total}회 중 피해 {success}회, 차단 {fail}회\n- 전술 태그 분포: {', '.join([f'{k}:{v}' for k,v in tactics.items()])}\n- 피해자 요약: 성향/지식 참고하여 행동 유도 포인트를 설계"

        # 저장
        row = dbq("""
            INSERT INTO vp.personalized_plan(batch_id, victim_ref, offender_ref, scenario_ref, insights_md, plan_md, sources)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            batch_id,
            json.dumps(victim_ref, ensure_ascii=False),
            json.dumps(offender_ref, ensure_ascii=False),
            json.dumps(scenario_ref, ensure_ascii=False),
            insights_md,
            plan_md,
            json.dumps([], ensure_ascii=False),
        ), one=True)

        return {"plan_id": row["id"], "batch_id": batch_id, "plan_md": plan_md}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/batch/{batch_id}/plan", summary="맞춤형 예방 대책 조회")
def get_plan(batch_id: str):
    row = dbq("""SELECT * FROM vp.personalized_plan WHERE batch_id=%s ORDER BY id DESC LIMIT 1""", (batch_id,), one=True)
    if not row:
        raise HTTPException(404, "플랜이 없습니다.")
    return row
