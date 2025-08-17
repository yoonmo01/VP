from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routers import health, offenders, victims, conversations, admin_cases, conversations_read  # ✅ checklists 제거

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(o) for o in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 정적 파일 서빙 (/static -> app/static)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health,         prefix=settings.API_PREFIX)
app.include_router(offenders, prefix=settings.API_PREFIX)
app.include_router(victims,        prefix=settings.API_PREFIX)
app.include_router(conversations,  prefix=settings.API_PREFIX)
app.include_router(admin_cases,    prefix=settings.API_PREFIX)
app.include_router(conversations_read.router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "env": settings.APP_ENV}
