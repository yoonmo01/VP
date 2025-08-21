#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"     # .../VP
VENV_DIR="$ROOT_DIR/../.venv"
FE_DIR="$ROOT_DIR/FE"

echo "[INFO] Shell    : $SHELL"
echo "[INFO] Workdir  : $ROOT_DIR"
echo "[INFO] Venv path: $VENV_DIR"

# ── 1) 시스템 파이썬 찾기 ─────────────────────────────────────────
SYS_PY=""
if command -v python >/dev/null 2>&1; then
  SYS_PY="python"
elif command -v python3 >/dev/null 2>&1; then
  SYS_PY="python3"
elif command -v py >/dev/null 2>&1; then
  SYS_PY="py -3"
fi
if [[ -z "$SYS_PY" ]]; then
  echo "[ERROR] python 실행 파일을 찾을 수 없습니다." >&2
  exit 1
fi
echo "[INFO] Using Python launcher: $SYS_PY"

# ── 2) venv 생성/결정 ─────────────────────────────────────────────
PY=""
if [[ -x "$VENV_DIR/bin/python" ]]; then
  PY="$VENV_DIR/bin/python"
elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
  PY="$VENV_DIR/Scripts/python.exe"
else
  echo "[SETUP] Creating venv: $VENV_DIR"
  $SYS_PY -m venv "$VENV_DIR"
  # 실패 시 Windows 런처로 재시도
  if [[ ! -x "$VENV_DIR/bin/python" && ! -x "$VENV_DIR/Scripts/python.exe" ]]; then
    if command -v py >/dev/null 2>&1; then
      py -3 -m venv "$VENV_DIR"
    fi
  fi
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    PY="$VENV_DIR/bin/python"
  elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
    PY="$VENV_DIR/Scripts/python.exe"
  else
    echo "[ERROR] venv 파이썬을 찾을 수 없습니다: $VENV_DIR" >&2
    exit 1
  fi
fi
echo "[INFO] Venv Python: $PY"
"$PY" -V

# ── 3) 백엔드 의존성 설치 ────────────────────────────────────────
REQ_TXT=""
if [[ -f "$ROOT_DIR/requirements.txt" ]]; then
  REQ_TXT="$ROOT_DIR/requirements.txt"
elif [[ -f "$ROOT_DIR/requirment.txt" ]]; then
  REQ_TXT="$ROOT_DIR/requirment.txt"   # 오타 파일명도 지원
fi

if [[ -n "$REQ_TXT" ]]; then
  echo "[SETUP] Upgrade pip & install deps: $REQ_TXT"
  "$PY" -m pip install -U pip
  "$PY" -m pip install -r "$REQ_TXT"
else
  echo "[WARN] requirements.txt(또는 requirment.txt)가 없어 설치를 건너뜁니다."
fi

# ── 4) 프론트 의존성 설치 ────────────────────────────────────────
if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm 이 필요합니다. Node.js 설치 후 다시 실행하세요." >&2
  exit 1
fi

pushd "$FE_DIR" >/dev/null
if [[ -d "node_modules" ]]; then
  echo "[SETUP] node_modules 존재 → 설치 건너뜀"
else
  if [[ -f "package-lock.json" ]]; then
    echo "[SETUP] npm ci"
    npm ci
  else
    echo "[SETUP] npm install"
    npm install
  fi
fi
popd >/dev/null

# ── 5) SEED (DB 테이블 생성/시드) ────────────────────────────────
echo "[SEED] python -m app.db.seed"
"$PY" -m app.db.seed

# ── 6) 서버 실행 (백엔드 & 프론트) ───────────────────────────────
API_PORT=${API_PORT:-8000}
FE_PORT=${FE_PORT:-5173}

echo "[RUN] Starting backend (uvicorn) ..."
pushd "$ROOT_DIR" >/dev/null
"$PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$API_PORT" &
BACK_PID=$!
popd >/dev/null

echo "[RUN] Starting frontend (Vite) ..."
pushd "$FE_DIR" >/dev/null
npm run dev -- --port "$FE_PORT" &
FRONT_PID=$!
popd >/dev/null

trap 'echo; echo "[STOP] 종료 중..."; kill $BACK_PID $FRONT_PID 2>/dev/null || true; wait $BACK_PID $FRONT_PID 2>/dev/null || true; echo "[STOP] 종료 완료";' INT TERM

echo "------------------------------------------------------------"
echo "API     → http://localhost:${API_PORT}/docs"
echo "Frontend→ http://localhost:${FE_PORT}/"
echo "Ctrl+C 로 종료합니다."
echo "------------------------------------------------------------"

wait
