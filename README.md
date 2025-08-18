# VoicePhish Simulator (VPSim)

보이스피싱 시뮬레이션을 위한 AI 기반 대화 시뮬레이터입니다.

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# Python 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 또는 conda 사용시
conda create -n vpsim python=3.11
conda activate vpsim
```

### 2. 백엔드 의존성 설치

```bash
# Python 패키지 설치
pip install -r requirements.txt

# 또는 개별 설치
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic pydantic-settings python-dotenv
```

### 3. 데이터베이스 설정

```bash
# PostgreSQL 데이터베이스 생성 (필요시)
sudo -u postgres createdb voicephish
sudo -u postgres createuser vpuser

# 환경변수 설정 (.env 파일 생성)
cat > .env << EOF
DATABASE_URL=postgresql+psycopg2://vpuser:password@localhost:5432/voicephish
APP_ENV=local
APP_NAME=VoicePhish Sim
MAX_OFFENDER_TURNS=10
MAX_VICTIM_TURNS=10
EOF
```

### 4. 데이터 시드 실행

```bash
# 데이터베이스 테이블 생성 및 샘플 데이터 삽입
python seed.py
```

### 5. 백엔드 서버 실행

```bash
# FastAPI 서버 실행 (포트 8000)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. 프론트엔드 실행

```bash
# 새 터미널에서
cd FE

# Node.js 의존성 설치
npm install

# 개발 서버 실행 (포트 5173)
npm run dev
```

## 🌐 접속 주소

- **프론트엔드**: http://localhost:5173
- **백엔드 API**: http://127.0.0.1:8000
- **API 문서**: http://127.0.0.1:8000/docs

## 📁 프로젝트 구조

```
VP/
├── app/                    # FastAPI 백엔드
│   ├── core/             # 설정 및 핵심 기능
│   ├── db/               # 데이터베이스 모델 및 세션
│   ├── routers/          # API 라우터
│   ├── services/         # 비즈니스 로직
│   └── schemas/          # Pydantic 스키마
├── FE/                   # React 프론트엔드
│   ├── src/              # 소스 코드
│   ├── public/           # 정적 파일
│   └── package.json      # Node.js 의존성
├── seeds/                # 샘플 데이터
├── requirements.txt       # Python 의존성
└── seed.py              # 데이터 시드 스크립트
```

## 🔧 주요 기능

### 시나리오 유형
- **기관 사칭형**: 수사기관, 금융기관 사칭
- **가족·지인 사칭**: 친척, 지인 사칭
- **대출사기형**: 저금리 대출 유도 후 사기

### 시뮬레이션 모드
- **AI 에이전트 없음**: 순수 AI 대화
- **AI 에이전트 사용**: 관리자 개입 시뮬레이션

## 🐛 문제 해결

### WebSocket 연결 오류
```bash
# Vite 설정에서 HMR 프로토콜 확인
# FE/vite.config.js의 hmr 설정이 올바른지 확인
```

### 데이터베이스 연결 오류
```bash
# PostgreSQL 서비스 상태 확인
sudo systemctl status postgresql

# 데이터베이스 연결 테스트
psql -h localhost -U vpuser -d voicephish
```

### 포트 충돌
```bash
# 사용 중인 포트 확인
netstat -tlnp | grep -E "(8000|5173)"

# 프로세스 종료
pkill -f "uvicorn app.main:app"
pkill -f "vite --host 0.0.0.0"
```

## 📊 샘플 데이터

- **공격자(시나리오)**: 8개
- **피해자**: 6개
- **대화 턴**: 최대 200턴

## 🚀 배포

### 프로덕션 빌드
```bash
# 프론트엔드 빌드
cd FE
npm run build

# 백엔드 실행 (프로덕션 모드)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📝 라이선스

이 프로젝트는 연구 및 교육 목적으로 제작되었습니다.