# app/routers/personalized.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app.db.session import get_db
from app.db import models as m
from app.schemas.personalized import PersonalizedOut

router = APIRouter(prefix="/personalized", tags=["personalized"])


@router.get("/{pp_id}", response_model=PersonalizedOut)
def get_personalized(pp_id: UUID, db: Session = Depends(get_db)):
    row = db.get(m.PersonalizedPrevention, pp_id)
    if not row:
        raise HTTPException(status_code=404,
                            detail="personalized prevention not found")
    return row


@router.get("/by-case/{case_id}", response_model=List[PersonalizedOut])
def list_personalized_by_case(
        case_id: UUID,
        latest: bool = Query(True, description="최신 1건만 반환"),
        db: Session = Depends(get_db),
):
    q = (db.query(m.PersonalizedPrevention).filter(
        m.PersonalizedPrevention.case_id == case_id).order_by(
            m.PersonalizedPrevention.run.desc().nullslast(),
            m.PersonalizedPrevention.created_at.desc(),
        ))
    rows = q.limit(1).all() if latest else q.all()
    return rows
