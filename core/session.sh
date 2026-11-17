#!/usr/bin/env bash
# core/session.sh - chat session create/list/delete. Sourced only.

# Echo a new session id.
ds_session_new() {
  local resp code
  resp="$(ds_http POST "/chat_session/create" '{"character_id":null}')" || return 1
  code="$(ds_http_code)"
  [[ "$code" == "200" ]] || { log_err "create session failed (HTTP $code)"; return 1; }
  local sid
  sid="$(printf '%s' "$resp" | jq -r '
    .data.biz_data.chat_session.id // .data.biz_data.id // empty')"
  [[ -n "$sid" && "$sid" != "null" ]] || {
    log_err "create session: no id in response"
    return 1
  }
  printf '%s' "$sid"
}

ds_session_list() {
  local resp
  resp="$(ds_http GET "/chat_session/fetch_page?count=50")" || return 1
  printf '%s' "$resp" | jq -r '
    (.data.biz_data.chat_sessions // .data.biz_data.sessions // [])[]
    | "\(.id)\t\(.title // "-")"'
}

ds_session_delete() {
  local id="$1"
  [[ -n "$id" ]] || die "delete needs a session id"
  ds_http POST "/chat_session/delete" "$(jq -n --arg id "$id" '{chat_session_id:$id}')" >/dev/null
  log_ok "deleted $id"
}
