# vp_mcp/mcp_server/server.py
from __future__ import annotations
import os
import uvicorn
from dotenv import load_dotenv

from starlette.applications import Starlette
from starlette.routing import Mount
from fastapi import FastAPI

from mcp.server.fastmcp import FastMCP

from .db.base import init_db

# (A) 툴 등록 방식: 헬퍼가 있으면 사용, 없으면 fallback
try:
    from .tools.simulate_dialogue import register_simulate_dialogue_tool_fastmcp
    USE_HELPER = True
except ImportError:
    from .tools.simulate_dialogue import simulate_dialogue_impl
    from .schemas import SimulationInput
    USE_HELPER = False

def build_app():
    # env 로드 + DB 초기화
    load_dotenv()
    init_db()

    # FastMCP 인스턴스
    mcp = FastMCP("vp-mcp-sim")

    # (A-1) 권장: 툴 등록 헬퍼 사용
    if USE_HELPER:
        register_simulate_dialogue_tool_fastmcp(mcp)
    else:
        # (B) 직접 등록: dict → pydantic 모델 변환 후 구현 호출
        @mcp.tool(
            name="sim.simulate_dialogue",
            description="공격자/피해자 LLM 교대턴 시뮬레이션 실행 후 로그 반환 및 DB 저장",
        )
        def simulate_dialogue(arguments: dict) -> dict:
            # App에서 넘어온 payload(dict)를 SimulationInput으로 검증/변환
            model = SimulationInput.model_validate(arguments)
            return simulate_dialogue_impl(model)

    mount_target = getattr(mcp, "app", None)
    if mount_target is None:
        # 구버전(또는 일부 배포)에서는 streamable_http_app() 제공
        mount_target = mcp.streamable_http_app()

    root = FastAPI()

    @root.get("/")
    def info():
        return {"name": "vp-mcp-sim", "status": "ok", "endpoint": "/mcp"}

    app = Starlette(routes=[
        Mount("/mcp", app=mount_target),
        Mount("/", app=root),
    ])
    return app

app = build_app()

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "5177"))
    uvicorn.run("vp_mcp.mcp_server.server:app", host=host, port=port, reload=True)
