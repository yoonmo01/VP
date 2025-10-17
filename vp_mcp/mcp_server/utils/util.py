# vp_mcp/mcp_server/utils/util.py
import os, httpx

TURNBUS_URL = os.getenv("VP_TURNBUS_URL")
TURNBUS_TOKEN = os.getenv("VP_TURNBUS_TOKEN", "")

def emit_turn_event(stream_id: str, payload: dict):
    """
    payload 예시:
    {
      "type": "new_message",
      "case_id": "...",
      "round": 1,
      "turn_index": 17,
      "role": "victim",
      "content": "…",
      "created_kst": "2025-10-17T18:34:33"
    }
    """
    if not TURNBUS_URL or not stream_id:
        return
    data = {"stream_id": stream_id, **payload}
    headers = {"X-VoicePhish-Token": TURNBUS_TOKEN} if TURNBUS_TOKEN else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(TURNBUS_URL, json=data, headers=headers)
    except Exception:
        # 네트워크에 실패해도 시뮬레이터 진행 자체는 방해하지 않음
        pass
