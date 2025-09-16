# vp_mcp/mcp_server/server.py
from __future__ import annotations
import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from mcp.server.fastmcp import FastMCP
from .db.base import init_db

# (A) 툴 등록 방식: 헬퍼가 있으면 사용, 없으면 fallback
try:
    from .tools.simulate_dialogue import register_simulate_dialogue_tool_fastmcp
    USE_HELPER = True
except ImportError:
    # 헬퍼가 없다면, 순수 구현/스키마로 직접 등록
    from .tools.simulate_dialogue import simulate_dialogue_impl
    from .schemas import SimulationInput
    USE_HELPER = False


def build_app():
    # 1) env 로드 + DB 초기화
    load_dotenv()
    init_db()

    # 2) FastMCP 인스턴스
    mcp = FastMCP("vp-mcp-sim")
    print(">> MCP: registering tools...")

    if USE_HELPER:
        # 권장: FastMCP 전용 등록 헬퍼
        register_simulate_dialogue_tool_fastmcp(mcp)
    else:
        # Fallback: dict → pydantic 변환 후 구현 호출
        @mcp.tool(
            name="sim.simulate_dialogue",
            description="공격자/피해자 LLM 교대턴 시뮬레이션 실행 후 로그 저장"
        )
        async def simulate_dialogue(arguments: dict) -> dict:
            model = SimulationInput.model_validate(arguments)
            return simulate_dialogue_impl(model)

    print(">> MCP: tools registered OK")

    # 3) FastAPI 앱 구성
    app = FastAPI()

    # ⚠️ /mcp → /mcp/ 로의 자동 리다이렉트를 끔 (307 방지)
    # FastAPI는 기본으로 슬래시 리다이렉트를 켭니다.
    # streamable HTTP 엔드포인트는 정확히 '/mcp' 경로에서만 받게 해야 하므로 끕니다.
    app.router.redirect_slashes = False

    @app.get("/")
    def info():
        return {"name": "vp-mcp-sim", "status": "ok", "endpoint": "/mcp"}

    # 4) FastMCP ASGI 앱 마운트
    mount_target = getattr(mcp, "app", None)
    if mount_target is None:
        # 일부 버전에선 streamable_http_app()만 제공됨
        mount_target = mcp.streamable_http_app()

    # ✅ '/mcp'에 정확히 한 번만 마운트 (중복 mount 금지)
    app.mount("/mcp", mount_target)

    return app


app = build_app()

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "5177"))
    uvicorn.run("vp_mcp.mcp_server.server:app", host=host, port=port, reload=True)
