#!/usr/bin/env bash
# core/auth.sh - auth handling for the unofficial chat.deepseek.com API.
#
# Two ways to authenticate, both stored in $DS_AUTH_FILE (0600):
#   1. Paste browser cookies (userToken / ds_session_id)  -> ds_auth_from_cookie
#   2. Email + password login                              -> ds_auth_login
#
# The resulting bearer token lands in $DS_TOKEN.

# --- storage -----------------------------------------------------------------

ds_auth_load() {
  [[ -f "$DS_AUTH_FILE" ]] || return 1
  DS_TOKEN="$(jq -r '.token // empty' "$DS_AUTH_FILE" 2>/dev/null)"
  DS_COOKIE="$(jq -r '.cookie // empty' "$DS_AUTH_FILE" 2>/dev/null)"
  DS_EMAIL="$(jq -r '.email // empty' "$DS_AUTH_FILE" 2>/dev/null)"
  [[ -n "$DS_TOKEN" || -n "$DS_COOKIE" ]] || return 1
  export DS_TOKEN DS_COOKIE DS_EMAIL
}

ds_auth_save() {
  local token="$1" cookie="${2:-}" email="${3:-}"
  ds_ensure_dirs
  jq -n --arg t "$token" --arg c "$cookie" --arg e "$email" \
    --arg ts "$(date -u +%FT%TZ)" \
    '{token:$t, cookie:$c, email:$e, saved_at:$ts}' > "$DS_AUTH_FILE"
  chmod 600 "$DS_AUTH_FILE"
  log_ok "Auth saved to $DS_AUTH_FILE"
}

ds_auth_logout() {
  rm -f "$DS_AUTH_FILE"
  log_ok "Logged out (removed $DS_AUTH_FILE)"
}

# Store a bare bearer token (from localStorage / devtools).
ds_auth_set_token() {
  local tok="$1"
  tok="$(printf '%s' "$tok" | tr -d '\r\n' | sed -E 's/^Bearer[[:space:]]+//')"
  [[ -n "$tok" ]] || die "empty token"
  # unwrap DeepSeek localStorage form {"value":"...","__version":"0"}
  case "$tok" in
    \{*\})
      local v
      v="$(printf '%s' "$tok" | jq -r '.value // empty' 2>/dev/null)"
      [[ -n "$v" ]] && tok="$v" ;;
  esac
  DS_TOKEN="$tok"; export DS_TOKEN
  ds_auth_save "$tok" "${DS_COOKIE:-}" "${DS_EMAIL:-}"
}

# --- extract token out of a raw cookie string / header blob -------------------

# Accepts: full "a=b; c=d" cookie strings, or the value of userToken alone.
ds_extract_token_from_cookie() {
  local raw="$1" tok=""

  # userToken=<jwt-ish>  (may be percent-encoded)
  tok="$(printf '%s' "$raw" | grep -oE '(^|[;[:space:]])userToken=[^;[:space:]]+' \
        | head -1 | sed -E 's/.*userToken=//')"
  [[ -z "$tok" ]] && tok="$(printf '%s' "$raw" | grep -oE '"(userToken|token)"[[:space:]]*:[[:space:]]*"[^"]+"' \
        | head -1 | sed -E 's/.*"([^"]+)"$/\1/')"

  # percent-decode if it looks encoded
  case "$tok" in
    *%*) tok="$(printf '%b' "${tok//%/\\x}")" ;;
  esac
  printf '%s' "$tok"
}

# --- method 1: pasted cookies -----------------------------------------------

# ds_auth_from_cookie '<cookie string>'  OR pipe via stdin, OR use -w to read
# from an open browser (best effort).
ds_auth_from_cookie() {
  local raw="${1:-}"
  [[ -z "$raw" ]] && raw="$(cat)"

  [[ -n "$raw" ]] || die "no cookie provided (pass as arg, pipe, or use --from-browser)"

  local token
  token="$(ds_extract_token_from_cookie "$raw")"
  [[ -n "$token" ]] || die "could not find userToken in the pasted cookies"

  DS_COOKIE="$raw"
  DS_TOKEN="$token"
  export DS_COOKIE DS_TOKEN

  ds_auth_save "$token" "$raw" "${DS_EMAIL:-}"
}

# --- method 2: email + password ---------------------------------------------

# DeepSeek's web /login body (captured from bundle): password is sent raw.
#   {email, mobile:"", area_code:"", password, device_id, os}
ds_hash_password() {
  # kept for compatibility; DeepSeek currently expects the raw password
  printf '%s' "$1"
}

ds_auth_login() {
  local email="${1:-}" password="${2:-}"
  [[ -n "$email" && "$email" == *@* ]] || die "usage: ds_auth_login <email> <password>"
  [[ -n "$password" ]] || die "usage: ds_auth_login <email> <password>"

  DS_TOKEN=""  # unauth call
  local device_id body resp code
  device_id="deepseek-web-cli-$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  body="$(jq -n \
    --arg e "$email" \
    --arg p "$password" \
    --arg d "$device_id" \
    '{email:$e, mobile:"", area_code:"", password:$p, device_id:$d, os:"web"}')"

  resp="$(ds_http POST "/users/login" "$body")"
  code="$(ds_http_code)"

  if [[ -z "$resp" || "$code" == "202" ]]; then
    log_err "login blocked by AWS WAF (HTTP $code, empty body)."
    log_info "Tip: use 'token' or 'cookie' auth instead of password login."
    return 1
  fi
  if [[ "$code" != "200" ]]; then
    log_err "login failed (HTTP $code): $(printf '%s' "$resp" | jq -c . 2>/dev/null || printf '%s' "$resp")"
    return 1
  fi

  # success shape: {code:0, data:{biz_code:0, biz_data:{user:{token,id}}}}
  local bizcode token
  bizcode="$(printf '%s' "$resp" | jq -r '.data.biz_code // empty')"
  token="$(printf '%s' "$resp" | jq -r '
    .data.biz_data.user.token // .data.biz_data.token
    // .data.user.token // .data.token // empty')"

  if [[ -z "$token" ]]; then
    if [[ -n "$bizcode" && "$bizcode" != "0" ]]; then
      log_err "login rejected (biz_code=$bizcode). Wrong email/password or MFA required."
    else
      log_err "login ok but no token in response"
    fi
    printf '%s\n' "$resp" >&2
    return 1
  fi

  DS_TOKEN="$token"; DS_EMAIL="$email"
  export DS_TOKEN DS_EMAIL
  ds_auth_save "$token" "" "$email"
}

# --- verify / whoami ---------------------------------------------------------

ds_auth_verify() {
  # Quiet validity check (used by cookie/token save). Exit 0 if profile loads.
  local resp code
  resp="$(ds_http GET "/users/current")"
  code="$(ds_http_code)"
  [[ "$code" == "200" ]] || return 1
  local msg
  msg="$(printf '%s' "$resp" | jq -r '.msg // empty' 2>/dev/null)"
  [[ "$msg" != "Missing Token" && "$msg" != "INVALID_TOKEN" ]] || return 1
  local biz
  biz="$(printf '%s' "$resp" | jq -c '.data.biz_data // empty' 2>/dev/null)"
  [[ -n "$biz" && "$biz" != "null" ]]
}

# Styled profile from /users/current (no raw JSON dump).
ds_auth_whoami() {
  local resp code
  resp="$(ds_http GET "/users/current")"
  code="$(ds_http_code)"
  if [[ "$code" != "200" ]]; then
    log_err "whoami failed (HTTP ${code:-?})"
    return 1
  fi
  local msg
  msg="$(printf '%s' "$resp" | jq -r '.msg // empty' 2>/dev/null)"
  if [[ "$msg" == "Missing Token" || "$msg" == "INVALID_TOKEN" ]]; then
    log_err "auth invalid: $msg"
    return 1
  fi

  local biz
  biz="$(printf '%s' "$resp" | jq -c '.data.biz_data // empty' 2>/dev/null)"
  if [[ -z "$biz" || "$biz" == "null" ]]; then
    log_err "whoami: empty profile"
    return 1
  fi

  local id email mobile status muted mainland minor token_fp
  id="$(printf '%s' "$biz" | jq -r '.id // "-"')"
  email="$(printf '%s' "$biz" | jq -r '
    .email // empty
    | if . == "" then "-"
      else (split("@") | "\(.[0][0:2])****@\(.[1])") end')"
  mobile="$(printf '%s' "$biz" | jq -r '
    .mobile_number // empty | if . == "" then "-" else . end')"
  status="$(printf '%s' "$biz" | jq -r '.status // 0')"
  muted="$(printf '%s' "$biz" | jq -r '.chat.is_muted // 0')"
  mainland="$(printf '%s' "$biz" | jq -r '.is_mainland // false')"
  minor="$(printf '%s' "$biz" | jq -r '.minor_mode_status // "NONE"')"
  token_fp="$(printf '%s' "$biz" | jq -r '
    .token // empty
    | if . == "" then "-"
      else "\(.[0:8])… (\(length) chars)" end')"

  local status_label="ok"
  [[ "$status" != "0" ]] && status_label="status=$status"

  printf '\n' >&2
  printf '  %s%s%s\n' "$_S_MINT$_S_BOLD" "whoami" "$_S_RST" >&2
  ds_hr 46 2
  log_kv "email"    "$email"
  log_kv "id"       "$id"
  log_kv "token"    "$token_fp"
  log_kv "mobile"   "$mobile"
  log_kv "account"  "$status_label"
  log_kv "muted"    "$muted"
  log_kv "mainland" "$mainland"
  log_kv "minor"    "$minor"
  ds_hr 46 2
  printf '\n' >&2
}

# Only re-auth when needed. Prefers an existing .env token/cookie.
ds_auth_ensure() {
  # .env-provided creds (config already loaded them) win if present
  if [[ -n "${DS_TOKEN:-}" || -n "${DS_COOKIE:-}" ]]; then
    log_debug "using .env credentials"
    return 0
  fi
  if ds_auth_load; then
    log_debug "using cached token"
    return 0
  fi
  die "not authenticated. Run: ./dsweb token   (or cookie/login)"
}
