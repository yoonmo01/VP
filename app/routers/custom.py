# app/api/routes_custom.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import CustomVictim, CustomScenario
from app.schemas.custom import (
    CustomVictimCreate, CustomVictimOut,
    CustomScenarioCreate, CustomScenarioOut,
    ResolveIn, ResolveOut
)
from app.services.custom_steps import generate_steps_from_tavily

router = APIRouter(prefix="/custom", tags=["custom"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----- Victim -----
@router.post("/victims", response_model=CustomVictimOut, status_code=201)
def create_custom_victim(body: CustomVictimCreate, db: Session = Depends(get_db)):
    obj = CustomVictim(
        name=body.name.strip(),
        meta=body.meta or {},
        knowledge=body.knowledge or {},
        traits=body.traits or {},
        note=body.note,
        is_active=True,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return CustomVictimOut(
        id=obj.id, name=obj.name, meta=obj.meta, knowledge=obj.knowledge, traits=obj.traits, is_active=obj.is_active
    )

@router.get("/victims/{vid}", response_model=CustomVictimOut)
def get_custom_victim(vid: str, db: Session = Depends(get_db)):
    obj = db.get(CustomVictim, vid)
    if not obj or not obj.is_active:
        raise HTTPException(404, "custom victim not found")
    return CustomVictimOut(
        id=obj.id, name=obj.name, meta=obj.meta, knowledge=obj.knowledge, traits=obj.traits, is_active=obj.is_active
    )

# ----- Scenario -----
@router.post("/scenarios", response_model=CustomScenarioOut, status_code=201)
def create_custom_scenario(body: CustomScenarioCreate, db: Session = Depends(get_db)):
    purpose = (body.purpose or "").strip()
    if not purpose:
        raise HTTPException(422, "purpose is required")

    steps = body.steps
    source = None
    if not steps:
        if body.use_tavily:
            steps, source = generate_steps_from_tavily(
                purpose=purpose, k=body.k, query=body.tavily_query
            )
        else:
            # 최소 안전 디폴트(검색 미사용)
            steps = [
                f"{purpose}: 초기 접촉/명분 제시",
                "신뢰 형성 및 정보 파악",
                "핵심 요구 제시",
                "설득/압박",
                "금전/정보 전달 및 종료",
            ]

    obj = CustomScenario(
        purpose=purpose,
        steps=steps,
        source=source,          # tavily 메타 저장(선택)
        note=body.note,
        is_active=True,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return CustomScenarioOut(
        id=obj.id, purpose=obj.purpose, steps=obj.steps, source=obj.source, is_active=obj.is_active
    )

@router.get("/scenarios/{sid}", response_model=CustomScenarioOut)
def get_custom_scenario(sid: str, db: Session = Depends(get_db)):
    obj = db.get(CustomScenario, sid)
    if not obj or not obj.is_active:
        raise HTTPException(404, "custom scenario not found")
    return CustomScenarioOut(
        id=obj.id, purpose=obj.purpose, steps=obj.steps, source=obj.source, is_active=obj.is_active
    )

# ----- Resolve → 오케스트레이터 투입형(JSON 통일)
@router.post("/resolve", response_model=ResolveOut)
def resolve_custom(body: ResolveIn, db: Session = Depends(get_db)):
    vp = {"meta": {}, "knowledge": {}, "traits": {}}
    if body.custom_victim_id:
        v = db.get(CustomVictim, body.custom_victim_id)
        if not v or not v.is_active:
            raise HTTPException(404, "custom victim not found")
        vp = {"meta": v.meta or {}, "knowledge": v.knowledge or {}, "traits": v.traits or {}}

    sc = {"purpose": "", "steps": [], "source": None}
    if body.custom_scenario_id:
        s = db.get(CustomScenario, body.custom_scenario_id)
        if not s or not s.is_active:
            raise HTTPException(404, "custom scenario not found")
        sc = {"purpose": s.purpose, "steps": list(s.steps or []), "source": s.source}

    return ResolveOut(victim_profile=vp, scenario=sc)
