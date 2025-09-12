# app/mcp/mcp_ws_server.py
from __future__ import annotations
import json
from types import SimpleNamespace
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime

from app.db.session import SessionLocal
from app.services.simulation import run_two_bot_simulation
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# MCP 도구 스키마 정의
TOOLS = [
    {
        "name": "simulator.run",
        "description": "Run voice-phishing simulation with React Agent optimized prompts",
        "inputSchema": {
            "type": "object",
            "properties": {
                "offender_id": {"type": "integer"},
                "victim_id": {"type": "integer"},
                "case_id_override": {"type": ["string", "null"]},
                "run_no": {"type": "integer", "default": 1},
                "max_rounds": {"type": "integer", "default": 30},
                "scenario": {"type": "object"},
                "guidance_type": {"type": ["string", "null"]},
                "guideline": {"type": ["string", "null"]},
                # React Agent 최적화 프롬프트들
                "custom_prompts": {
                    "type": "object",
                    "properties": {
                        "attacker_prompt": {"type": "string"},
                        "victim_prompt": {"type": "string"}
                    }
                },
                # 모델 선택
                "models": {
                    "type": "object",
                    "properties": {
                        "attacker_model": {"type": "string", "default": "gpt-4"},
                        "victim_model": {"type": "string", "default": "claude-3"}
                    }
                }
            },
            "required": ["offender_id", "victim_id"]
        }
    },
    {
        "name": "simulator.status",
        "description": "Get simulation status and recent logs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
                "run_no": {"type": "integer", "default": None}
            },
            "required": ["case_id"]
        }
    },
    {
        "name": "simulator.logs",
        "description": "Retrieve conversation logs for analysis",
        "inputSchema": {
            "type": "object", 
            "properties": {
                "case_id": {"type": "string"},
                "run_no": {"type": "integer", "default": None},
                "limit": {"type": "integer", "default": 50}
            },
            "required": ["case_id"]
        }
    }
]

@router.websocket("/ws")
async def mcp_websocket_handler(websocket: WebSocket):
    """MCP WebSocket 서버 - React Agent와 통신"""
    await websocket.accept()
    session_id = id(websocket)
    logger.info(f"MCP WebSocket 연결: {session_id}")

    try:
        while True:
            # 메시지 수신
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
                msg_id = message.get("id")
                method = message.get("method")
                params = message.get("params") or {}

                logger.debug(f"MCP 요청 수신: {method} (id: {msg_id})")

                # MCP 프로토콜 처리
                if method == "initialize":
                    response = {
                        "serverInfo": {
                            "name": "voice-phishing-simulation-mcp", 
                            "version": "2.0.0",
                            "description": "React Agent 지원 보이스피싱 시뮬레이션 MCP 서버"
                        },
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "logging": {"level": "info"},
                            "resources": {}
                        }
                    }
                    await send_response(websocket, msg_id, response)

                elif method in ("tools/list", "mcp.tools.list"):
                    response = {"tools": TOOLS}
                    await send_response(websocket, msg_id, response)

                elif method in ("tools/call", "mcp.tools.call"):
                    await handle_tool_call(websocket, msg_id, params)

                elif method == "ping":
                    await send_response(websocket, msg_id, "pong")

                else:
                    await send_error(websocket, msg_id, -32601, f"Method '{method}' not found")

            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                await send_error(websocket, None, -32700, "Parse error")

            except Exception as e:
                logger.error(f"메시지 처리 오류: {e}")
                await send_error(websocket, msg_id if 'msg_id' in locals() else None, -32603, "Internal error")

    except WebSocketDisconnect:
        logger.info(f"MCP WebSocket 연결 종료: {session_id}")
    except Exception as e:
        logger.error(f"MCP WebSocket 오류: {e}")
        await websocket.close()


async def send_response(websocket: WebSocket, msg_id: str, result: dict):
    """성공 응답 전송"""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": result
    }
    await websocket.send_text(json.dumps(response, ensure_ascii=False))


async def send_error(websocket: WebSocket, msg_id: str, code: int, message: str):
    """에러 응답 전송"""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": code,
            "message": message
        }
    }
    await websocket.send_text(json.dumps(response, ensure_ascii=False))


async def handle_tool_call(websocket: WebSocket, msg_id: str, params: dict):
    """도구 호출 처리"""
    tool_name = params.get("name")
    args = params.get("arguments") or {}

    try:
        if tool_name == "simulator.run":
            await handle_simulation_run(websocket, msg_id, args)
        elif tool_name == "simulator.status":
            await handle_simulation_status(websocket, msg_id, args)
        elif tool_name == "simulator.logs":
            await handle_simulation_logs(websocket, msg_id, args)
        else:
            await send_error(websocket, msg_id, -32601, f"Unknown tool: {tool_name}")

    except Exception as e:
        logger.error(f"도구 실행 오류 ({tool_name}): {e}")
        await send_error(websocket, msg_id, -32000, f"Tool execution failed: {str(e)}")


async def handle_simulation_run(websocket: WebSocket, msg_id: str, args: dict):
    """시뮬레이션 실행"""
    db = SessionLocal()
    try:
        # React Agent가 최적화한 설정들 추출
        custom_prompts = args.get("custom_prompts", {})
        models = args.get("models", {})

        logger.info(f"시뮬레이션 시작: offender_id={args.get('offender_id')}, victim_id={args.get('victim_id')}")

        # 시뮬레이션 요청 구성
        simulation_request = SimpleNamespace(
            offender_id=args["offender_id"],
            victim_id=args["victim_id"],
            include_judgement=True,
            max_rounds=args.get("max_rounds", 30),
            case_scenario={
                **(args.get("scenario") or {}),
                "guidance_type": args.get("guidance_type"),
                "guideline": args.get("guideline"),
                # React Agent 최적화 프롬프트 적용
                "custom_attacker_prompt": custom_prompts.get("attacker_prompt"),
                "custom_victim_prompt": custom_prompts.get("victim_prompt"),
                "attacker_model": models.get("attacker_model", "gpt-4"),
                "victim_model": models.get("victim_model", "claude-3"),
                # React Agent 메타데이터
                "react_agent_optimized": bool(custom_prompts),
                "optimization_timestamp": datetime.now().isoformat()
            },
            case_id_override=args.get("case_id_override"),
            run_no=args.get("run_no", 1),
            use_agent=True,  # React Agent 시뮬레이션임을 표시
            guidance_type=args.get("guidance_type"),
            guideline=args.get("guideline")
        )

        # 시뮬레이션 실행
        case_id, total_turns = run_two_bot_simulation(db, simulation_request)

        # 성공 응답
        result = {
            "content": {
                "case_id": str(case_id),
                "run": int(simulation_request.run_no),
                "total_turns": total_turns,
                "models_used": {
                    "attacker": models.get("attacker_model", "gpt-4"),
                    "victim": models.get("victim_model", "claude-3")
                },
                "react_agent_enhanced": {
                    "custom_prompts_applied": bool(custom_prompts),
                    "optimization_level": "high" if custom_prompts else "standard"
                },
                "execution_timestamp": datetime.now().isoformat(),
                "mcp_server": "voice-phishing-simulation-v2"
            }
        }

        logger.info(f"시뮬레이션 완료: case_id={case_id}, turns={total_turns}")
        await send_response(websocket, msg_id, result)

    except Exception as e:
        logger.error(f"시뮬레이션 실행 실패: {e}")
        raise
    finally:
        db.close()


async def handle_simulation_status(websocket: WebSocket, msg_id: str, args: dict):
    """시뮬레이션 상태 조회"""
    from uuid import UUID
    from app.db.models import ConversationLog

    db = SessionLocal()
    try:
        case_id = UUID(args["case_id"])
        run_no = args.get("run_no")

        # 로그 조회 쿼리
        query = db.query(ConversationLog).filter(ConversationLog.case_id == case_id)
        if run_no:
            query = query.filter(ConversationLog.run == run_no)

        logs = query.order_by(ConversationLog.turn_index.asc()).all()

        # 상태 정보 구성
        status_info = {
            "content": {
                "case_id": str(case_id),
                "total_logs": len(logs),
                "available_runs": list(set(log.run for log in logs)),
                "last_activity": max(log.created_at for log in logs).isoformat() if logs else None,
                "simulation_active": len(logs) > 0,
                "recent_activity": [
                    {
                        "turn": log.turn_index,
                        "role": log.role,
                        "timestamp": log.created_at.isoformat(),
                        "run": log.run,
                        "preview": log.content[:100] + "..." if len(log.content) > 100 else log.content
                    }
                    for log in logs[-5:]  # 최근 5개 활동
                ]
            }
        }

        await send_response(websocket, msg_id, status_info)

    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        raise
    finally:
        db.close()


async def handle_simulation_logs(websocket: WebSocket, msg_id: str, args: dict):
    """대화 로그 조회"""
    from uuid import UUID
    from app.db.models import ConversationLog

    db = SessionLocal()
    try:
        case_id = UUID(args["case_id"])
        run_no = args.get("run_no")
        limit = args.get("limit", 50)

        # 로그 조회
        query = db.query(ConversationLog).filter(ConversationLog.case_id == case_id)
        if run_no:
            query = query.filter(ConversationLog.run == run_no)

        logs = query.order_by(ConversationLog.turn_index.asc()).limit(limit).all()

        # 로그 데이터 구성
        log_data = {
            "content": {
                "case_id": str(case_id),
                "run_filter": run_no,
                "total_retrieved": len(logs),
                "logs": [
                    {
                        "turn_index": log.turn_index,
                        "role": log.role,
                        "content": log.content,
                        "run": log.run,
                        "timestamp": log.created_at.isoformat(),
                        "use_agent": log.use_agent,
                        "guidance_type": log.guidance_type
                    }
                    for log in logs
                ]
            }
        }

        await send_response(websocket, msg_id, log_data)

    except Exception as e:
        logger.error(f"로그 조회 실패: {e}")
        raise
    finally:
        db.close()


# MCP 서버 정보 조회 엔드포인트 (HTTP)
@router.get("/info")
async def mcp_server_info():
    """MCP 서버 정보 (HTTP 엔드포인트)"""
    return {
        "server_name": "voice-phishing-simulation-mcp",
        "version": "2.0.0",
        "protocol": "MCP (Model Context Protocol)",
        "websocket_endpoint": "/mcp/ws",
        "features": [
            "React Agent 최적화 프롬프트 지원",
            "다중 LLM 모델 지원",
            "실시간 시뮬레이션 실행",
            "대화 로그 실시간 조회",
            "상태 모니터링"
        ],
        "available_tools": [tool["name"] for tool in TOOLS],
        "status": "ready"
    }