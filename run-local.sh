#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"     # .../VP
SETUP_DIR="$ROOT_DIR/.setup"
VENV_DIR="$ROOT_DIR/../.venv"
FE_DIR="$ROOT_DIR/FE"

mkdir -p "$SETUP_DIR"

API_PORT=${API_PORT:-8000}
FE_PORT=${FE_PORT:-5173}
RUN_INSTALL=false
RUN_SEED=true

# ---- args ----
for arg in "$@"; do
  case "$arg" in
    --install) RUN_INSTALL=true ;;
    --no-seed) RUN_SEED=false ;;
  esac
done

echo "[INFO] Workdir : $ROOT_DIR"
echo "[INFO] Venv    : $VENV_DIR"

# ---- 1) pick system python ----
SYS_PY=""
if command -v python >/dev/null 2>&1; then SYS_PY="python"
elif command -v python3 >/dev/null 2>&1; then SYS_PY="python3"
elif command -v py >/dev/null 2>&1; then SYS_PY="py -3"; fi
if [[ -z "$SYS_PY" ]]; then echo "[ERROR] python not found"; exit 1; fi

# ---- 2) ensure venv ----
PY=""
if [[ -x "$VENV_DIR/bin/python" ]]; then
  PY="$VENV_DIR/bin/python"
elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then
  PY="$VENV_DIR/Scripts/python.exe"
else
  echo "[SETUP] Creating venv at $VENV_DIR"
  $SYS_PY -m venv "$VENV_DIR" || { command -v py >/dev/null 2>&1 && py -3 -m venv "$VENV_DIR" || true; }
  if [[ -x "$VENV_DIR/bin/python" ]]; then PY="$VENV_DIR/bin/python"
  elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then PY="$VENV_DIR/Scripts/python.exe"
  else echo "[ERROR] venv python not found"; exit 1; fi
fi
echo "[INFO] Python : $("$PY" -V 2>&1)"

# ---- 3) backend deps (install on first run or if changed) ----
REQ="$ROOT_DIR/requirements.txt"
REQ_SNAP="$SETUP_DIR/requirements.snapshot"
NEED_PIP=false
if $RUN_INSTALL; then
  NEED_PIP=true
elif [[ ! -f "$REQ_SNAP" ]]; then
  NEED_PIP=true
elif [[ -f "$REQ" ]] && ! cmp -s "$REQ" "$REQ_SNAP"; then
  NEED_PIP=true
fi

if $NEED_PIP; then
  if [[ -f "$REQ" ]]; then
    echo "[SETUP] Installing backend deps from requirements.txt ..."
    # pip가 깨져있을 수 있어 ensurepip로 복구
    if ! "$PY" -m pip --version >/dev/null 2>&1; then
      "$PY" -m ensurepip --upgrade
      "$PY" -m pip install --upgrade --force-reinstall --no-cache-dir pip setuptools wheel
    fi
    "$PY" -m pip install -r "$REQ" --no-cache-dir --disable-pip-version-check
    cp "$REQ" "$REQ_SNAP"
  else
    echo "[WARN] requirements.txt not found. Skipping backend install."
  fi
else
  echo "[SKIP] Backend deps up-to-date."
fi

# ---- 4) frontend deps (install on first run or if changed) ----
PKG_LOCK="$FE_DIR/package-lock.json"
PKG_SNAP="$SETUP_DIR/package-lock.snapshot"
NEED_NPM=false
if $RUN_INSTALL; then
  NEED_NPM=true
elif [[ ! -d "$FE_DIR/node_modules" ]]; then
  NEED_NPM=true
elif [[ -f "$PKG_LOCK" ]] && { [[ ! -f "$PKG_SNAP" ]] || ! cmp -s "$PKG_LOCK" "$PKG_SNAP"; }; then
  NEED_NPM=true
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm is required. Install Node.js first (https://nodejs.org/)."
  exit 1
fi

if $NEED_NPM; then
  echo "[SETUP] Installing frontend deps ..."
  pushd "$FE_DIR" >/dev/null
  if [[ -f "package-lock.json" ]]; then npm ci; else npm install; fi
  popd >/dev/null
  [[ -f "$PKG_LOCK" ]] && cp "$PKG_LOCK" "$PKG_SNAP" || true
else
  echo "[SKIP] Frontend deps up-to-date."
fi

# ---- 5) seed (idempotent recommended) ----
if $RUN_SEED; then
  echo "[SEED] Running: python -m seed"
  "$PY" -m seed
else
  echo "[SKIP] Seed step skipped (--no-seed)."
fi

# ---- 6) run servers ----
echo "[RUN] Backend docs  → http://localhost:${API_PORT}/docs"
echo "[RUN] Frontend → http://localhost:${FE_PORT}/"
echo "------------------------------------------------------------"

# backend
pushd "$ROOT_DIR" >/dev/null
"$PY" -m uvicorn app.main:app --reload --port "$API_PORT" &
BACK_PID=$!
popd >/dev/null

# frontend
pushd "$FE_DIR" >/dev/null
npm run dev -- --port "$FE_PORT" &
FRONT_PID=$!
popd >/dev/null

trap 'echo; echo "[STOP] shutting down..."; kill $BACK_PID $FRONT_PID 2>/dev/null || true; wait $BACK_PID $FRONT_PID 2>/dev/null || true; echo "[STOP] done";' INT TERM

wait
