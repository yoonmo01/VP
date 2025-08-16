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

OFFENDERS_JSON = SEEDS_DIR / "offenders.json"
VICTIMS_JSON   = SEEDS_DIR / "victims.json"
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

        # 2) 피싱범 insert (이름 중복 방지: name 기준 존재 체크)
        offender_ids = []
        for o in offenders:
            name = o.get("name")
            existing = db.query(m.PhishingOffender).filter(m.PhishingOffender.name == name).first()
            if existing:
                offender_ids.append(existing.id)
                continue
            obj = m.PhishingOffender(
                name=name,
                type=o.get("type"),
                profile=o.get("profile", {}),
                is_active=bool(o.get("is_active", True)),
            )
            db.add(obj)
            db.flush()  # id 확보
            offender_ids.append(obj.id)

        # 3) 피해자 insert (이름 중복 방지: name 기준 존재 체크)
        victim_ids = []
        for v in victims:
            name = v.get("name")
            existing = db.query(m.Victim).filter(m.Victim.name == name).first()
            if existing:
                victim_ids.append(existing.id)
                continue
            obj = m.Victim(
                name=name,
                meta=v.get("meta", {}),
                knowledge=v.get("knowledge", {}),
                traits=v.get("traits", {}),
                is_active=bool(v.get("is_active", True)),
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
