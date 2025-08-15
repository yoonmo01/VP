from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.deps import get_db
from app.db import models as m
from app.schemas.offender import OffenderCreate, OffenderOut

router = APIRouter(prefix="/offenders", tags=["offenders"])

@router.post("/", response_model=OffenderOut)
def create_offender(payload: OffenderCreate, db: Session = Depends(get_db)):
    obj = m.PhishingOffender(name=payload.name, profile=payload.profile)
    db.add(obj)
    db.commit(); db.refresh(obj)
    return obj

@router.get("/{offender_id}", response_model=OffenderOut)
def get_offender(offender_id: int, db: Session = Depends(get_db)):
    return db.get(m.PhishingOffender, offender_id)