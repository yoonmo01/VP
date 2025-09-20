# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# ✅ 모델 모듈 import: 테이블 생성시에 커스텀 모델까지 포함되도록
from app.db import models as _models  # 기존 카탈로그
# from app.db import models_custom as _models_custom  # 커스텀 Victim/Scenario

# ✅ 라우터들
from app.routers import health, offenders, victims, conversations, admin_cases
from app.routers import conversations_read, simulator as simulator_router
from app.routers import agent as agent_router
from app.routers.personalized import router as personalized_router

# TTS
from app.routers.tts import router as tts_router

# ✅ 커스텀 API 라우터 추가
from app.routers.custom import router as custom
# from app.db.models import custom
# ─────────────────────────────────────────────────────────────
# DB 스키마 생성 (모델 import 이후에 호출)
# ─────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 필요시 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ✅ APIRouter 등록 (이미 APIRouter 객체이므로 .router 붙이지 않음)
app.include_router(health, prefix=settings.API_PREFIX)
app.include_router(offenders, prefix=settings.API_PREFIX)
app.include_router(victims, prefix=settings.API_PREFIX)
app.include_router(conversations, prefix=settings.API_PREFIX)
app.include_router(admin_cases, prefix=settings.API_PREFIX)
app.include_router(personalized_router, prefix="/api")  # 기존 유지

# 이 3개는 모듈이라 .router 필요
app.include_router(conversations_read.router, prefix=settings.API_PREFIX)
app.include_router(simulator_router.router, prefix=settings.API_PREFIX)
app.include_router(agent_router.router, prefix=settings.API_PREFIX)

# ✅ 커스텀 라우터 등록: /api/custom/*
app.include_router(custom, prefix=settings.API_PREFIX)

# ✅ TTS 라우터 등록
app.include_router(tts_router, prefix=settings.API_PREFIX)

# ─────────────────────────────────────────────────────────────
# Root
# ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "env": settings.APP_ENV, "message": "See /docs"}
