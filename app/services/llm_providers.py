# app/services/llm_providers.py
from typing import Optional
from app.core.config import settings

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


# ---------- 공통: OpenAI ----------
def openai_chat(model: Optional[str] = None, temperature: float = 0.7):
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    return ChatOpenAI(
        model=model or settings.OPENAI_MODEL,  # 예: gpt-4.1-mini
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )


# ---------- 공통: Gemini ----------
def gemini_chat(model: Optional[str] = None, temperature: float = 0.7):
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")
    return ChatGoogleGenerativeAI(
        model=model or "gemini-2.5-flash-lite",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
    )


# ---------- 역할별 래퍼 ----------
def attacker_chat():
    # 공격자는 OpenAI 유지 (필요하면 ENV로 분기 추가 가능)
    return openai_chat(settings.ATTACKER_MODEL, temperature=0.7)


def victim_chat():
    # 피해자만 프로바이더 스위치: openai | gemini
    provider = getattr(settings, "VICTIM_PROVIDER", "openai").lower()
    model = settings.VICTIM_MODEL

    if provider == "gemini":
        return gemini_chat(model, temperature=0.7)  # 예: gemini-2.5-flash-lite
    elif provider == "openai":
        return openai_chat(model, temperature=0.7)
    else:
        raise ValueError(f"Unsupported VICTIM_PROVIDER: {provider}. Use 'openai' or 'gemini'.")


def admin_chat():
    # 요약/채점용은 안정성 위해 온도 낮게
    return openai_chat(settings.ADMIN_MODEL, temperature=0.2)
