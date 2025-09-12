# app/mcp/mcp_ws_server.py (개선 버전)
from __future__ import annotations
import json
import asyncio
from types import SimpleNamespace
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.db.session import SessionLocal
from app.services.simulation import run_two_bot_simulation
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])

# 도구 스키마 확장
TOOLS = [
    {
        "name": "simulator.run",
        "description":
        "Run voice-phishing simulation with customizable prompts and models",
        "inputSchema": {
            "type": "object",
            "properties": {
                "offender_id": {
                    "type": "integer"
                },
                "victim_id": {
                    "type": "integer"
                },
                "case_id_override": {
                    "type": ["string", "null"]
                },
                "run_no": {
                    "type": "integer",
                    "default": 1
                },
                "max_rounds": {
                    "type": "integer",
                    "default": 30
                },
                "scenario": {
                    "type": "object"
                },
                "guidance_type": {
                    "type": ["string", "null"]
                },
                "guideline": {
                    "type": ["string", "null"]
                },
                # React Agent가 최적화한 프롬프트들
                "custom_prompts": {
                    "type": "object",
                    "properties": {
                        "attacker_prompt": {
                            "type": "string"
                        },
                        "victim_prompt": {
                            "type": "string"
                        }
                    }
                },
                # 모델 선택
                "models": {
                    "type": "object",
                    "properties": {
                        "attacker_model": {
                            "type": "string",
                            "default": "gpt-4"
                        },
                        "victim_model": {
                            "type": "string",
                            "default": "claude-3"
                        }
                    }
                }
            },
            "required": ["offender_id", "victim_id"]
        }
    },
    {
        "name": "simulator.status",
        "description": "Get simulation status and logs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string"
                },
                "run_no": {
                    "type": "integer"
                }
            },
            "required": ["case_id"]
        }
    }
]


@router.websocket("/ws")
async def mcp_ws(ws: WebSocket):
    await ws.accept()
    session_id = id(ws)
    logger.info(f"MCP WebSocket 연결 시작: {session_id}")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mid = msg.get("id")
            method = msg.get("method")
            params = msg.get("params") or {}

            logger.debug(f"MCP 요청: {method} (id: {mid})")

            if method == "initialize":
                res = {
                    "serverInfo": {
                        "name": "voice-phishing-sim-mcp",
                        "version": "2.0.0"
                    },
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        },
                        "logging": {}
                    }
                }
                await ws.send_text(
                    json.dumps({
                        "jsonrpc": "2.0",
                        "id": mid,
                        "result": res
                    },
                               ensure_ascii=False))

            elif method in ("tools/list", "mcp.tools.list"):
                res = {"tools": TOOLS}
                await ws.send_text(
                    json.dumps({
                        "jsonrpc": "2.0",
                        "id": mid,
                        "result": res
                    },
                               ensure_ascii=False))

            elif method in ("tools/call", "mcp.tools.call"):
                await handle_tool_call(ws, mid, params)

            elif method == "ping":
                await ws.send_text(
                    json.dumps({
                        "jsonrpc": "2.0",
                        "id": mid,
                        "result": "pong"
                    }))

            else:
                await ws.send_text(
                    json.dumps({
                        "jsonrpc": "2.0",
                        "id": mid,
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found"
                        }
                    }))

    except WebSocketDisconnect:
        logger.info(f"MCP WebSocket 연결 종료: {session_id}")
    except Exception as e:
        logger.error(f"MCP WebSocket 오류: {e}")


async def handle_tool_call(ws: WebSocket, msg_id: str, params: Dict[str, Any]):
    """도구 호출 처리"""
    tool_name = params.get("name")
    args = params.get("arguments") or {}

    try:
        if tool_name == "simulator.run":
            await handle_simulation_run(ws, msg_id, args)
        elif tool_name == "simulator.status":
            await handle_simulation_status(ws, msg_id, args)
        else:
            await ws.send_text(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }))
    except Exception as e:
        logger.error(f"도구 실행 실패 ({tool_name}): {e}")
        await ws.send_text(
            json.dumps({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32000,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }))


async def handle_simulation_run(ws: WebSocket, msg_id: str, args: Dict[str,
                                                                       Any]):
    """시뮬레이션 실행 처리"""
    db = SessionLocal()
    try:
        # React Agent가 최적화한 설정 적용
        custom_prompts = args.get("custom_prompts", {})
        models = args.get("models", {})

        # 시뮬레이션 요청 구성
        sim_request = SimpleNamespace(
            offender_id=args["offender_id"],
            victim_id=args["victim_id"],
            include_judgement=True,
            max_rounds=args.get("max_rounds", 30),
            case_scenario={
                **(args.get("scenario") or {}),
                "guidance_type":
                args.get("guidance_type"),
                "guideline":
                args.get("guideline"),
                # React Agent 최적화 프롬프트 추가
                "custom_attacker_prompt":
                custom_prompts.get("attacker_prompt"),
                "custom_victim_prompt":
                custom_prompts.get("victim_prompt"),
                "attacker_model":
                models.get("attacker_model", "gpt-4"),
                "victim_model":
                models.get("victim_model", "claude-3")
            },
            case_id_override=args.get("case_id_override"),
            run_no=args.get("run_no", 1),
            use_agent=True,
            guidance_type=args.get("guidance_type"),
            guideline=args.get("guideline"))

        # 시뮬레이션 실행
        case_id, total_turns = run_two_bot_simulation(db, sim_request)

        result = {
            "case_id": str(case_id),
            "run": int(sim_request.run_no),
            "total_turns": total_turns,
            "models_used": models,
            "custom_prompts_applied": bool(custom_prompts),
            "timestamp": datetime.now().isoformat()
        }

        await ws.send_text(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": result
                    }
                },
                ensure_ascii=False))

    finally:
        db.close()


async def handle_simulation_status(ws: WebSocket, msg_id: str,
                                   args: Dict[str, Any]):
    """시뮬레이션 상태 조회"""
    db = SessionLocal()
    try:
        case_id = UUID(args["case_id"])
        run_no = args.get("run_no")

        # 로그 조회
        query = db.query(
            m.ConversationLog).filter(m.ConversationLog.case_id == case_id)
        if run_no:
            query = query.filter(m.ConversationLog.run == run_no)

        logs = query.order_by(m.ConversationLog.turn_index.asc()).all()

        status = {
            "case_id":
            str(case_id),
            "total_logs":
            len(logs),
            "runs":
            list(set(log.run for log in logs)),
            "last_update":
            max(log.created_at for log in logs).isoformat() if logs else None,
            "recent_logs": [
                {
                    "turn":
                    log.turn_index,
                    "role":
                    log.role,
                    "content":
                    log.content[:100] +
                    "..." if len(log.content) > 100 else log.content,
                    "run":
                    log.run
                } for log in logs[-5:]  # 최근 5개
            ]
        }

        await ws.send_text(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": status
                    }
                },
                ensure_ascii=False))

    finally:
        db.close()
