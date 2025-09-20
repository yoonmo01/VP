#app/routers/offenders.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.deps import get_db
from app.db import models as m
from app.schemas.offender import OffenderCreate, OffenderOut
from typing import List


router = APIRouter(tags=["offenders"])


@router.post("/make/offenders/", response_model=OffenderOut)
def create_offender(payload: OffenderCreate, db: Session = Depends(get_db)):
    profile: Dict[str, Any] = {
        "purpose": payload.purpose,
        "steps": payload.steps,
    }
    obj = m.PhishingOffender(
        name=payload.name,
        type=payload.type,
        profile=profile,   # ← JSONB에 자동 직렬화되어 저장됨
        # source는 저장 안 함
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/offenders/", response_model=List[OffenderOut])
def get_offenders(db: Session = Depends(get_db)):
    return db.query(m.PhishingOffender).all()


@router.get("/offenders/{offender_id}", response_model=OffenderOut)
def get_offender(offender_id: int, db: Session = Depends(get_db)):
    return db.get(m.PhishingOffender, offender_id)


@router.get("/offenders/by-type/{type_name}", response_model=List[OffenderOut])
def get_offenders_by_type(type_name: str, db: Session = Depends(get_db)):
    return (db.query(m.PhishingOffender).filter(
        m.PhishingOffender.type == type_name).order_by(
            m.PhishingOffender.id).all())
