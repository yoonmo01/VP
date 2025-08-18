import os, asyncio
from typing import Callable, Awaitable


def _openai() -> Callable[[str], Awaitable[str]]:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def run(prompt: str) -> str:
        resp = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for safe research-only simulations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        )
        return resp.choices[0].message.content

    return run


def _anthropic() -> Callable[[str], Awaitable[str]]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

    async def run(prompt: str) -> str:
        resp = await asyncio.to_thread(
            lambda: client.messages.create(
                model=model,
                max_tokens=700,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return "".join([b.text for b in resp.content if getattr(b, "type", None) == "text"]) or ""

    return run


def get_llm() -> Callable[[str], Awaitable[str]]:
    if os.getenv("OPENAI_API_KEY"):
        return _openai()
    if os.getenv("ANTHROPIC_API_KEY"):
        return _anthropic()

    async def echo(prompt: str) -> str:
        return "[DEV] LLM 미설정. 다음 프롬프트 일부를 수신:\n" + (prompt or "")[:800]

    return echo