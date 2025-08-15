# app/services/llm_providers.py
from typing import Optional
from app.core.config import settings
from langchain_openai import ChatOpenAI

def openai_chat(model: Optional[str] = None) -> ChatOpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    return ChatOpenAI(
        model=model or settings.OPENAI_MODEL,  # ex) gpt-4.1-mini
        temperature=0.7,
        api_key=settings.OPENAI_API_KEY,
    )

# ✅ 지금은 전부 GPT로: gemini_chat도 GPT로 우회
def gemini_chat(model: Optional[str] = None) -> ChatOpenAI:
    return openai_chat(model or settings.OPENAI_MODEL)

# (옵션) 역할별 래퍼도 모두 GPT로
def attacker_chat(): return openai_chat(settings.ATTACKER_MODEL)
def victim_chat():   return openai_chat(settings.VICTIM_MODEL)
def admin_chat():    return openai_chat(settings.ADMIN_MODEL)
