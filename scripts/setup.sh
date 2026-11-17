#!/usr/bin/env bash
# scripts/setup.sh — idempotent bootstrap for a fresh machine / clone.
# Skips work that's already done. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=../lib/config.sh
source "$ROOT/lib/config.sh"
# shellcheck source=../lib/log.sh
source "$ROOT/lib/log.sh"

NEED_PY=()
SKIPPED=0
DID=0

have_cmd() { command -v "$1" >/dev/null 2>&1; }

step_ok() { log_ok "$*"; DID=$((DID + 1)); }
step_skip() { log_info "skip: $*"; SKIPPED=$((SKIPPED + 1)); }
step_fail() { log_err "$*"; exit 1; }

log_info "dsweb setup (root=$ROOT)"

# ── system tools ──────────────────────────────────────────────
if have_cmd python3; then
  step_ok "python3 $(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
else
  step_fail "python3 missing — install Python 3.10+"
fi

if have_cmd jq; then step_ok "jq"
else NEED_PY+=("jq"); log_warn "jq missing (needed for CLI JSON)"; fi

if have_cmd curl; then step_ok "curl"
else step_fail "curl missing"; fi

# ── .env ──────────────────────────────────────────────────────
if [[ -f "$ROOT/.env" ]]; then
  step_skip ".env already present"
else
  if [[ -f "$ROOT/.env.example" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    step_ok "wrote .env from .env.example — edit DS_TOKEN / DS_API_KEY"
  else
    step_fail ".env.example missing"
  fi
fi

# ── XDG dirs ──────────────────────────────────────────────────
ds_ensure_dirs
step_ok "XDG dirs config=$DS_CONFIG_DIR data=$DS_DATA_DIR"

# ── venv ──────────────────────────────────────────────────────
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  step_skip "venv exists ($ROOT/.venv)"
else
  log_info "creating .venv"
  python3 -m venv "$ROOT/.venv"
  step_ok "venv created"
fi
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

# ── deps ──────────────────────────────────────────────────────
REQS="$ROOT/requirements.txt"
STAMP="$ROOT/.venv/.dsweb-deps-stamp"
REQ_HASH="$(cksum "$REQS" 2>/dev/null | awk '{print $1"-"$2}')"
PREV_HASH="$(cat "$STAMP" 2>/dev/null || true)"

need_install=0
if [[ ! -f "$STAMP" ]]; then
  need_install=1
elif [[ "$REQ_HASH" != "$PREV_HASH" ]]; then
  need_install=1
  log_info "requirements.txt changed — reinstalling"
else
  # verify imports even if stamp matches
  if ! "$PY" -c 'import curl_cffi, wasmtime, fastapi, uvicorn' 2>/dev/null; then
    need_install=1
    log_warn "stamp ok but imports failed — reinstalling"
  fi
fi

if [[ $need_install -eq 0 ]]; then
  step_skip "python deps already installed"
else
  log_info "installing python deps"
  "$PIP" install --upgrade pip >/dev/null
  "$PIP" install -r "$REQS"
  printf '%s\n' "$REQ_HASH" > "$STAMP"
  step_ok "python deps installed"
fi

# ── wasm present ──────────────────────────────────────────────
if [[ -f "$DS_WASM" ]]; then
  step_ok "pow wasm present"
else
  log_warn "pow wasm missing at $DS_WASM (PoW will fail)"
fi

# ── optional: cloudflared hint ────────────────────────────────
if have_cmd cloudflared; then
  step_ok "cloudflared on PATH"
else
  step_skip "cloudflared not installed (optional; ./dsweb cloudflared can auto-install)"
fi

# ── auth hint ─────────────────────────────────────────────────
if [[ -f "$DS_AUTH_FILE" ]] || [[ -n "${DS_TOKEN:-}" ]]; then
  step_ok "auth credential present (file or DS_TOKEN)"
else
  log_warn "no auth yet — next: ./dsweb token <userToken from chat.deepseek.com localStorage>"
fi

echo
log_ok "setup done (did=$DID skipped=$SKIPPED)"
log_info "next:  ./dsweb doctor"
log_info "auth:  ./dsweb token   # paste userToken"
log_info "try:   ./dsweb whoami && ./dsweb ask 'hi'"
