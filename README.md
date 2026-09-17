# VishBox — AI Agent 기반 보이스피싱 시뮬레이션 프레임워크

> **IEEE Access (SCIE) 게재 논문의 공식 구현체**
> 실제 대화 데이터 없이도 보이스피싱 진행 과정을 재현해, 예방 교육과 행동 보안 연구에 쓸 수 있는 시뮬레이터

[![Paper](https://img.shields.io/badge/IEEE%20Access-10.1109%2FACCESS.2026.3667823-00629B)](https://ieeexplore.ieee.org/document/11411806)
[![License](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey)](https://creativecommons.org/licenses/by/4.0/)

**Y. Yang**, D. Choi, Y. Hong, J.-W. Park, J.-Y. Yu, H.-D. Kim, and S. Park,
"VishBox: An AI-Agent-Based Adaptive Voice Phishing Simulation Framework for Cybersecurity Education,"
*IEEE Access*, vol. 14, pp. 39672–39686, 2026. — **제1저자**

한림대학교 소프트웨어학부 · 지능형의사결정시스템 연구실 (LIT LAB) · 경찰청 KIPoT 과제 (RS-2025-02218280)

> 후속 연구 **VishBox v2** (ACL 2026 Industry Track, Oral) → [yoonmo01/VP2](https://github.com/yoonmo01/VP2)

---

## 📌 왜 만들었나

보이스피싱 예방 교육은 정형화된 사례에 머물러 있습니다. 실제 범죄는 피해자의 반응에 따라 수법이 실시간으로 바뀌는데, 교육 자료는 고정된 시나리오를 쓰기 때문입니다. 실제 통화 녹취는 수사·privacy 문제로 연구에 쓸 수 없습니다.

VishBox는 **공격자·피해자·관리자 3개 LLM Agent**로 이 상호작용을 윤리적으로 안전하게 재현합니다. 생성된 대화는 피해자 특성에 따라 다르게 전개되며, 각 턴마다 위험도가 평가됩니다.

---

## 📊 검증 결과

| 항목 | 결과 |
|---|---|
| **현실성 검증** | 참여자 **102명**이 실제 녹취 대화와 생성 대화를 구분한 정답률 **48.04%** — 우연 수준(50%)과 차이가 없음 |
| **연령별 취약성 분포** | 실제 피해 통계의 연령대별 패턴과 전반적으로 일치 |
| **기관사칭 시나리오** | 시뮬레이션 성공률 80% 이상 (20대 초반 대상, 실제 통계와 동일한 경향) |
| **가족사칭 시나리오** | 60대 이상 대상 취약성 100% |
| **턴 단위 위험도** | 사람이 매긴 위험도 평가와 시스템의 턴 단위 추정치가 유사하게 움직임 |
| **성격 기반 위험** | 사건 통계에는 거의 안 잡히는 성격 특성 기반 위험 시나리오를 추가로 발견 |

> 48.04%는 "사람이 생성 대화를 진짜와 구분하지 못했다"는 뜻으로, 시뮬레이터의 현실성을 뒷받침하는 핵심 수치입니다.

---

## 🏗️ 시스템 구조

중앙 **Manager Agent**가 3단계를 순차적으로 관리합니다.

```
① 사용자 설정            ② LLM 대화 시뮬레이션          ③ 분석 · 반복 평가
   시나리오 유형 선택         공격자 Agent ↔ 피해자 Agent       턴 단위 위험도 채점
   피해자 프로파일 구성        (MCP 격리 환경에서 실행)          맞춤형 예방 전략 도출
        │                          │                           │
        └──── Prompt Builder ──────┴──── 구조화 로그 반환 ───────┘
                            Manager Agent
```

### 피해자 프로파일

국내 실증 연구를 기반으로 3개 축을 조합합니다.

| 축 | 내용 |
|---|---|
| **인구통계** | 연령대별 특성 (20대 / 30–40대 / 60대 이상) |
| **디지털 금융 리터러시** | 지식 · 행동 · 태도 3개 하위 차원, 국가 조사 데이터로 보정 |
| **성격** | OCEAN(Big Five) 5요인 |

이 값들이 확인 전화를 걸 확률, 절차 검증 성향, 감정적 취약성에 반영됩니다.

### 시나리오 3종

| 유형 | 수법 | 주 표적 |
|---|---|---|
| **대출빙자형** | 저금리 대환대출 미끼 | 30–40대 |
| **기관사칭형** | 검찰·금융감독원 사칭, 긴급성 압박 | 20대 초반 |
| **가족사칭형** | 가족 위급상황 조작, 감정적 패닉 유도 | 60대 이상 |

모든 시나리오는 **접촉 → 신뢰 구축 → 통제 → 갈취** 4단계 구조를 따릅니다. 이 구조와 세부 수법은 경찰청 발간 *월간 피싱* 범죄분석 보고서에 근거합니다.

### MCP 기반 대화 격리

대화 생성은 **MCP 서버(`vp_mcp/`)** 안에서 실행되며, Manager Agent를 포함한 외부 Agent 시스템과 분리됩니다. 공격자·피해자 모델은 시뮬레이션 내부에서만 상호작용하고, 밖으로는 표준화된 프롬프트 교환과 구조화 로그만 오갑니다. 재현 가능한 시뮬레이션과 통제된 실험을 위한 설계입니다.

### 행동 메타데이터

매 턴마다 피해자 발화에 내부 상태가 함께 기록됩니다.

```json
{
  "utterance": "음, 일단 은행 공식 번호로 확인해볼게요.",
  "is_convinced": 2,
  "thoughts": "계속 같은 말만 반복하네. 뭔가 이상한데, 은행 공식 번호로 먼저 확인하는 게 낫겠다."
}
```

Manager Agent는 이 주석을 읽어 라운드별 위험 상태를 갱신합니다.

---

## 🛠 기술 스택

| 계층 | 기술 |
|---|---|
| **Backend** | FastAPI · SQLAlchemy · Pydantic |
| **Agent** | MCP 서버 (`vp_mcp`) · ReAct 오케스트레이터 · Tavily 웹 검색 |
| **LLM** | GPT-4.1-mini (공격자) · Gemini 2.5 Flash Lite / GPT (피해자) · o4-mini (관리자) |
| **DB** | PostgreSQL |
| **Frontend** | React · Vite |
| **기타** | TTS 합성 · 대화 스플리터 |

---

## 🚀 실행 방법

### 1. PostgreSQL 준비 (최초 1회)

**옵션 A — 로컬 설치**

```bash
# Linux (systemd)
sudo systemctl enable --now postgresql
sudo -u postgres psql -c "CREATE USER vpuser WITH PASSWORD '<비밀번호>';"
sudo -u postgres psql -c "CREATE DATABASE voicephish OWNER vpuser;"
```

```bash
# macOS (Homebrew)
brew services start postgresql
psql postgres -c "CREATE USER vpuser WITH PASSWORD '<비밀번호>';"
psql postgres -c "CREATE DATABASE voicephish OWNER vpuser;"
```

Windows: PostgreSQL 설치 후 *SQL Shell (psql)* 에서 위 SQL 두 줄을 실행합니다.

**옵션 B — Docker**

```bash
docker run -d --name vpsim-postgres \
  -e POSTGRES_USER=vpuser \
  -e POSTGRES_PASSWORD=<비밀번호> \
  -e POSTGRES_DB=voicephish \
  -p 5432:5432 \
  postgres:16
```

연결 확인:

```bash
psql -h localhost -U vpuser -d voicephish -c "\dt"
```

> 처음에는 테이블이 비어 있는 게 정상입니다. 실행 스크립트가 생성·시드합니다.

### 2. 환경변수 설정

`.env` 를 만들고 아래를 채웁니다. **프론트엔드는 별도 `.env`가 필요 없습니다** (`window.location.origin` 기반).

```ini
# ── Database ──────────────────────────
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/voicephish

# ── LLM Keys ──────────────────────────
OPENAI_API_KEY=sk-xxxx
GOOGLE_API_KEY=AIza-xxxx      # 피해자 모델을 Gemini로 쓸 때만 필요

# ── App ───────────────────────────────
APP_ENV=dev
API_PREFIX=/api

# 역할별 모델
ATTACKER_MODEL=gpt-4.1-mini
VICTIM_MODEL=gemini-2.5-flash-lite
ADMIN_MODEL=o4-mini

VICTIM_PROVIDER=openai        # openai | gemini

# (선택) 라운드 제한
MAX_OFFENDER_TURNS=15
MAX_VICTIM_TURNS=15
```

> ⚠️ 실제 키와 비밀번호는 커밋하지 마세요.

### 3. 실행

```bash
./run-local.sh
```

의존성 설치 → DB 시드 → 백엔드·프론트엔드 기동까지 한 번에 처리합니다.

| 대상 | 주소 |
|---|---|
| 프론트엔드 | http://localhost:5173 |
| 백엔드 API | http://127.0.0.1:8000 |
| API 문서 | http://127.0.0.1:8000/docs |

<details>
<summary>개별 실행 (수동)</summary>

```bash
# 가상환경
python3 -m venv venv && source venv/bin/activate
# 또는: conda create -n vpsim python=3.11 && conda activate vpsim

pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000

# 프론트엔드
cd FE && npm install && npm run dev
```

</details>

<details>
<summary>문제 해결</summary>

```bash
# DB 연결 확인
sudo systemctl status postgresql
psql -h localhost -U vpuser -d voicephish

# 포트 충돌
netstat -tlnp | grep -E "(8000|5173)"
pkill -f "uvicorn app.main:app"
pkill -f "vite --host 0.0.0.0"
```

</details>

---

## 📁 프로젝트 구조

```
VP/
├── app/                          # FastAPI 백엔드
│   ├── core/                     # 설정 · 로깅
│   ├── db/                       # 모델 · 세션
│   ├── routers/                  # API 라우터 (simulator, agent, mcp, tts ...)
│   ├── services/
│   │   ├── agent/                # Manager Agent · MCP/ReAct 오케스트레이터 · 도구
│   │   ├── prompt_builder.py     # 프롬프트 구성
│   │   └── simulation.py         # 시뮬레이션 진행 로직
│   └── schemas/                  # Pydantic 스키마
├── vp_mcp/mcp_server/            # MCP 서버 (대화 시뮬레이터 격리 환경)
├── FE/                           # React 프론트엔드
├── seeds/                        # 공격자 8 · 피해자 6 시드 데이터
├── run-local.sh                  # 통합 실행 스크립트
└── seed.py                       # DB 시드
```

**샘플 데이터** — 공격자(시나리오) 8개 · 피해자 6개 · 대화 턴 최대 200턴

---

## 📖 인용

```bibtex
@article{yang2026vishbox,
  title   = {VishBox: An AI-Agent-Based Adaptive Voice Phishing Simulation
             Framework for Cybersecurity Education},
  author  = {Yang, Yoonmo and Choi, Daon and Hong, Yunyi and Park, Jee-Won
             and Yu, Jae-Yong and Kim, Hee-Dou and Park, Sungmi},
  journal = {IEEE Access},
  volume  = {14},
  pages   = {39672--39686},
  year    = {2026},
  doi     = {10.1109/ACCESS.2026.3667823}
}
```

---

## ⚖️ 윤리 및 라이선스

본 시스템은 **예방 교육과 보안 연구 목적**으로만 제작되었습니다. 생성되는 대화는 전부 합성 데이터이며, 실제 피해자나 통화 녹취를 포함하지 않습니다. 실제 사기 행위에 활용하는 것을 금합니다.

논문은 CC BY 4.0으로 공개되어 있습니다.
