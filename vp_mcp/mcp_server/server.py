# VP/mcp_server/mcp_server/server.py
from starlette.applications import Starlette
from starlette.routing import Mount
import os
import uvicorn

from mcp.server.fastmcp import FastMCP   # ✅ Streamable HTTP용
from .db.base import init_db

# (A) 시뮬 도구 등록용 구현을 import
#    - 아래 두 가지 중 하나를 택해:
# 1) simulate_dialogue_impl 같은 "순수 구현 함수"가 있으면 직접 등록
# 2) register_simulate_dialogue_tool_fastmcp(mcp) 같은 헬퍼를 tools에서 만들어서 호출
try:
    # (권장) FastMCP 전용 등록 헬퍼가 있으면 이걸 사용
    from .tools.simulate_dialogue import register_simulate_dialogue_tool_fastmcp
    USE_HELPER = True
except ImportError:
    # 없으면 순수 구현 함수로 직접 등록 (아래 B 분기 사용)
    from .tools.simulate_dialogue import simulate_dialogue_impl
    USE_HELPER = False


def build_app():
    init_db()

    # ✅ FastMCP 인스턴스 생성
    mcp = FastMCP("vp-mcp-sim")

    # (A-1) FastMCP 등록 헬퍼가 있다면 그걸로 등록
    if USE_HELPER:
        register_simulate_dialogue_tool_fastmcp(mcp)
    else:
        # (B) 직접 등록 (simulate_dialogue_impl은 dict->dict 구현이어야 함)
        @mcp.tool(name="sim.simulate_dialogue", description="공격자/피해자 LLM 교대턴 시뮬레이션 실행 후 로그 반환 및 DB 저장")
        async def simulate_dialogue(arguments: dict) -> dict:
            # arguments는 app에서 보낸 SimulationInput과 1:1 매핑
            return simulate_dialogue_impl(arguments)

    # ✅ /mcp 경로에 Streamable HTTP 엔드포인트 마운트
    app = Starlette(routes=[
        Mount("/mcp", app=mcp.streamable_http_app()),
    ])
    return app


app = build_app()

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "5177"))
    uvicorn.run("mcp_server.server:app", host=host, port=port, reload=True)
