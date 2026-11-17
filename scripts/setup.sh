#!/usr/bin/env bash
# scripts/setup.sh — idempotent bootstrap for a fresh machine / clone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=../lib/config.sh
source "$ROOT/lib/config.sh"
# shellcheck source=../lib/log.sh
source "$ROOT/lib/log.sh"

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

if have_cmd curl; then step_ok "curl"
else step_fail "curl missing"; fi

# jq is optional — auth/CLI fall back to python. Offer install if missing.
if have_cmd jq; then
  step_ok "jq"
else
  log_warn "jq missing (optional — python JSON fallback is used)"
  install_jq=n
  if [[ -t 0 ]]; then
    printf 'Install jq now? [y/N] ' >&2
    read -r install_jq || true
  elif [[ "${DS_SETUP_INSTALL_JQ:-}" == "1" ]]; then
    install_jq=y
  fi
  case "$(printf '%s' "$install_jq" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
      if have_cmd apt-get && [[ "$(id -u)" -eq 0 ]]; then
        apt-get install -y jq && step_ok "jq installed (apt)"
      elif have_cmd apt-get; then
        if sudo -n true 2>/dev/null; then
          sudo apt-get install -y jq && step_ok "jq installed (apt/sudo)"
        else
          log_warn "run: sudo apt-get install -y jq"
        fi
      elif have_cmd brew; then
        brew install jq && step_ok "jq installed (brew)"
      elif have_cmd dnf; then
        sudo dnf install -y jq && step_ok "jq installed (dnf)"
      elif have_cmd pacman; then
        sudo pacman -S --noconfirm jq && step_ok "jq installed (pacman)"
      else
        log_warn "no known package manager — install jq yourself, or ignore (python fallback works)"
      fi
      ;;
    *)
      step_skip "jq not installed (auth works without it)"
      ;;
  esac
fi

# ── XDG dirs + config.json ────────────────────────────────────
ds_ensure_dirs
ds_ensure_config_file
step_ok "XDG config=$DS_CONFIG_DIR data=$DS_DATA_DIR"
step_ok "config.json → $DS_CONFIG_FILE"

# Migrate leftover .env secrets → auth.json, settings → config.json
if [[ -f "$ROOT/.env" ]]; then
  if grep -qE '^DS_TOKEN=.+' "$ROOT/.env" 2>/dev/null; then
    log_info "migrating DS_TOKEN from .env → auth.json"
    tok="$(grep -E '^DS_TOKEN=' "$ROOT/.env" | head -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//')"
    if [[ -n "$tok" ]]; then
      existing="$(ds_json_get_file "$DS_AUTH_FILE" '.token //empty' 2>/dev/null || true)"
      if [[ -z "$existing" ]]; then
        ts="$(date -u +%FT%TZ)"
        printf '%s\n' "$(ds_json_build "token=$tok" "cookie=" "email=" "saved_at=$ts")" \
          | ds_json_write_file "$DS_AUTH_FILE" 600
        step_ok "token → $DS_AUTH_FILE"
      fi
    fi
  fi
  # Non-secret DS_* still in .env → config.json (don't clobber existing keys)
  "$DS_PYTHON" - "$ROOT/.env" "$DS_CONFIG_FILE" <<'PY' && step_ok "settings synced .env → config.json" || true
import json, sys
from pathlib import Path
env_path, cfg_path = Path(sys.argv[1]), Path(sys.argv[2])
secrets = {"DS_TOKEN", "DS_COOKIE", "DS_PASSWORD", "DS_EMAIL"}
cfg = {}
if cfg_path.is_file():
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        cfg = {}
changed = False
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    k, v = k.strip(), v.strip().strip("\"'")
    if not k.startswith("DS_") or k in secrets or not v:
        continue
    if k not in cfg or cfg.get(k) in (None, "", "sk-dsweb-change-me"):
        if cfg.get(k) != v:
            cfg[k] = v
            changed = True
if changed:
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY
  sed -i -E \
    -e 's/^(DS_TOKEN|DS_COOKIE|DS_PASSWORD)=/# moved to auth.json — \1=/' \
    -e 's/^(DS_API_KEY|DS_HOST|DS_PORT|DS_MODEL|DS_SAVE_CHATS)=/# moved to config.json — \1=/' \
    "$ROOT/.env" 2>/dev/null || true
fi

# .env is optional legacy — we no longer require it
if [[ -f "$ROOT/.env" ]]; then
  step_skip ".env present (legacy settings only; prefer: ./dsweb config)"
else
  step_skip ".env not required — use ./dsweb config / auth.json"
fi

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

if [[ -f "$DS_WASM" ]]; then
  step_ok "pow wasm present"
else
  log_warn "pow wasm missing at $DS_WASM (PoW will fail)"
fi

if have_cmd cloudflared; then
  step_ok "cloudflared on PATH"
else
  step_skip "cloudflared not installed (optional)"
fi

if [[ -f "$DS_AUTH_FILE" ]] || [[ -n "${DS_TOKEN:-}" ]]; then
  step_ok "auth credential present (auth.json or DS_TOKEN env)"
else
  log_warn "no auth yet — next: ./dsweb token <userToken from chat.deepseek.com>"
fi

echo
log_ok "setup done (did=$DID skipped=$SKIPPED)"
log_info "config: ./dsweb config          # ~/.config/dsweb/config.json"
log_info "auth:   ./dsweb token           # → ~/.config/dsweb/auth.json"
log_info "next:   ./dsweb doctor && ./dsweb whoami && ./dsweb serve"
