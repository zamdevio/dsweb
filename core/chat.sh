#!/usr/bin/env bash
# core/chat.sh - completion streaming (SSE) against the web chat endpoint.
#
# DeepSeek requires a PoW header (x-ds-pow-response) on /chat/completion.
# We solve it via lib/pow.py (wasm) using the DS_PYTHON interpreter.

# ds_chat_stream <session_id> <prompt>
# Streams assistant text to stdout as it arrives.
ds_chat_stream() {
  local session_id="$1" prompt="$2"
  [[ -n "$prompt" ]] || die "empty prompt"

  # solve PoW for this endpoint
  local pow
  if pow="$(ds_pow_solve "/api/v0/chat/completion")" && [[ -n "$pow" ]]; then
    DS_POW_RESPONSE="$pow"
  else
    log_warn "could not obtain PoW, trying without it"
    DS_POW_RESPONSE=""
  fi
  export DS_POW_RESPONSE

  local payload
  local think="false" search="false"
  [[ -n "${DS_THINKING:-}" ]] && think="true"
  [[ -n "${DS_SEARCH:-}" ]] && search="true"
  payload="$("$DS_PYTHON" - "$session_id" "$prompt" "$think" "$search" <<'PY'
import json, sys
sid, prompt, think, search = sys.argv[1:5]
print(json.dumps({
    "chat_session_id": sid,
    "parent_message_id": None,
    "prompt": prompt,
    "ref_file_ids": [],
    "thinking_enabled": think == "true",
    "search_enabled": search == "true",
}, ensure_ascii=False))
PY
)"

  _ds_stream_request "$payload"
}

_ds_stream_request() {
  local data="$1"

  local -a args=(
    -sS -N -m "$DS_TIMEOUT"
    -X POST "${DS_API}/chat/completion"
    -H "User-Agent: $DS_USER_AGENT"
    -H "Accept: */*"
    -H "Content-Type: application/json"
    -H "Origin: $DS_BASE_URL"
    -H "Referer: $DS_BASE_URL/"
    -H "x-app-version: 20241129.1"
    -H "x-client-locale: $DS_CLIENT_LOCALE"
    -H "x-client-platform: web"
    -H "x-client-version: 1.0.0-always"
    -H "Authorization: Bearer ${DS_TOKEN:-}"
    --data-raw "$data"
  )
  [[ -n "${DS_COOKIE:-}" ]] && args+=(-H "Cookie: ${DS_COOKIE}")
  [[ -n "${DS_POW_RESPONSE:-}" ]] && args+=(-H "x-ds-pow-response: ${DS_POW_RESPONSE}")

  # Show THINK fragments when --think / DS_THINKING is set.
  if [[ -n "${DS_THINKING:-}" ]]; then
    DS_SHOW_THINK=1
  else
    DS_SHOW_THINK=0
  fi
  export DS_SHOW_THINK
  curl "${args[@]}" 2>/dev/null | _ds_parse_sse
}

# Parse DeepSeek SSE (fragment/patch protocol + legacy choices deltas).
_ds_parse_sse() {
  "$DS_PYTHON" "$DS_ROOT/lib/sse_parse.py"
}
