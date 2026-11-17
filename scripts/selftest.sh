#!/usr/bin/env bash
# scripts/selftest.sh — offline checks (pow, SSE, auth helpers, client/tools).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$ROOT/lib/config.sh"
source "$ROOT/lib/log.sh"
source "$ROOT/lib/http.sh"
source "$ROOT/core/chat.sh"
source "$ROOT/core/auth.sh"

pass=0; fail=0
check() {
  if [[ "$2" == "$3" ]]; then log_ok "PASS: $1"; pass=$((pass+1));
  else log_err "FAIL: $1 (want '$2' got '$3')"; fail=$((fail+1)); fi
}

# 1. PoW
chal='{"algorithm":"DeepSeekHashV1","challenge":"b0000b22959bad0cc1ecbbfa07f97191b20332fa10d7341ff9c7ba6e7ed927f1","salt":"dde3ed472be5a2494ee0","difficulty":144000,"expire_at":1777057596443,"signature":"test","target_path":"/api/v0/chat/completion"}'
answer="$(printf '%s' "$chal" | "$DS_PYTHON" "$ROOT/lib/pow.py" | base64 -d | jq -r '.answer')"
check "pow solves challenge" "58033" "$answer"

# 2. SSE
got="$(printf 'data: {"choices":[{"delta":{"content":"Hello"}}]}\ndata: {"choices":[{"delta":{"content":" world"}}]}\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n' | _ds_parse_sse)"
check "sse parser legacy" "Hello world" "$got"
got="$(printf '%s\n' \
  'data: {"v":{"response":{"fragments":[{"type":"RESPONSE","content":"C"}]}}}' \
  'data: {"p":"response/fragments/-1/content","o":"APPEND","v":"ats"}' \
  'data: {"v":"!"}' \
  'data: {"p":"response/status","o":"SET","v":"FINISHED"}' \
  | _ds_parse_sse)"
check "sse parser fragments" "Cats!" "$got"

# 3. Cookie extract
tok="$(ds_extract_token_from_cookie 'foo=bar; userToken=abc.def.ghi; other=1')"
check "cookie token extract" "abc.def.ghi" "$tok"

# 4. Token normalize (temp auth file — never clobber real creds)
DS_AUTH_FILE="$(mktemp)"
trap 'rm -f "$DS_AUTH_FILE"' EXIT
DS_TOKEN=""; ds_auth_set_token "Bearer xyz.123" 2>/dev/null
check "token strips Bearer" "xyz.123" "${DS_TOKEN:-}"
DS_TOKEN=""; ds_auth_set_token '{"value":"real.tok","__version":"0"}' 2>/dev/null
check "token unwraps json" "real.tok" "${DS_TOKEN:-}"
unset DS_TOKEN

# 5. HTTP status survives subshell
mkdir -p "$DS_CACHE_DIR"
printf '200' > "$DS_HTTP_STATUS_FILE"
_discard="$(
  DS_LAST_CODE=999
  printf '418' > "$DS_HTTP_STATUS_FILE"
)"
check "http code survives subshell" "418" "$(ds_http_code)"

# 6. XDG defaults point at dsweb
case "$DS_CONFIG_DIR" in */dsweb) check "config dir is dsweb" "ok" "ok" ;;
  *) check "config dir is dsweb" "*/dsweb" "$DS_CONFIG_DIR" ;; esac
case "$DS_DATA_DIR" in */dsweb) check "data dir is dsweb" "ok" "ok" ;;
  *) check "data dir is dsweb" "*/dsweb" "$DS_DATA_DIR" ;; esac

# 7. client + tools
if "$DS_PYTHON" - <<'PY' 2>/dev/null
import sys
from pathlib import Path
sys.path.insert(0, str(Path("lib").resolve()))
from client import DeepSeekClient
from client.tools import parse_tool_calls, strip_tool_blocks, messages_to_prompt
text = 'sure\n<tool_call>\n{"name":"get_weather","arguments":{"city":"SF"}}\n</tool_call>'
calls = parse_tool_calls(text)
assert len(calls) == 1 and calls[0]["function"]["name"] == "get_weather"
assert strip_tool_blocks(text) == "sure"
prompt = messages_to_prompt(
    [{"role":"user","content":"hi"}],
    tools=[{"type":"function","function":{"name":"get_weather","parameters":{"type":"object"}}}],
)
assert "get_weather" in prompt and "<tool_call>" in prompt
assert DeepSeekClient is not None
PY
then log_ok "PASS: client + tools"; pass=$((pass+1))
else log_err "FAIL: client + tools"; fail=$((fail+1)); fi

echo
log_info "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
