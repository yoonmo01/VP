# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# ✅ __init__.py 덕분에 라우터들을 직접 가져올 수 있음
from app.routers import health, offenders, victims, conversations, admin_cases
from app.routers import conversations_read, simulator as simulator_router
from app.routers import agent as agent_router
from app.routers.personalized import router as personalized_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",  # ← 원래처럼 /docs
    openapi_url="/openapi.json",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ✅ 여기서 .router 붙이지 말 것 (이미 APIRouter 객체임)
app.include_router(health, prefix=settings.API_PREFIX)
app.include_router(offenders, prefix=settings.API_PREFIX)
app.include_router(victims, prefix=settings.API_PREFIX)
app.include_router(conversations, prefix=settings.API_PREFIX)
app.include_router(admin_cases, prefix=settings.API_PREFIX)
app.include_router(personalized_router, prefix="/api")

# 이 3 개는 아직 모듈이므로 .router 필요
app.include_router(conversations_read.router, prefix=settings.API_PREFIX)
app.include_router(simulator_router.router, prefix=settings.API_PREFIX)
app.include_router(agent_router.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "env": settings.APP_ENV}


@app.get("/")
def index():
    return {"ok": True, "message": "See /docs"}


# #------------------------logging----------------------------

# setup_logging()  # 반드시 FastAPI 인스턴스 만들기 전에 한 번 호출
# log = get_logger(__name__)

# app = FastAPI(
#     title="Anti-Phishing Simulator",
#     docs_url="/docs",
#     redoc_url="/redoc",
#     openapi_url="/openapi.json",
# )

# @app.middleware("http")
# async def bind_request_context(request: Request, call_next):
#     # request-id
#     rid = request.headers.get("x-request-id")
#     rid = set_request_id(rid)

#     # verbose: 헤더(X-Verbose) 또는 쿼리(verbose)
#     v = request.headers.get("x-verbose")
#     if v is None:
#         v = request.query_params.get("verbose")
#     verbose = str(v).lower() in ("1", "true", "yes", "on")
#     set_request_verbose(verbose)

#     log.info(f"--> {request.method} {request.url.path}?{request.url.query}")
#     if verbose:
#         log.debug(f"[VERBOSE ON] headers={dict(request.headers)}")

#     try:
#         response = await call_next(request)
#     finally:
#         log.info(
#             f"<-- {request.method} {request.url.path} (rid={rid}) verbose={verbose}"
#         )

#     response.headers["x-request-id"] = rid
#     response.headers["x-verbose"] = "true" if verbose else "false"
#     return response
