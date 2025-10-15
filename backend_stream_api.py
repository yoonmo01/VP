"""
보이스피싱 시뮬레이터 백엔드 (Streamable HTTP)
MCP 서버를 호출하고 결과를 NDJSON으로 스트리밍
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, AsyncGenerator
import httpx
import json
import asyncio

app = FastAPI(title="VP Simulator Backend")

# CORS 설정 (프론트엔드와 연결)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP 서버 URL
MCP_SERVER_URL = "http://127.0.0.1:5177"

class SimulateRequest(BaseModel):
    """프론트엔드에서 받을 시나리오 정보"""
    offender_id: int = 1
    victim_id: int = 1
    scenario_type: str = "bank_impersonation"  # 시나리오 타입
    victim_age: int = 65
    victim_tech_level: str = "low"
    max_turns: int = 10

# 시나리오 템플릿
SCENARIO_TEMPLATES = {
    "bank_impersonation": {
        "attacker_system": """당신은 은행원을 사칭하는 보이스피싱 범죄자입니다.
목표: 피해자의 계좌번호와 비밀번호를 알아내기
전략: 
- 긴급한 보안 문제가 있다고 말하기
- 권위있는 말투 사용
- 빠른 행동을 요구하기
자연스럽고 설득력있게 대화하세요.""",
        
        "victim_system": """당신은 {age}세의 일반인입니다.
기술 이해도: {tech_level}
특성:
- 은행 직원을 신뢰하는 경향
- 긴급 상황에 당황함
- 개인정보 보호에 대한 인식이 낮음
자연스럽게 반응하세요.""",
        
        "scenario_desc": "은행원 사칭 피싱"
    },
    
    "government_officer": {
        "attacker_system": """당신은 정부 기관 직원을 사칭하는 보이스피싱 범죄자입니다.
목표: 피해자로부터 금전 이체를 유도하기
전략:
- 법적 문제가 발생했다고 위협
- 공식적이고 권위있는 말투
- 즉시 해결하지 않으면 큰 문제가 된다고 압박
설득력있게 연기하세요.""",
        
        "victim_system": """당신은 {age}세의 일반인입니다.
기술 이해도: {tech_level}
특성:
- 정부 기관을 두려워함
- 법적 문제에 민감
- 혼란스러운 상황에서 판단력 저하
자연스럽게 반응하세요.""",
        
        "scenario_desc": "정부기관 사칭 피싱"
    }
}

async def stream_simulation(request: SimulateRequest) -> AsyncGenerator[str, None]:
    """MCP 서버 호출 및 스트리밍 처리"""
    
    # 1. 시나리오 템플릿 가져오기
    template = SCENARIO_TEMPLATES.get(request.scenario_type, SCENARIO_TEMPLATES["bank_impersonation"])
    
    # 2. MCP 요청 페이로드 구성
    mcp_payload = {
        "arguments": {
            "attacker": {
                "system": template["attacker_system"]
            },
            "victim": {
                "system": template["victim_system"].format(
                    age=request.victim_age,
                    tech_level=request.victim_tech_level
                )
            },
            "max_turns": request.max_turns,
            "offender_id": request.offender_id,
            "victim_id": request.victim_id,
            "scenario": {
                "type": request.scenario_type,
                "description": template["scenario_desc"]
            },
            "victim_profile": {
                "meta": {"age": request.victim_age, "tech_level": request.victim_tech_level}
            },
            "models": {
                "attacker": "gpt-4o-mini",
                "victim": "gemini-2.0-flash-exp"
            },
            "temperature": 0.7
        }
    }
    
    # 3. 시뮬레이션 시작 알림
    yield json.dumps({
        "type": "start",
        "data": {
            "scenario": template["scenario_desc"],
            "max_turns": request.max_turns
        }
    }) + "\n"
    
    # 4. MCP 서버 호출 (실제 시뮬레이션)
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{MCP_SERVER_URL}/api/simulate",
                json=mcp_payload
            )
            
            if response.status_code != 200:
                yield json.dumps({
                    "type": "error",
                    "data": {"message": f"MCP 서버 오류: {response.status_code}"}
                }) + "\n"
                return
            
            result = response.json()
            
            # 5. 대화 턴 스트리밍
            if "result" in result and "turns" in result["result"]:
                turns = result["result"]["turns"]
                
                for i, turn in enumerate(turns):
                    # 각 턴을 개별적으로 스트리밍
                    yield json.dumps({
                        "type": "dialogue",
                        "data": {
                            "turn": i + 1,
                            "speaker": turn["role"],
                            "message": turn["text"]
                        }
                    }) + "\n"
                    
                    # 실시간 느낌을 위한 약간의 딜레이
                    await asyncio.sleep(0.3)
                    
                    # 피싱 패턴 감지 (간단한 규칙 기반)
                    if i % 2 == 0:  # 공격자 턴마다
                        detection = analyze_phishing_patterns(turn["text"])
                        if detection["is_suspicious"]:
                            yield json.dumps({
                                "type": "detection",
                                "data": detection
                            }) + "\n"
                
                # 6. 분석 결과 생성
                analysis = generate_analysis(turns)
                yield json.dumps({
                    "type": "analysis",
                    "data": analysis
                }) + "\n"
                
                # 7. 대응 지침 생성
                guidelines = generate_guidelines(turns)
                for guideline in guidelines:
                    yield json.dumps({
                        "type": "guideline",
                        "data": guideline
                    }) + "\n"
                    await asyncio.sleep(0.2)
                
                # 8. 예방책 생성
                preventions = generate_preventions(request.scenario_type)
                for prevention in preventions:
                    yield json.dumps({
                        "type": "prevention",
                        "data": prevention
                    }) + "\n"
                    await asyncio.sleep(0.2)
            
            # 9. 완료 알림
            yield json.dumps({
                "type": "complete",
                "data": {
                    "conversation_id": result.get("result", {}).get("conversation_id", ""),
                    "total_turns": len(turns) if "turns" in result.get("result", {}) else 0
                }
            }) + "\n"
            
        except Exception as e:
            yield json.dumps({
                "type": "error",
                "data": {"message": str(e)}
            }) + "\n"

def analyze_phishing_patterns(text: str) -> Dict[str, Any]:
    """피싱 패턴 감지 (간단한 키워드 기반)"""
    suspicious_keywords = [
        "계좌번호", "비밀번호", "개인정보", "카드번호",
        "긴급", "즉시", "지금 당장", "법적 조치", "체포"
    ]
    
    found = [kw for kw in suspicious_keywords if kw in text]
    
    return {
        "is_suspicious": len(found) > 0,
        "confidence": min(len(found) * 0.3, 1.0),
        "patterns": found,
        "message": f"의심스러운 키워드 감지: {', '.join(found)}" if found else ""
    }

def generate_analysis(turns: list) -> Dict[str, Any]:
    """전체 대화 분석"""
    offender_turns = [t for t in turns if t["role"] == "offender"]
    victim_turns = [t for t in turns if t["role"] == "victim"]
    
    # 간단한 위험도 계산
    risk_score = min(len(offender_turns) * 0.15, 1.0)
    
    return {
        "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low",
        "risk_score": round(risk_score, 2),
        "total_turns": len(turns),
        "offender_tactics": ["긴급성 강조", "권위 사칭", "개인정보 요구"],
        "victim_vulnerabilities": ["정보 확인 부족", "즉각적 반응"]
    }

def generate_guidelines(turns: list) -> list:
    """대응 지침 생성"""
    return [
        {
            "priority": "high",
            "category": "즉시 행동",
            "content": "통화를 즉시 종료하고 공식 은행 번호로 직접 확인하세요."
        },
        {
            "priority": "medium",
            "category": "정보 보호",
            "content": "어떤 경우에도 계좌번호나 비밀번호를 전화로 알려주지 마세요."
        },
        {
            "priority": "medium",
            "category": "신고",
            "content": "의심스러운 전화는 경찰(112) 또는 금융감독원(1332)에 신고하세요."
        }
    ]

def generate_preventions(scenario_type: str) -> list:
    """예방책 생성"""
    base_preventions = [
        {
            "title": "공식 채널 확인",
            "description": "은행이나 정부기관은 전화로 개인정보를 요구하지 않습니다.",
            "actionable": "수상한 전화를 받으면 끊고, 공식 웹사이트에서 찾은 번호로 직접 연락하세요."
        },
        {
            "title": "시간을 가지세요",
            "description": "피싱범은 '긴급', '즉시'라는 말로 압박합니다.",
            "actionable": "급하게 결정하지 말고, 가족이나 친구와 상의하세요."
        },
        {
            "title": "개인정보 보호",
            "description": "계좌번호, 비밀번호, 카드번호는 절대 전화로 알려주지 마세요.",
            "actionable": "요청받으면 무조건 거절하고 공식 채널로 문의하세요."
        }
    ]
    return base_preventions

@app.post("/api/simulate")
async def simulate_endpoint(request: SimulateRequest):
    """시뮬레이션 시작 엔드포인트 (스트리밍)"""
    return StreamingResponse(
        stream_simulation(request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/health")
async def health_check():
    """헬스체크"""
    return {"status": "ok", "service": "vp-simulator-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)