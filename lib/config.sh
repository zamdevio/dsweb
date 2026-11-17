#!/usr/bin/env bash
# lib/config.sh - portable config. Sourced, not executed.
#
# Precedence (highest wins):
#   1. process environment (CI / one-shot overrides)
#   2. ~/.config/dsweb/config.json   ← settings (port, api key, model, …)
#   3. repo .env (LEGACY, settings only — secrets ignored with a warning)
#   4. built-in defaults
#
# Secrets (DS_TOKEN / DS_COOKIE):
#   1. process env DS_TOKEN / DS_COOKIE
#   2. ~/.config/dsweb/auth.json     ← ONLY persisted secret store
#   NEVER from .env / config.json

DS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DS_ROOT

# ── XDG layout ───────────────────────────────────────────────
DS_CONFIG_DIR="${DS_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/dsweb}"
DS_DATA_DIR="${DS_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/dsweb}"
DS_AUTH_FILE="${DS_AUTH_FILE:-$DS_CONFIG_DIR/auth.json}"
DS_CONFIG_FILE="${DS_CONFIG_FILE:-$DS_CONFIG_DIR/config.json}"
DS_CACHE_DIR="${DS_CACHE_DIR:-$DS_DATA_DIR/cache}"
DS_COOKIE_JAR="${DS_COOKIE_JAR:-$DS_DATA_DIR/cookies.jar}"
export DS_CONFIG_DIR DS_DATA_DIR DS_AUTH_FILE DS_CONFIG_FILE DS_CACHE_DIR DS_COOKIE_JAR

ds_venv_python() {
  if [[ -x "$DS_ROOT/.venv/bin/python" ]]; then
    printf '%s' "$DS_ROOT/.venv/bin/python"
  else
    printf '%s' "${DS_PYTHON:-python3}"
  fi
}
DS_PYTHON="${DS_PYTHON:-$(ds_venv_python)}"
export DS_PYTHON

# shellcheck source=json.sh
source "$DS_ROOT/lib/json.sh"

# Keys that must never come from .env / config.json into the secret path.
_DS_SECRET_KEYS="DS_TOKEN DS_COOKIE DS_PASSWORD"

# ── load config.json into env (no secrets) ───────────────────
ds_load_config_json() {
  [[ -f "$DS_CONFIG_FILE" ]] || return 0
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" != *=* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    case " $_DS_SECRET_KEYS " in *" $key "*) continue ;; esac
    if [[ -z "${!key:-}" ]]; then
      export "$key=$val"
    fi
  done < <(
    "$DS_PYTHON" - "$DS_CONFIG_FILE" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)
for k, v in data.items():
    if not isinstance(k, str) or not k.startswith("DS_"):
        continue
    if v is None:
        continue
    if isinstance(v, bool):
        v = "true" if v else "false"
    else:
        v = str(v)
    # shell-safe single line
    print(f"{k}={v}")
PY
  )
}

# ── legacy .env (settings only) ──────────────────────────────
ds_load_env() {
  local file="${1:-$DS_ROOT/.env}"
  [[ -f "$file" ]] || return 1
  local line key val warned=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    case " $_DS_SECRET_KEYS " in
      *" $key "*)
        if [[ -n "$val" && $warned -eq 0 ]]; then
          # defer warning until log.sh may be loaded — stash
          DS_ENV_SECRET_WARN=1
          export DS_ENV_SECRET_WARN
          warned=1
        fi
        continue
        ;;
    esac
    if [[ -z "${!key:-}" ]]; then
      export "$key=$val"
    fi
  done < "$file"
}

ds_load_config_json
ds_load_env || true

# ── upstream defaults ────────────────────────────────────────
DS_BASE_URL="${DS_BASE_URL:-https://chat.deepseek.com}"
DS_API="${DS_API:-$DS_BASE_URL/api/v0}"
DS_CLIENT_VERSION="${DS_CLIENT_VERSION:-2.3.0}"
DS_IMPERSONATE="${DS_IMPERSONATE:-chrome131}"
export DS_BASE_URL DS_API DS_CLIENT_VERSION DS_IMPERSONATE

DS_USER_AGENT="${DS_USER_AGENT:-Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36}"
DS_CLIENT_LOCALE="${DS_CLIENT_LOCALE:-en_US}"
DS_CLIENT_TIMEZONE_OFFSET="${DS_CLIENT_TIMEZONE_OFFSET:-28800}"
export DS_USER_AGENT DS_CLIENT_LOCALE DS_CLIENT_TIMEZONE_OFFSET
DS_PROXY="${DS_PROXY:-}"
export DS_PROXY

DS_MODEL="${DS_MODEL:-deepseek-chat}"
DS_TIMEOUT="${DS_TIMEOUT:-600}"
DS_SYSTEM_PROMPT="${DS_SYSTEM_PROMPT:-}"
export DS_MODEL DS_TIMEOUT DS_SYSTEM_PROMPT

DS_HOST="${DS_HOST:-127.0.0.1}"
DS_PORT="${DS_PORT:-8787}"
DS_API_KEY="${DS_API_KEY:-sk-dsweb-change-me}"
DS_ALLOW_UNAUTHENTICATED="${DS_ALLOW_UNAUTHENTICATED:-false}"
export DS_HOST DS_PORT DS_API_KEY DS_ALLOW_UNAUTHENTICATED

ds_bool() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on|enabled) return 0 ;;
    *) return 1 ;;
  esac
}
DS_DEFAULT_THINKING="${DS_DEFAULT_THINKING:-false}"
DS_DEFAULT_SEARCH="${DS_DEFAULT_SEARCH:-false}"
export DS_DEFAULT_THINKING DS_DEFAULT_SEARCH

DS_SAVE_CHATS="${DS_SAVE_CHATS:-false}"
DS_TEMP_SESSIONS="${DS_TEMP_SESSIONS:-true}"
export DS_SAVE_CHATS DS_TEMP_SESSIONS

DS_WASM="${DS_WASM:-$DS_ROOT/lib/wasm/sha3_wasm_bg.wasm}"
export DS_WASM

DS_REQS_STAMP="${DS_REQS_STAMP:-$DS_ROOT/.venv/.dsweb-deps-stamp}"
export DS_REQS_STAMP

ds_ensure_dirs() {
  mkdir -p "$DS_CONFIG_DIR" "$DS_DATA_DIR" "$DS_CACHE_DIR" || return 1
}

ds_ensure_config_file() {
  ds_ensure_dirs
  if [[ ! -f "$DS_CONFIG_FILE" ]]; then
    "$DS_PYTHON" -c "import sys; sys.path.insert(0,'$DS_ROOT/lib'); from xdg_config import ensure_config_file; print(ensure_config_file())" >/dev/null
  fi
}

ds_api_key_is_weak() {
  case "${DS_API_KEY:-}" in
    ""|sk-dsweb-change-me|proxy|changeme|secret)
      return 0 ;;
    *)
      [[ ${#DS_API_KEY} -lt 8 ]] && return 0
      return 1 ;;
  esac
}
