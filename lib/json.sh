#!/usr/bin/env bash
# lib/json.sh — JSON helpers. Prefer system jq when present; otherwise
# fall back to $DS_PYTHON so auth/token/whoami never hard-depend on jq.

ds_have_jq() { command -v jq >/dev/null 2>&1 && jq -n '.' >/dev/null 2>&1; }

# ds_json_query <filter>   — read JSON on stdin, print raw string result
# Filter: .token  .data.biz_data.id   (append //empty for blank-on-miss)
ds_json_query() {
  local filter="${1:-.}"
  local raw
  raw="$(cat)"
  if ds_have_jq; then
    local jqf="$filter"
    jqf="${jqf//'//empty'/\/\/ empty}"
    printf '%s' "$raw" | jq -r "$jqf" 2>/dev/null
    return $?
  fi
  printf '%s' "$raw" | DS_JSON_FILTER="$filter" "$DS_PYTHON" -c '
import json, os, sys
filt = (os.environ.get("DS_JSON_FILTER") or ".").strip() or "."
empty_on_miss = False
if filt.replace(" ", "").endswith("//empty"):
    empty_on_miss = True
    filt = filt.split("//", 1)[0].strip()
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if filt in (".", ""):
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False))
    elif data is None:
        print("" if empty_on_miss else "null")
    else:
        print(data)
    raise SystemExit(0)
cur = data
for part in filt.lstrip(".").split("."):
    if not part:
        continue
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print("" if empty_on_miss else "null")
        raise SystemExit(0)
if cur is None:
    print("" if empty_on_miss else "null")
elif isinstance(cur, bool):
    print("true" if cur else "false")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
else:
    print(cur)
'
}

ds_json_get_file() {
  local file="$1" filter="${2:-.}"
  [[ -f "$file" ]] || { printf ''; return 1; }
  ds_json_query "$filter" < "$file"
}

# ds_json_build key=val ... — compact JSON object (string values)
ds_json_build() {
  if ds_have_jq; then
    local args=() k body first=1
    for pair in "$@"; do
      k="${pair%%=*}"
      args+=(--arg "$k" "${pair#*=}")
    done
    body="{"
    for pair in "$@"; do
      k="${pair%%=*}"
      [[ $first -eq 1 ]] && first=0 || body+=", "
      body+="\"$k\": \$$k"
    done
    body+="}"
    jq -nc "${args[@]}" "$body"
    return
  fi
  "$DS_PYTHON" -c '
import json, sys
out = {}
for pair in sys.argv[1:]:
    if "=" not in pair:
        continue
    k, v = pair.split("=", 1)
    out[k] = v
print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
' "$@"
}

# ds_json_write_file <path> [mode_octal]  — write stdin JSON pretty
ds_json_write_file() {
  local file="$1" mode="${2:-644}"
  DS_JSON_OUT="$file" DS_JSON_MODE="$mode" "$DS_PYTHON" -c '
import json, os, sys
path = os.environ["DS_JSON_OUT"]
mode = int(os.environ.get("DS_JSON_MODE") or "644", 8)
data = json.load(sys.stdin)
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
os.replace(tmp, path)
os.chmod(path, mode)
'
}
