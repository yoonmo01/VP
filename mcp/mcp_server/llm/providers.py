from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from app_like_shim import make_openai_chat, make_gemini_chat  # 구현 방식 자유

class BaseRoleLLM:
    def __init__(self, model: str, system: str, temperature: float = 0.6):
        self.system = system
        self.temperature = temperature
        self.model = model
        self.chain = self._build_chain()

    def _build_chain(self):
        # 여기서 실제 ChatModel 인스턴스 생성 (OpenAI, Gemini 등)
        # 예: return ChatPromptTemplate.from_messages([("system", self.system)]) | chat_model
        ...

    def next(self, history: List, **kwargs) -> str:
        msg = self.chain.invoke({**kwargs, "history": history})
        return getattr(msg, "content", str(msg)).strip()

class AttackerLLM(BaseRoleLLM): ...
class VictimLLM(BaseRoleLLM): ...
