#!/usr/bin/env bash
# core/session.sh - upstream chat_session create / list / delete.

ds_session_new() {
  local resp sid
  resp="$(ds_http POST "/chat_session/create" '{"character_id":null}')"
  sid="$(printf '%s' "$resp" | ds_json_query '.data.biz_data.id //empty')"
  [[ -z "$sid" ]] && sid="$(printf '%s' "$resp" | ds_json_query '.data.biz_data.chat_session.id //empty')"
  [[ -n "$sid" ]] || die "create session failed: $resp"
  printf '%s' "$sid"
}

ds_session_list() {
  local resp
  resp="$(ds_http GET "/chat_session/fetch_page?count=50")"
  DS_SESS_JSON="$resp" "$DS_PYTHON" -c '
import json, os
data = json.loads(os.environ.get("DS_SESS_JSON") or "{}")
biz = (data.get("data") or {}).get("biz_data") or {}
items = biz.get("chat_sessions") or biz.get("items") or []
for s in items:
    if not isinstance(s, dict):
        continue
    sid = s.get("id") or ""
    title = (s.get("title") or s.get("name") or "")[:60]
    print(f"{sid}\t{title}")
'
}

# ds_session_delete <id> [--quiet]
ds_session_delete() {
  local id="$1" quiet=0
  [[ "${2:-}" == "--quiet" ]] && quiet=1
  [[ -n "$id" ]] || die "delete needs a session id"
  local body
  body="$(ds_json_build "chat_session_id=$id")"
  ds_http POST "/chat_session/delete" "$body" >/dev/null || true
  [[ $quiet -eq 1 ]] || log_ok "deleted $id"
}

# True when throwaway upstream sessions are enabled (default).
# DS_SAVE_CHATS=true flips this off.
ds_temp_sessions() {
  if [[ -n "${DS_SAVE_CHATS:-}" ]] && ds_bool "$DS_SAVE_CHATS"; then
    return 1
  fi
  ds_bool "${DS_TEMP_SESSIONS:-true}"
}
