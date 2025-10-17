# app/services/agent/turn_bus.py
from __future__ import annotations
from typing import Callable, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# stream_id -> sink(callback) 등록
_SINKS: Dict[str, Callable[[Dict[str, Any]], None]] = {}
_CURRENT_STREAM_ID: Optional[str] = None

def set_stream_id(stream_id: str):
    global _CURRENT_STREAM_ID
    _CURRENT_STREAM_ID = stream_id

def register_sink(stream_id: str, sink: Callable[[Dict[str, Any]], None]):
    _SINKS[stream_id] = sink
    logger.info("[turn_bus] sink registered for stream=%s", stream_id)

def unregister_sink(stream_id: str):
    if stream_id in _SINKS:
        _SINKS.pop(stream_id, None)
        logger.info("[turn_bus] sink unregistered for stream=%s", stream_id)

def push(stream_id: str, ev: Dict[str, Any]) -> bool:
    sink = _SINKS.get(stream_id)
    if not sink:
        return False
    try:
        sink(ev)
        return True
    except Exception as e:
        logger.warning("[turn_bus] sink push failed: %s", e)
        return False
