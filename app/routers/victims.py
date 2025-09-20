# routers/victim.py
import re
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.utils.deps import get_db
from app.db import models as m
from app.schemas.victim import (
    VictimCreate,
    VictimOut,
    VictimIntakeSimple,  # ← 직접 사용
)

router = APIRouter(tags=["victims"])

# ------------------------------------------------------------------
# OCEAN 순서/처리 규칙
# - 프론트 ocean_levels 순서: [개방성, 성실성, 외향성, 친화성, 신경성]
# - 각 값은 "높음"/"낮음"으로 온다고 가정
# - vulnerability_notes: 한 줄 생성
# ------------------------------------------------------------------
OCEAN_ORDER = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
LEVEL_CONV = {"높음": "높음", "낮음": "낮음"}

SAFE_CONDITIONS = {
    "neuroticism": "낮음",
    "openness": "높음",
    "agreeableness": "높음",
    "conscientiousness": "높음",
}
# SAFE_CONDITIONS와 일치하지 않으면 취약군으로 분류

def map_ocean_by_order(levels: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for i, trait in enumerate(OCEAN_ORDER):
        if i < len(levels):
            lv_raw = (levels[i] or "").strip()
            out[trait] = LEVEL_CONV.get(lv_raw, lv_raw)
    return out

def _trait_label_kr(trait_key: str) -> str:
    return {
        "openness": "개방성",
        "conscientiousness": "성실성",
        "extraversion": "외향성",
        "agreeableness": "친화성",
        "neuroticism": "신경성",
    }.get(trait_key, trait_key)

def _level_stem(level_text: str) -> str:
    if level_text.startswith("높"):
        return "높"
    if level_text.startswith("낮"):
        return "낮"
    return level_text[:1] if level_text else ""

def make_vulnerability_note_one_line(ocean: Dict[str, str]) -> str:
    safe_traits: List[tuple[str, str]] = []
    risk_traits: List[tuple[str, str]] = []

    for trait, val in ocean.items():
        label = _trait_label_kr(trait)
        if SAFE_CONDITIONS.get(trait) == val:
            safe_traits.append((label, val))
        else:
            risk_traits.append((label, val))

    def join_clauses(pairs: List[tuple[str, str]]) -> str:
        if not pairs:
            return ""
        parts: List[str] = []
        for i, (lab, v) in enumerate(pairs):
            stem = _level_stem(v)
            ending = "아" if i == len(pairs) - 1 else "고"
            parts.append(f"{lab}이 {stem}{ending}")
        return " ".join(parts)

    safe_text = join_clauses(safe_traits)
    risk_text = join_clauses(risk_traits)

    if safe_text and risk_text:
        return f"{safe_text} 보이스피싱에 안전한 면이 있지만 {risk_text} 보이스피싱에 취약한 면도 있다".strip()
    if safe_text:
        return f"{safe_text} 보이스피싱에 안전한 면이 있다".strip()
    if risk_text:
        return f"{risk_text} 보이스피싱에 취약한 면이 있다".strip()
    return ""

# ------------------------------------------------------------------
# 간소 입력 엔드포인트
# ------------------------------------------------------------------
@router.post("/make/victims/", response_model=VictimOut)
def create_victim_from_simple(payload: VictimIntakeSimple, db: Session = Depends(get_db)):
    """
    - checklist_lines: 체크된 문장만 배열로 전달 → 그대로 comparative_notes에 저장
    - ocean_levels: ["높음","낮음","..."] 5개 (개방성→성실성→외향성→친화성→신경성)
    """
    # meta
    age_val: Any = payload.age
    if age_val is not None:
        mnum = re.search(r"\d{1,3}", str(age_val))
        age_val = int(mnum.group()) if mnum else age_val

    meta = {
        "age": age_val,
        "education": payload.education,
        "gender": payload.gender,
        "address": payload.address,
    }

    # knowledge
    comparative_notes = [line.strip() for line in (payload.checklist_lines or []) if line and line.strip()]
    knowledge = {"comparative_notes": comparative_notes, "competencies": []}

    # traits
    ocean = map_ocean_by_order(payload.ocean_levels or [])
    if len(ocean) != 5:
        raise HTTPException(
            status_code=422,
            detail="ocean_levels는 5개(개방성→성실성→외향성→친화성→신경성)로 전달되어야 합니다.",
        )
    vulnerability_note = make_vulnerability_note_one_line(ocean)
    traits = {"ocean": ocean, "vulnerability_notes": [vulnerability_note] if vulnerability_note else []}

    # 저장
    obj = m.Victim(
        name=payload.name,
        meta=meta,
        knowledge=knowledge,
        traits=traits,
        photo_path=payload.photo_path,
        is_active=payload.is_active,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

# ------------------------------------------------------------------
# 기존 생성/조회
# ------------------------------------------------------------------
@router.post("/victims/", response_model=VictimOut)
def create_victim(payload: VictimCreate, db: Session = Depends(get_db)):
    obj = m.Victim(
        name=payload.name,
        meta=payload.meta,
        knowledge=payload.knowledge,
        traits=payload.traits,
        photo_path=getattr(payload, "photo_path", None),
        is_active=getattr(payload, "is_active", True),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/victims/", response_model=List[VictimOut])
def get_victims(db: Session = Depends(get_db)):
    return db.query(m.Victim).all()

@router.get("/victims/{victim_id}", response_model=VictimOut)
def get_victim(victim_id: int, db: Session = Depends(get_db)):
    obj = db.get(m.Victim, victim_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Victim not found")
    return obj
