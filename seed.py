# seed.py
import json
from pathlib import Path
from typing import Any

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db import models as m

from sqlalchemy import text
print("ENGINE_URL =", engine.url)

with engine.connect() as conn:
    row = conn.execute(text("select current_database(), current_user")).fetchone()
    print("DB CHECK:", row)

BASE_DIR = Path(__file__).parent
SEEDS_DIR = BASE_DIR / "seeds"

OFFENDERS_JSON = SEEDS_DIR / "offenders_v2.json"
VICTIMS_JSON   = SEEDS_DIR / "victims_v2.json"
SCENARIO_JSON  = SEEDS_DIR / "scenario.json"  # 옵션: 출력용

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def main() -> None:
    # 1) 테이블 생성 (없으면 생성)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        offenders = load_json(OFFENDERS_JSON) if OFFENDERS_JSON.exists() else []
        victims   = load_json(VICTIMS_JSON) if VICTIMS_JSON.exists() else []
        scenario  = load_json(SCENARIO_JSON) if SCENARIO_JSON.exists() else None

        # 2) 피싱범 upsert (이름 중복 방지: name 기준 존재 시 업데이트)
        offender_ids = []
        for o in offenders:
            name = (o.get("name") or "").strip()
            if not name:
                continue

            existing = db.query(m.PhishingOffender).filter(m.PhishingOffender.name == name).first()
            if existing:
                # 존재하면 업데이트
                existing.type      = o.get("type")
                existing.profile   = o.get("profile", {}) or {}
                existing.is_active = bool(o.get("is_active", True))
                existing.source    = o.get("source") or {}     # ✅ 출처 저장
                db.add(existing)
                db.flush()
                offender_ids.append(existing.id)
            else:
                # 없으면 생성
                obj = m.PhishingOffender(
                    name=name,
                    type=o.get("type"),
                    profile=o.get("profile", {}) or {},
                    is_active=bool(o.get("is_active", True)),
                    source=o.get("source") or {},              # ✅ 출처 저장
                )
                db.add(obj)
                db.flush()  # id 확보
                offender_ids.append(obj.id)

        # 3) 피해자 upsert (이름 중복 방지: name 기준)
        victim_ids = []
        for v in victims:
            name = (v.get("name") or "").strip()
            if not name:
                continue

            existing = db.query(m.Victim).filter(m.Victim.name == name).first()
            if existing:
                existing.meta       = v.get("meta", {}) or {}
                existing.knowledge  = v.get("knowledge", {}) or {}
                existing.traits     = v.get("traits", {}) or {}
                existing.is_active  = bool(v.get("is_active", True))
                existing.photo_path = v.get("photo_path")   # ✅ 추가
                db.add(existing)
                db.flush()
                victim_ids.append(existing.id)
            else:
                obj = m.Victim(
                    name=name,
                    meta=v.get("meta", {}) or {},
                    knowledge=v.get("knowledge", {}) or {},
                    traits=v.get("traits", {}) or {},
                    is_active=bool(v.get("is_active", True)),
                    photo_path=v.get("photo_path"),         # ✅ 추가
                )
                db.add(obj)
                db.flush()
                victim_ids.append(obj.id)

        db.commit()

        print({
            "offender_ids": offender_ids,
            "victim_ids": victim_ids,
            "scenario": scenario  # 시뮬 호출 때 그대로 사용 가능
        })

    finally:
        db.close()

if __name__ == "__main__":
    main()
