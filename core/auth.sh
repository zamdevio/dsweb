#!/usr/bin/env bash
# core/auth.sh - auth for unofficial chat.deepseek.com API.
#
# Secrets live ONLY in $DS_AUTH_FILE (~/.config/dsweb/auth.json).
# Process env DS_TOKEN/DS_COOKIE may override for CI. Never from .env.

# --- storage -----------------------------------------------------------------

ds_auth_load() {
  [[ -f "$DS_AUTH_FILE" ]] || return 1
  DS_TOKEN="$(ds_json_get_file "$DS_AUTH_FILE" '.token //empty')"
  DS_COOKIE="$(ds_json_get_file "$DS_AUTH_FILE" '.cookie //empty')"
  DS_EMAIL="$(ds_json_get_file "$DS_AUTH_FILE" '.email //empty')"
  [[ -n "$DS_TOKEN" || -n "$DS_COOKIE" ]] || return 1
  export DS_TOKEN DS_COOKIE DS_EMAIL
}

ds_auth_save() {
  local token="$1" cookie="${2:-}" email="${3:-}"
  ds_ensure_dirs
  local ts
  ts="$(date -u +%FT%TZ)"
  printf '%s\n' "$(ds_json_build \
    "token=$token" "cookie=$cookie" "email=$email" "saved_at=$ts")" \
    | ds_json_write_file "$DS_AUTH_FILE" 600
  log_ok "Auth saved to $DS_AUTH_FILE"
}

ds_auth_logout() {
  rm -f "$DS_AUTH_FILE"
  unset DS_TOKEN DS_COOKIE
  log_ok "Logged out (removed $DS_AUTH_FILE)"
}

ds_auth_set_token() {
  local tok="$1"
  tok="$(printf '%s' "$tok" | tr -d '\r\n' | sed -E 's/^Bearer[[:space:]]+//')"
  [[ -n "$tok" ]] || die "empty token"
  case "$tok" in
    \{*\})
      local v
      v="$(printf '%s' "$tok" | ds_json_query '.value //empty')"
      [[ -n "$v" ]] && tok="$v" ;;
  esac
  DS_TOKEN="$tok"; export DS_TOKEN
  ds_auth_save "$tok" "${DS_COOKIE:-}" "${DS_EMAIL:-}"
}

ds_extract_token_from_cookie() {
  local raw="$1" tok=""
  tok="$(printf '%s' "$raw" | grep -oE '(^|[;[:space:]])userToken=[^;[:space:]]+' \
        | head -1 | sed -E 's/.*userToken=//')"
  [[ -z "$tok" ]] && tok="$(printf '%s' "$raw" | grep -oE '"(userToken|token)"[[:space:]]*:[[:space:]]*"[^"]+"' \
        | head -1 | sed -E 's/.*"([^"]+)"$/\1/')"
  case "$tok" in
    *%*) tok="$(printf '%b' "${tok//%/\\x}")" ;;
  esac
  printf '%s' "$tok"
}

ds_auth_from_cookie() {
  local raw="${1:-}"
  [[ -z "$raw" ]] && raw="$(cat)"
  [[ -n "$raw" ]] || die "no cookie provided (pass as arg, pipe, or use --from-browser)"

  local token
  token="$(ds_extract_token_from_cookie "$raw")"
  [[ -n "$token" ]] || die "could not find userToken in cookie string"

  DS_COOKIE="$raw"
  DS_TOKEN="$token"
  export DS_COOKIE DS_TOKEN
  ds_auth_save "$token" "$raw" "${DS_EMAIL:-}"
}

ds_auth_login() {
  local email="${1:-}" password="${2:-}"
  [[ -n "$email" && "$email" == *@* ]] || die "usage: ds_auth_login <email> <password>"
  [[ -n "$password" ]] || die "usage: ds_auth_login <email> <password>"

  DS_TOKEN=""  # unauth call
  local device_id body resp code
  device_id="deepseek-web-cli-$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  body="$(ds_json_build "email=$email" "mobile=" "area_code=" "password=$password" "device_id=$device_id" "os=web")"
  # login body needs empty strings — ds_json_build is fine

  resp="$(ds_http POST "/users/login" "$body")"
  code="$(ds_http_code)"

  if [[ -z "$resp" || "$code" == "202" ]]; then
    log_err "login blocked by AWS WAF (HTTP $code, empty body)."
    log_info "Tip: use 'token' or 'cookie' auth instead of password login."
    return 1
  fi
  if [[ "$code" != "200" ]]; then
    log_err "login failed (HTTP $code): $(printf '%s' "$resp" | ds_json_query '.' 2>/dev/null || printf '%s' "$resp")"
    return 1
  fi

  local bizcode token
  bizcode="$(printf '%s' "$resp" | ds_json_query '.data.biz_code //empty')"
  token="$(printf '%s' "$resp" | ds_json_query '.data.biz_data.user.token //empty')"
  [[ -z "$token" ]] && token="$(printf '%s' "$resp" | ds_json_query '.data.biz_data.token //empty')"

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

ds_auth_verify() {
  local resp code
  resp="$(ds_http GET "/users/current")"
  code="$(ds_http_code)"
  [[ "$code" == "200" ]] || return 1
  local msg
  msg="$(printf '%s' "$resp" | ds_json_query '.msg //empty')"
  case "$msg" in
    Missing\ Token|INVALID_TOKEN|Authorization\ Failed*) return 1 ;;
  esac
  # also catch code 40003
  local c
  c="$(printf '%s' "$resp" | ds_json_query '.code //empty')"
  [[ "$c" == "40003" ]] && return 1
  local biz
  biz="$(printf '%s' "$resp" | ds_json_query '.data.biz_data //empty')"
  [[ -n "$biz" && "$biz" != "null" ]]
}

ds_auth_whoami() {
  local resp code
  resp="$(ds_http GET "/users/current")"
  code="$(ds_http_code)"
  if [[ "$code" != "200" ]]; then
    log_err "whoami failed (HTTP ${code:-?})"
    return 1
  fi
  local msg c
  msg="$(printf '%s' "$resp" | ds_json_query '.msg //empty')"
  c="$(printf '%s' "$resp" | ds_json_query '.code //empty')"
  if [[ "$c" == "40003" || "$msg" == "Missing Token" || "$msg" == "INVALID_TOKEN" || "$msg" == Authorization\ Failed* ]]; then
    log_err "auth invalid: ${msg:-code $c}"
    log_info "fix: ./dsweb token   (paste fresh userToken)"
    return 1
  fi

  local lines
  # Pass JSON via env — a heredoc would steal stdin from a pipe.
  lines="$(DS_WHOAMI_JSON="$resp" "$DS_PYTHON" -c '
import json, os, sys
data = json.loads(os.environ.get("DS_WHOAMI_JSON") or "")
biz = ((data.get("data") or {}).get("biz_data")) or {}
if not biz:
    sys.exit(1)

def mask_email(e):
    if not e or "@" not in e:
        return "-"
    u, d = e.split("@", 1)
    return f"{u[:2]}****@{d}"

email = mask_email(biz.get("email") or "")
tok = biz.get("token") or ""
tok_fp = f"{tok[:8]}… ({len(tok)} chars)" if tok else "-"
status = biz.get("status", 0)
status_label = "ok" if status == 0 else f"status={status}"
chat = biz.get("chat") or {}
rows = [
    ("email", email),
    ("id", str(biz.get("id") or "-")),
    ("token", tok_fp),
    ("mobile", str(biz.get("mobile_number") or "-")),
    ("account", status_label),
    ("muted", str(chat.get("is_muted", 0))),
    ("mainland", str(biz.get("is_mainland", False))),
    ("minor", str(biz.get("minor_mode_status") or "NONE")),
]
for k, v in rows:
    print(f"{k}\t{v}")
')" || { log_err "whoami: empty profile / auth invalid"; return 1; }

  printf '\n' >&2
  printf '  %s%s%s\n' "$_S_MINT$_S_BOLD" "whoami" "$_S_RST" >&2
  ds_hr 46 2
  while IFS=$'\t' read -r k v; do
    [[ -n "$k" ]] && log_kv "$k" "$v"
  done <<< "$lines"
  ds_hr 46 2
  printf '\n' >&2
}

# Auth resolve order: process env → auth.json. Never .env.
ds_auth_ensure() {
  if [[ -n "${DS_TOKEN:-}" || -n "${DS_COOKIE:-}" ]]; then
    log_debug "using process-env credentials"
    return 0
  fi
  if ds_auth_load; then
    log_debug "using auth.json"
    return 0
  fi
  die "not authenticated. Run: ./dsweb token   (secrets live in $DS_AUTH_FILE)"
}
