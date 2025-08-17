#app/routers/victims.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.deps import get_db
from app.db import models as m
from app.schemas.victim import VictimCreate, VictimOut
from typing import List

router = APIRouter(tags=["victims"])


@router.post("/victims", response_model=VictimOut)
def create_victim(payload: VictimCreate, db: Session = Depends(get_db)):
    obj = m.Victim(name=payload.name,
                   meta=payload.meta,
                   knowledge=payload.knowledge,
                   traits=payload.traits)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/victims", response_model=List[VictimOut])
def get_victims(db: Session = Depends(get_db)):
    return db.query(m.Victim).all()


@router.get("/victims/{victim_id}", response_model=VictimOut)
def get_victim(victim_id: int, db: Session = Depends(get_db)):
    return db.get(m.Victim, victim_id)
