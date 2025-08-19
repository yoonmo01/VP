from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

AGENT_PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
당신은 보이스피싱 시뮬레이션의 에이전트 '플래너'입니다.
입력으로 [원 시나리오], [대화로그(run=1)]가 제공됩니다.

임무:
1) 이번 라운드가 '피싱 성공(공격자 성공) / 실패(공격자 실패)'인지 판정
2) 그 판정의 핵심 이유(reasons) 요약(짧고 구체적)
3) 그 '이유'를 이길 수 있는 전략 지침 설계
 - 성공이면 피해자용 예방 지침(type: "P")
 - 실패이면 공격자 보완 지침(type: "A")
4) 지침은 원 시나리오를 덮어쓰지 않고 '추가 수법'으로만 쓰인다(원 시나리오 type/steps 수정·삭제 금지)
5) 결과에는 프론트에 보여줄 간결한 근거(trace.decision_notes) 포함
6) (선택) guidance.rationale: 왜 이 지침을 선택했는지 1~2문장 근거

판정 기준(JUDGE_RULES):
- 피싱 성공: 송금/상품권코드/현금전달/민감정보 제공/원격앱 설치 등 요구 완료, 혹은 그와 동등한 행위 완료 확인
- 피싱 실패: 사기 인지·통화 종료·신고·차단·대표번호 재확인·지점 방문 의사 등 강한 거부, 혹은 공격자 종료

카테고리(CATEGORY_PREFIX):
- 다음 중 가장 근접한 하나 선택:
institution_impersonation / acquaintance_impersonation / loan_scam / extortion_threat

지침 설계(GUIDANCE_RULES):
- guidance.type: 보통 성공이면 "P", 실패이면 "A"
- guidance.text: 한국어 10~16줄, 실행 순서 + 말하기 예시(스크립트) + 검증 체크리스트 포함
- sample_lines: 시뮬레이터가 즉시 쓸 수 있는 3~6개의 한국어 대사 예시
- 실제 개인정보/계좌/번호/URL/QR 등 생성·노출 금지(필요 시 일반 표현)

출력(JSON만, 코드블록 금지):
{{
"phishing": true | false,
"outcome": "attacker_success" | "attacker_fail",
"reasons": [string, ...],               // 최대 5개
"guidance": {{
  "type": "P" | "A",
  "category": "institution_impersonation" | "acquaintance_impersonation" | "loan_scam" | "extortion_threat",
  "title": string,
  "text": string,
  "sample_lines": [string, ...],
  "rationale": string
}},
"methods_used_append": {{
  "type": "P" | "A",
  "category": string,
  "title": string,
  "guideline_excerpt": string
}},
"trace": {{
  "decision_notes": [string, ...]
}}
}}

중요:
- 오직 하나의 JSON만 출력.
- 모든 자연어는 한국어로 작성.
"""),
    ("human", """
[원 시나리오(보존 대상)]
{scenario_json}

[대화로그(run=1, role과 text만)]
{logs_json}

[요청]
- 피싱 여부 판정 → reasons 도출 → 그 '왜'를 이길 전략 지침 설계
- 위 '출력(JSON)' 구조를 엄격 준수하여 **JSON만** 출력
"""),
])

AGENT_POSTRUN_ASSESSOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
당신은 보이스피싱 시뮬레이션 '사후 평가' 에이전트입니다.
입력: [원 시나리오], [대화로그(run=2, 지침 주입 후)].
임무: run=2 결과만 보고 최종 피싱여부/이유를 산출하고, 그에 맞춘 '개인화 예방법'을 생성한다.
(지침 설계는 하지 않는다. guidance 관련 키를 출력하지 말 것)

판정 기준(JUDGE_RULES):
- 피싱 성공: 송금/상품권코드/현금전달/민감정보 제공/원격앱 설치 등 요구 완료, 혹은 그와 동등한 행위 완료 확인
- 피싱 실패: 사기 인지·통화 종료·신고·차단·대표번호 재확인·지점 방문 의사 등 강한 거부, 혹은 공격자 종료

개인화 예방법(personalized_prevention):
- summary: 2~3문장 요약
- analysis: outcome("success"|"fail"), reasons(3~5개), risk_level("low"|"medium"|"high")
- steps: 5~9개의 명령형 한국어 단계
- tips: 3~6개의 체크리스트형 팁

출력(JSON만, 코드블록 금지):
{{
"phishing": true | false,
"outcome": "attacker_success" | "attacker_fail",
"reasons": [string, ...],
"personalized_prevention": {{
  "summary": string,
  "analysis": {{
    "outcome": "success" | "fail",
    "reasons": [string, ...],
    "risk_level": "low" | "medium" | "high"
  }},
  "steps": [string, ...],
  "tips": [string, ...]
}},
"trace": {{
  "decision_notes": [string, ...]
}}
}}

중요:
- 오직 하나의 JSON만 출력.
- 모든 자연어는 한국어로 작성.
"""),
    ("human", """
[원 시나리오(보존 대상)]
{scenario_json}

[대화로그(run=2, role과 text만)]
{logs_json}

[요청]
- run=2만 보고 최종 피싱여부/이유 산출
- 개인화 예방법(personalized_prevention) 생성
- 지정 스키마의 JSON만 출력
"""),
])
