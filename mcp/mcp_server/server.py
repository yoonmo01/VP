from mcp.server import Server
from mcp.transport.websockets.server import serve_websocket
import asyncio, os
from .db.base import init_db
from .tools.simulate_dialogue import register_simulate_dialogue_tool

async def main():
    init_db()
    server = Server("vp-mcp-sim")
    register_simulate_dialogue_tool(server)
    host, port = os.getenv("MCP_HOST","127.0.0.1"), int(os.getenv("MCP_PORT","5177"))
    async with serve_websocket(server, host=host, port=port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
