# import logging

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
# )
# logger = logging.getLogger("voicephish")
# app/core/logging.py
from __future__ import annotations
import logging
import logging.config
from contextvars import ContextVar
from typing import Optional
import uuid

# ── 요청 컨텍스트
_REQUEST_ID: ContextVar[str] = ContextVar("_REQUEST_ID", default="-")
_REQUEST_VERBOSE: ContextVar[bool] = ContextVar("_REQUEST_VERBOSE",
                                                default=False)


def set_request_id(req_id: Optional[str] = None) -> str:
    rid = req_id or str(uuid.uuid4())
    _REQUEST_ID.set(rid)
    return rid


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_verbose(flag: bool) -> None:
    _REQUEST_VERBOSE.set(bool(flag))


def get_request_verbose() -> bool:
    return _REQUEST_VERBOSE.get()


class RequestContextFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.verbose = get_request_verbose()
        return True


class VerboseGateFilter(logging.Filter):
    """DEBUG 로그는 verbose=True 일 때만 통과; INFO 이상은 항상 통과."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.INFO:
            return True
        return get_request_verbose()


def setup_logging(level: str = "INFO") -> None:
    fmt = "[%(levelname)s] %(asctime)s %(name)s " \
          "rid=%(request_id)s verbose=%(verbose)s :: %(message)s"
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "ctx": {"()": RequestContextFilter},
            "v_gate": {"()": VerboseGateFilter},
        },
        "formatters": {"default": {"format": fmt}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",              # 모두 받고
                "filters": ["ctx", "v_gate"],  # v_gate에서 걸러냄
                "formatter": "default",
            }
        },
        "loggers": {
            "": {  # root
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
        },
    }
    logging.config.dictConfig(config)


def get_logger(name: str = "voicephish") -> logging.Logger:
    return logging.getLogger(name)


# ── 뒤호환: 기존 코드에서 import 하던 logger 객체 유지
logger = get_logger("voicephish")
