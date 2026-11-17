#!/usr/bin/env bash
# lib/http.sh - HTTP wrapper. Delegates to lib/dshttp.py (curl_cffi, WAF-aware).
# Body goes to stdout; status code is stored in $DS_LAST_CODE AND a status
# file (so `resp="$(ds_http ...)"` subshells don't lose the code).

DS_LAST_CODE=""
DS_LAST_BODY=""
DS_HTTP_STATUS_FILE="${DS_HTTP_STATUS_FILE:-$DS_CACHE_DIR/last_http_status}"

# Last HTTP status even after command-substitution capture of ds_http.
ds_http_code() {
  if [[ -f "$DS_HTTP_STATUS_FILE" ]]; then
    cat "$DS_HTTP_STATUS_FILE"
  else
    printf '%s' "${DS_LAST_CODE:-0}"
  fi
}

# ds_http METHOD PATH [json_body]
# Env consumed by the bridge: DS_TOKEN, DS_COOKIE, DS_POW_RESPONSE, plus config.
ds_http() {
  local method="$1" path="$2" body="${3:-}"
  local out rc
  out="$(mktemp)"
  local err
  err="$(mktemp)"

  DS_HTTP_OUT="$out" "$DS_PYTHON" "$DS_ROOT/lib/dshttp.py" \
    request "$method" "$path" "$body" 2>"$err"
  rc=$?

  local status
  status="$(sed -n 's/^__DS_STATUS__ \([0-9]*\) .*/\1/p' "$err" | tail -1)"
  DS_LAST_CODE="${status:-0}"
  # Persist outside the subshell created by $(ds_http ...) callers.
  mkdir -p "$(dirname "$DS_HTTP_STATUS_FILE")" 2>/dev/null || true
  printf '%s' "$DS_LAST_CODE" > "$DS_HTTP_STATUS_FILE"

  if [[ $rc -ne 0 ]]; then
    log_debug "bridge error: $(sed -n 's/^__DS_ERROR__ //p' "$err" | tail -1)"
  fi

  DS_LAST_BODY="$(cat "$out")"
  rm -f "$out" "$err"
  log_debug "$method $path -> $DS_LAST_CODE"
  printf '%s' "$DS_LAST_BODY"
}

# Parse a field out of JSON on stdin using jq, empty-safe.
ds_jq() { jq -r "${1:-.}" 2>/dev/null; }

ds_urlencode() { jq -rn --arg v "$1" '$v|@uri'; }

# Warm the upstream session (primes WAF cookies into the shared jar).
ds_http_warm() {
  "$DS_PYTHON" "$DS_ROOT/lib/dshttp.py" warm 2>/dev/null || true
}

# ds_pow_solve <target_path> -> prints x-ds-pow-response value.
# Fetches a challenge (needs auth) then solves it with the wasm.
ds_pow_solve() {
  local target="$1"
  local resp code
  resp="$(ds_http POST "/chat/create_pow_challenge" \
    "$(jq -n --arg t "$target" '{target_path:$t}')")" || return 1
  code="$(ds_http_code)"
  [[ "$code" == "200" ]] || { log_debug "pow challenge HTTP $code"; return 1; }

  local challenge
  challenge="$(printf '%s' "$resp" | jq -c '.data.biz_data.challenge')"
  [[ "$challenge" == "null" || -z "$challenge" ]] && return 1

  printf '%s' "$challenge" | "$DS_PYTHON" "$DS_ROOT/lib/pow.py"
}
