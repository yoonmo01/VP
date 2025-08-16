# app/services/llm_providers.py
from typing import Optional
from app.core.config import settings
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

def openai_chat(model: Optional[str] = None, temperature: float = 0.7):
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    mdl = model or settings.ADMIN_MODEL
    is_o_series = mdl.strip().lower().startswith("o")  # "o4-mini", "o3-mini", "o1" 등

    if is_o_series:
        # ❗ 기본값(0.7)이 실수로 들어가지 않게 temperature=1을 **명시적으로** 전달
        return ChatOpenAI(
            model=mdl,
            temperature=1,            # ← 이것이 핵심
            api_key=settings.OPENAI_API_KEY,
        )
    else:
        return ChatOpenAI(
            model=mdl,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )

def gemini_chat(model: Optional[str] = None, temperature: float = 0.7):
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")
    return ChatGoogleGenerativeAI(
        model=model or "gemini-2.5-flash-lite",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
    )

def attacker_chat():
    # gpt-4.1-mini는 temperature 조절 가능
    return openai_chat(settings.ATTACKER_MODEL, temperature=0.7)

def victim_chat():
    provider = getattr(settings, "VICTIM_PROVIDER", "openai").lower()
    model = settings.VICTIM_MODEL
    if provider == "gemini":
        return gemini_chat(model, temperature=0.7)
    elif provider == "openai":
        return openai_chat(model, temperature=0.7)
    else:
        raise ValueError(f"Unsupported VICTIM_PROVIDER: {provider}. Use 'openai' or 'gemini'.")

def admin_chat():
    # o4-mini 경로 → temperature=1이 강제되도록 openai_chat 내부 분기 사용
    return openai_chat(settings.ADMIN_MODEL)
