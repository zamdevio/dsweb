# Architecture

Agent/dev map — enough to navigate without reading every file.

## Layout

```
dsweb                 CLI entry (bash)
scripts/              setup.sh · selftest.sh
~/.config/dsweb/      auth.json (secrets) · config.json (settings)
lib/client/           Python upstream client
  api.py              DeepSeekClient: whoami, temp sessions, stream, chat
  tools.py            <tool_call> + DSML (fullwidth ｜) → OpenAI tool_calls
  sse.py / pow.py / http.py / config.py
lib/xdg_config.py     config.json load/set
lib/json.sh           jq-optional JSON helpers
lib/style/unix.sh     TTY ANSI + banners
lib/                  proxy, dshttp, wasm, bash helpers
core/                 bash: auth, session, chat
apps/web/             Vite + React site (thedsweb.pages.dev)
examples/proxy/       sample calls against local /v1
docs/ · maintainer/
```

## Request path (CLI ask)

```
./dsweb ask
  → core/chat.sh
  → PoW (create_pow_challenge → wasm solve → x-ds-pow-response)
  → POST /api/v0/chat/completion (SSE)
  → lib/sse_parse.py / client.sse → stdout text
```

HTTP from bash goes through `lib/http.sh` → `lib/dshttp.py` (`curl_cffi`,
Chrome impersonation) so AWS WAF is less angry than plain curl.

## Request path (proxy)

```
OpenAI client → POST /v1/chat/completions
  → lib/proxy.py
  → client.tools.messages_to_prompt (optional tools)
  → client.DeepSeekClient.stream/chat
  → OpenAI chunks (reasoning_content + optional tool_calls)
```

## Hard dependencies

| Piece | Why |
|-------|-----|
| `curl_cffi` | TLS/JA3 fingerprint ≈ Chrome; beats many WAF checks |
| `wasmtime` + `lib/wasm/*.wasm` | DeepSeekHashV1 PoW required on completion |
| `fastapi` / `uvicorn` | Local OpenAI-compatible server |

## Auth storage

- Config: `~/.config/dsweb/auth.json` (mode 0600)
- Data: `~/.local/share/dsweb/` (cookie jar, cache, future history)
- Overrides: `DS_CONFIG_DIR`, `DS_DATA_DIR`, `DS_AUTH_FILE`, … via `.env`

## Tools (important)

Web chat has **no native tools API**. The proxy emulates OpenAI `tools` by
prompt injection and parsing `<tool_call>{...}</tool_call>`. Good enough for
many agent loops; not identical to `api.deepseek.com`.

See [proxy.md](./proxy.md).
