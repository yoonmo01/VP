# # app/core/log_config.py
# import os, sys
# import logging as _logging
# from contextvars import ContextVar

# # 요청 단위 추적용 request_id 컨텍스트
# _request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# def setup_logging():
#     level = os.getenv("LOG_LEVEL", "INFO").upper()
#     fmt = os.getenv("LOG_FORMAT", "text")  # "text" | "json"

#     root = _logging.getLogger()
#     root.setLevel(level)

#     # uvicorn 기본 핸들러 중복 제거
#     for h in list(root.handlers):
#         root.removeHandler(h)

#     handler = _logging.StreamHandler(sys.stdout)
#     if fmt == "json":
#         try:
#             from json_log_formatter import JSONFormatter  # pip install json-log-formatter (선택)
#             handler.setFormatter(JSONFormatter())
#         except Exception:
#             handler.setFormatter(
#                 _logging.Formatter(
#                     "%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
#     else:
#         handler.setFormatter(
#             _logging.Formatter(
#                 "%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

#     root.addHandler(handler)

# def get_request_id() -> str | None:
#     return _request_id.get()

# def set_request_id(req_id: str | None):
#     _request_id.set(req_id)
