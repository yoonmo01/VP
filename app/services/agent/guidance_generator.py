# app/services/agent/guidance_generator.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from sqlalchemy.orm import Session

from langchain_core.prompts import ChatPromptTemplate
from app.services.llm_providers import agent_chat
from app.core.logging import get_logger

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.utils.ids import safe_uuid

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────
# 동적 지침 생성 프롬프트
# ─────────────────────────────────────────────────────────
GUIDANCE_GENERATOR_PROMPT = ChatPromptTemplate.from_messages([("system", """
당신은 보이스피싱 시뮬레이션을 위한 전략 지침 생성 전문가입니다.

[목적]
- 현재 시나리오와 대화 상황을 분석하여 피싱범(공격자)에게 필요한 구체적인 지침을 생성합니다.
- 생성된 지침은 공격자 프롬프트의 guidance 섹션에 주입되어 더 현실적이고 효과적인 피싱 대화를 만듭니다.

[분석 기준]
1. **시나리오 특성**: 사칭 대상, 피싱 유형, 목표 행동
2. **피해자 프로필**: 연령대, 디지털 리터러시, 성격 특성
3. **대화 진행도**: 현재 단계, 피해자 반응, 신뢰도 구축 수준
4. **이전 라운드 결과**: 성공/실패 패턴, 피해자 저항 포인트
5. **상황별 전략 우선순위**: 
   - 저항 발생시: G, H, I 고려  
   - 복잡한 시나리오: K-V 활용
   - 특수 대상: 직업/상황별 맞춤 전략 (Q, T, U 등)

[지침 카테고리]
- 아래 카테고리는 예시이며(A~W), 반드시 A,B,C,F에 한정하지 않고 상황에 가장 적합한 조합을 선택할 수 있습니다.
- 필요하다면 2개 이상을 조합하거나 새로운 복합 카테고리를 제안해도 됩니다.

**기본 카테고리 (A~J)**
A. **어휘/어조 조절**: 피해자 수준에 맞는 언어 사용
B. **긴급성 강조**: 시간 압박을 통한 판단력 흐림
C. **감정적 접근**: 두려움, 책임감, 걱정 자극
D. **전문성 연출**: 용어, 절차, 공식성 강조
E. **점진적 요구**: 단계별 정보 수집 전략
F. **의심 무마**: 보안 우려 해소, 정당성 강조
G. **사칭 다변화**: 인물/기관 변경으로 신뢰성 증대
H. **수법 복합화**: 여러 피싱 기법 조합 활용
I. **심리적 압박**: 위협, 협박을 통한 강제성
J. **격리 및 통제**: 외부 접촉 차단, 물리적/심리적 고립 유도

[추가 시나리오]
**추가 시나리오 (K~W) - 반드시 하나 이상 포함 필수**
K. **카드배송-검사사칭 연계형**: 카드 배송기사 사칭 → 가짜 고객센터 연결 → 개인정보 유출 우려 조성 → 원격제어 앱 설치 유도 → 금감원/검찰청 사칭으로 확대, 전화 가로채기로 피해자 직접 통화도 조작
L. **납치빙자형 극단적 공포**: 가족 음성 모방 + 즉각적 협박("딸 납치", "나체 동영상 유포", "마약/폭행 연루", "칼에 찔림")으로 극도 공포 조성, 가족 보호 본능 자극해 즉시 송금 유도
M. **홈캠 해킹 협박형**: 가족 이름 + 주거지 홈캠 영상 보유 주장 + 지인 배포 위협으로 사생활 노출 공포 자극, 미리 파악한 개인정보로 신뢰성 강화
N. **공신력 기관 사칭**: 정당/군부대/시청/교도소 관계자 사칭으로 대리 구매 요청, 공적 업무 명분 + 나중 일괄 정산 약속으로 선입금 유도, 권위 복종 심리와 사회적 책임감 자극
O. **가족사칭 정보수집**: "회원가입 비밀번호 설정 도움" 명목으로 자주 사용하는 비밀번호 요청, 일상적 도움으로 위장해 중요 정보 탈취, 가족 간 신뢰 관계 악용
P. **허위계약서 작성유도**: 검사 사칭 → 범행계좌 이체 → 계좌 지급정지 → 차량거래 계약서 작성으로 해제 유도, 피해자를 범죄 은폐 공범으로 만드는 복합 수법
Q. **국세청 사칭 세무협박**: 자영업자 대상 "세금 포탈/미납" 의혹 제기 → 세무조사/법적 처벌 위협, 세무 관련 두려움과 사업 중단 위험으로 자영업자 스트레스 악용
R. **격리형 장기통제**: 범죄 연루 → 자금 전수조사 → 임시 보호관찰 → 격리 공간 유도 → 새 휴대폰 개통 → 원격제어 앱 설치 → 주변 연락 차단, 물리적/심리적 격리로 완전 통제
S. **권위 편향 활용**: 금융기관, 정부기관, 전문가 신분으로 즉각적 신뢰 획득, 전문 용어와 정확한 절차 지식으로 전문성 연출, 공신력 있는 기관명으로 무조건적 신뢰 유도
T. **손실 회피 심리**: 기존 대출 금리 인하, 채무 해결 기회 제시로 절박함 자극, 구체적 혜택("13% → 4% 금리 인하")으로 유혹, 현재 손실 상황 탈출 기회 착각 조성
U. **희소성 효과 조성**: "오늘만", "선착순", "마감 임박" 등으로 시간 압박, 깊은 고민이나 검증 시간 박탈로 즉흥적 결정 유도, 기회 상실 강박 조성
V. **휴리스틱 의존 악용**: 비대면 금융거래 일반화 상황 악용, "모바일 서류 제출", "온라인 승인" 등 익숙한 패턴으로 의심 차단, 기존 경험과 유사하게 위장해 직관적 신뢰 유도
W. **2차 피해 암시**: 비협조 시 추가 문제 제기

[필수 요구사항]
⚠️ **중요**: 선택된 카테고리(selected_categories)에는 반드시 K~W 중 하나 이상이 포함되어야 합니다.
- 기본 카테고리(A~J)만으로는 부족합니다.
- 추가 시나리오(K~W)를 활용하여 더욱 현실적이고 정교한 피싱 시뮬레이션을 구현해야 합니다.

[출력 형식]
반드시 다음 JSON 형식으로 응답하세요:
```json
{{
    "selected_categories": ["K", "A", "B"],  // 반드시 K~W 중 하나 이상 포함
    "guidance_text": "구체적인 지침 내용 (2-3문장)",
    "reasoning": "이 지침을 선택한 근거와 분석 (K~W 포함 이유 명시)",
    "expected_effect": "예상되는 효과나 변화"
}}
```
"""),
                                                              ("human", """
[시나리오 정보]
{scenario}

[피해자 프로필]
{victim_profile}

[현재 라운드]
{round_no}

[이전 판정 결과]
{previous_judgments}

[최근 대화 로그 (최대 5턴)]
{recent_logs}

위 정보를 종합 분석하여 다음 라운드에서 공격자가 사용할 최적의 지침을 생성해주세요.
반드시 추가 시나리오(K~W) 중 하나 이상을 포함해야 합니다
""")])


class SingleData(BaseModel):
    data: Any


def _unwrap(obj: Any) -> Dict[str, Any]:
    """LangChain Action Input 견고 언래핑."""

    # 딕셔너리면 그대로 사용
    if isinstance(obj, dict):
        return obj.get("data", obj)

    # Pydantic 모델이면 딕셔너리로 변환
    if hasattr(obj, 'model_dump'):
        dumped = obj.model_dump()
        return dumped.get("data", dumped)

    # 문자열인 경우 JSON 파싱 시도
    if isinstance(obj, str):
        try:
            # JSON 파싱 시도
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                # "data" 키가 있으면 그 안의 내용 반환
                if "data" in parsed:
                    return parsed["data"]
                else:
                    return parsed
            else:
                logger.warning(
                    f"[_unwrap] JSON 파싱 결과가 딕셔너리가 아님: {type(parsed)}")
                return {}
        except json.JSONDecodeError as e:
            logger.error(f"[_unwrap] JSON 파싱 실패: {str(e)}")
            logger.error(f"[_unwrap] 파싱 실패한 문자열: {obj[:200]}...")
            return {}

    # 기타
    logger.warning(f"[_unwrap] 예상치 못한 입력 타입: {type(obj)}")
    return {}


# ─────────────────────────────────────────────────────────
# 동적 지침 생성기 클래스
# ─────────────────────────────────────────────────────────
class DynamicGuidanceGenerator:

    def __init__(self):
        self.llm = agent_chat(temperature=0.7)  # 창의성을 위해 temperature 높임

    def generate_guidance(
            self, db: Session, case_id: str, round_no: int,
            scenario: Dict[str, Any], victim_profile: Dict[str, Any],
            previous_judgments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        시나리오와 상황을 분석하여 동적으로 지침을 생성합니다.
        """
        extracted_case_id: str | None = None     # ← ★ 반드시 초기화
        if not extracted_case_id or extracted_case_id in ("", "None"):
            extracted_case_id = "temp_case_id"
            logger.warning("[GuidanceGenerator] case_id 추출 실패, 임시값 사용")
            
        u = safe_uuid(extracted_case_id)
        if not u:
            logger.warning("[GuidanceGenerator] 임시 case_id 사용으로 로그 조회 생략")
            recent_logs = []
        else:
            extracted_case_id = str(u)
            recent_logs = self._get_recent_logs(db, extracted_case_id, round_no)

        try:
            # case_id 안전성 검사 및 변환
            extracted_case_id = None

            if hasattr(case_id, 'get') and callable(getattr(case_id, 'get')):
                # 딕셔너리 같은 객체인 경우
                logger.warning(
                    f"[GuidanceGenerator] case_id가 딕셔너리 같은 객체임: {case_id}")
                extracted_case_id = getattr(case_id, 'get',
                                            lambda x: None)("case_id")
                if not extracted_case_id:
                    # 첫 번째 값 시도
                    try:
                        for key in case_id:
                            value = case_id[key] if hasattr(
                                case_id, '__getitem__') else None
                            if isinstance(
                                    value,
                                    str) and len(value) == 36 and "-" in value:
                                extracted_case_id = value
                                break
                    except:
                        pass
            elif isinstance(case_id, str):
                extracted_case_id = case_id
            else:
                # 기타 타입인 경우 문자열 변환 시도
                extracted_case_id = str(case_id)

            # 추출된 case_id 검증
            if not extracted_case_id or extracted_case_id in ["", "None"]:
                extracted_case_id = "temp_case_id"
                logger.warning("[GuidanceGenerator] case_id 추출 실패, 임시값 사용")

            logger.info(
                f"[GuidanceGenerator] 추출된 case_id: {extracted_case_id}")

            # case_id가 유효한 UUID인지 확인
            if extracted_case_id == "temp_case_id":
                logger.warning("[GuidanceGenerator] 임시 case_id 사용으로 로그 조회 생략")
                recent_logs = []
            else:
                try:
                    from uuid import UUID
                    # UUID 유효성 검사
                    UUID(extracted_case_id)
                    recent_logs = self._get_recent_logs(
                        db, extracted_case_id, round_no)
                except ValueError as e:
                    logger.warning(
                        f"[GuidanceGenerator] 잘못된 UUID 형식: {extracted_case_id}, 오류: {e}"
                    )
                    recent_logs = []

            # previous_judgments 타입 검사 및 변환
            if isinstance(previous_judgments, str):
                try:
                    previous_judgments = json.loads(previous_judgments)
                except json.JSONDecodeError:
                    logger.warning(
                        "[GuidanceGenerator] previous_judgments JSON 파싱 실패, 빈 리스트 사용"
                    )
                    previous_judgments = []

            # previous_judgments가 리스트가 아닌 경우 처리
            if not isinstance(previous_judgments, list):
                if isinstance(previous_judgments, dict):
                    previous_judgments = [previous_judgments]
                else:
                    logger.warning(
                        f"[GuidanceGenerator] previous_judgments가 예상과 다른 타입: {type(previous_judgments)}"
                    )
                    previous_judgments = []

            # scenario와 victim_profile 타입 검사
            if isinstance(scenario, str):
                try:
                    scenario = json.loads(scenario)
                except json.JSONDecodeError:
                    logger.warning("[GuidanceGenerator] scenario JSON 파싱 실패")
                    scenario = {}

            if isinstance(victim_profile, str):
                try:
                    victim_profile = json.loads(victim_profile)
                except json.JSONDecodeError:
                    logger.warning(
                        "[GuidanceGenerator] victim_profile JSON 파싱 실패")
                    victim_profile = {}

            logger.info(f"[GuidanceGenerator] 처리된 파라미터:")
            logger.info(f"  extracted_case_id: {extracted_case_id}")
            logger.info(f"  round_no: {round_no}")
            logger.info(f"  scenario 타입: {type(scenario)}")
            logger.info(f"  victim_profile 타입: {type(victim_profile)}")
            logger.info(
                f"  previous_judgments 타입: {type(previous_judgments)}, 길이: {len(previous_judgments)}"
            )

            # 프롬프트 입력 구성
            prompt_input = {
                "scenario":
                json.dumps(scenario, ensure_ascii=False, indent=2),
                "victim_profile":
                json.dumps(victim_profile, ensure_ascii=False, indent=2),
                "round_no":
                round_no,
                "previous_judgments":
                json.dumps(previous_judgments, ensure_ascii=False, indent=2),
                "recent_logs":
                json.dumps(recent_logs, ensure_ascii=False, indent=2)
            }

            # LLM 호출
            chain = GUIDANCE_GENERATOR_PROMPT | self.llm
            response = chain.invoke(prompt_input)

            # 응답 파싱
            content = getattr(response, 'content', str(response))

            # JSON 추출 (```json 블록이 있을 경우)
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content,
                                   re.DOTALL)
            if json_match:
                content = json_match.group(1)

            guidance_result = json.loads(content)

            # 결과 검증 및 기본값 설정
            guidance_result.setdefault("selected_categories", [])
            guidance_result.setdefault("guidance_text", "기본 피싱 전략을 사용하세요.")
            guidance_result.setdefault("reasoning", "기본 지침 적용")
            guidance_result.setdefault("expected_effect", "일반적인 피싱 효과 기대")

            # 로깅
            self._log_guidance_generation(extracted_case_id, round_no,
                                          guidance_result, prompt_input)

            return guidance_result

        except Exception as e:
            logger.error(f"[GuidanceGenerator] 지침 생성 실패: {e}")
            import traceback
            logger.error(
                f"[GuidanceGenerator] 상세 오류: {traceback.format_exc()}")
            # 폴백 지침
            return {
                "selected_categories": ["B", "C"],
                "guidance_text": "긴급한 상황임을 강조하고 피해자의 불안감을 자극하여 빠른 대응을 유도하세요.",
                "reasoning": f"지침 생성 실패로 인한 기본 지침 적용 (오류: {str(e)})",
                "expected_effect": "기본적인 긴급성 및 감정적 압박 효과"
            }

    def _get_recent_logs(self,
                         db: Session,
                         case_id: str,
                         round_no: int,
                         limit: int = 10) -> List[Dict[str, Any]]:
        """최근 대화 로그를 조회합니다."""

        u = safe_uuid(case_id)
        if not u:
            logger.error(f"[GuidanceGenerator] UUID 변환 실패: {case_id}")
            return []
        case_uuid = u

        try:
            from app.db.models import ConversationLog
            from uuid import UUID

            # UUID 변환 안전성 확인
            try:
                case_uuid = UUID(case_id)
            except ValueError as e:
                logger.error(
                    f"[GuidanceGenerator] UUID 변환 실패: {case_id} - {e}")
                return []

            logs = (db.query(ConversationLog).filter(
                ConversationLog.case_id == case_uuid,
                ConversationLog.run <= round_no).order_by(
                    ConversationLog.run.desc(),
                    ConversationLog.turn_index.desc()).limit(limit).all())

            return [
                {
                    "run":
                    log.run,
                    "turn":
                    log.turn_index,
                    "role":
                    log.role,
                    "content":
                    log.content[:200] +
                    "..." if len(log.content) > 200 else log.content,
                    "created_at":
                    log.created_at.isoformat() if log.created_at else None
                } for log in reversed(logs)  # 시간순 정렬
            ]
        except Exception as e:
            logger.warning(f"[GuidanceGenerator] 로그 조회 실패: {e}")
            return []

    def _log_guidance_generation(self, case_id: str, round_no: int,
                                 result: Dict[str, Any], context: Dict[str,
                                                                       Any]):
        """지침 생성 과정을 상세히 로깅합니다."""
        try:
            # context 값들을 안전하게 파싱
            scenario_data = context.get("scenario", "{}")
            if isinstance(scenario_data, str):
                try:
                    scenario_data = json.loads(scenario_data)
                except json.JSONDecodeError:
                    scenario_data = {}

            victim_profile_data = context.get("victim_profile", "{}")
            if isinstance(victim_profile_data, str):
                try:
                    victim_profile_data = json.loads(victim_profile_data)
                except json.JSONDecodeError:
                    victim_profile_data = {}

            previous_judgments_data = context.get("previous_judgments", "[]")
            if isinstance(previous_judgments_data, str):
                try:
                    previous_judgments_data = json.loads(
                        previous_judgments_data)
                except json.JSONDecodeError:
                    previous_judgments_data = []

            log_data = {
                "case_id": case_id,
                "round_no": round_no,
                "timestamp": datetime.now().isoformat(),
                "generated_guidance": {
                    "categories": result.get("selected_categories", []),
                    "text": result.get("guidance_text", ""),
                    "reasoning": result.get("reasoning", ""),
                    "expected_effect": result.get("expected_effect", "")
                },
                "analysis_context": {
                    "scenario_type":
                    scenario_data.get("type", "unknown") if isinstance(
                        scenario_data, dict) else "unknown",
                    "victim_age_group":
                    (victim_profile_data.get("meta", {}).get(
                        "age_group", "unknown") if isinstance(
                            victim_profile_data, dict) else "unknown"),
                    "previous_rounds":
                    len(previous_judgments_data) if isinstance(
                        previous_judgments_data, list) else 0,
                    "recent_log_count":
                    len(context.get("recent_logs", []))
                }
            }

            logger.info("[GuidanceGeneration] %s",
                        json.dumps(log_data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"[_log_guidance_generation] 로깅 실패: {e}")
        # 로깅 실패해도 메인 로직에 영향 주지 않음


# ─────────────────────────────────────────────────────────
# 기존 admin tools에 추가할 새로운 도구
# ─────────────────────────────────────────────────────────


class GuidanceGenerationInput(BaseModel):
    case_id: str = Field(..., description="케이스 ID")
    round_no: int = Field(..., description="라운드 번호")
    scenario: Dict[str, Any] = Field(..., description="시나리오 정보")
    victim_profile: Dict[str, Any] = Field(..., description="피해자 프로필")
    previous_judgments: List[Dict[str, Any]] = Field(default=[],
                                                     description="이전 판정 결과")


def make_guidance_generation_tool(db: Session):
    """동적 지침 생성 도구를 생성합니다."""

    generator = DynamicGuidanceGenerator()

    @tool(
        "admin.generate_guidance",
        args_schema=SingleData,  # ← GuidanceGenerationInput에서 SingleData로 변경
        description="시나리오와 대화 상황을 분석하여 공격자를 위한 맞춤형 지침을 동적으로 생성합니다.")
    def generate_guidance(data: Any) -> Dict[str, Any]:
        payload = _unwrap(data)

        # 디버깅 로그 추가
        logger.info(
            f"[generate_guidance] 파싱된 payload 키들: {list(payload.keys())}")

        case_id = payload.get("case_id")
        round_no = payload.get("round_no")
        scenario = payload.get("scenario", {})
        victim_profile = payload.get("victim_profile", {})
        previous_judgments = payload.get("previous_judgments", [])

        # previous_judgment → previous_judgments 변환 (에이전트가 단수형으로 보낼 수 있음)
        if not previous_judgments and "previous_judgment" in payload:
            previous_judgments = [payload["previous_judgment"]]

        # case_id와 round_no 보정
        if not case_id:
            case_id = "temp_case_id"
            logger.warning("[generate_guidance] case_id 누락, 임시값 사용")

        if not round_no:
            round_no = 2
            logger.warning("[generate_guidance] round_no 누락, 기본값 사용")

        try:
            # 실제 지침 생성 시도
            result = generator.generate_guidance(
                db=db,
                case_id=str(case_id),
                round_no=int(round_no),
                scenario=scenario,
                victim_profile=victim_profile,
                previous_judgments=previous_judgments)

            return {
                "ok": True,
                "type": "A",
                "text": result.get("guidance_text", ""),
                "categories": result.get("selected_categories", []),
                "reasoning": result.get("reasoning", ""),
                "expected_effect": result.get("expected_effect", ""),
                "generation_method": "dynamic_analysis"
            }

        except Exception as e:
            logger.error(f"[admin.generate_guidance] 실행 실패: {e}")
            return {
                "ok": False,
                "error": str(e),
                "type": "A",
                "text": "긴급한 상황임을 강조하고 피해자의 불안감을 자극하여 빠른 대응을 유도하세요.",
                "generation_method": "fallback"
            }
