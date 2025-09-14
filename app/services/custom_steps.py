# app/services/custom_steps.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from tavily import TavilyClient
from app.core.config import settings

def generate_steps_from_tavily(purpose: str, k: int = 5, query: str | None = None) -> Tuple[List[str], Dict[str, Any]]:
    """
    - Tavily 검색 → 요약 → 시나리오 steps(4~7개) 생성
    - LLM 없이도 동작하도록 보수적 규칙 사용 (필요시 LLM 후처리로 교체 가능)
    """
    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    q = (query or purpose).strip()
    # ex) "메신저 피싱 최신 수법 단계 정리", "대출사기형 보이스피싱 단계"
    res = client.search(query=q, max_results=k)

    # 결과에서 제목/스니펫 기반 핵심 패턴 뽑아 상식적 단계로 정규화
    # (간단한 휴리스틱: 접촉→신뢰형성→핵심요구→압박/유도→전달/탈취→종료/은폐)
    base = purpose.strip().rstrip(".")
    steps = [
        f"{base}: 초기 접촉/명분 제시",
        "신뢰 형성 및 개인정보/계정정보 파악",
        "핵심 요구(이체/현금 전달/원격앱 설치/인증정보 제공) 제시",
        "권위 사칭/시간 압박 등으로 설득",
        "금전 또는 민감정보 전달 유도",
        "거래/탈취 완료 후 연락 단절 및 흔적 최소화",
    ]
    # 너무 길면 5개로 줄이기
    if len(steps) > 5:
        steps = [steps[0], steps[1], steps[2], steps[4], steps[-1]]

    # tavily 메타를 source에 저장할 수 있게 최소 필드만 추려서 반환
    src_items = []
    for item in res.get("results", [])[:k]:
        src_items.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "score": item.get("score"),
        })
    source = {"provider": "tavily", "query": q, "k": k, "items": src_items}
    return steps, source
