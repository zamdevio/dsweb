# Proxy

```bash
./dsweb serve                 # http://127.0.0.1:8787/v1
./dsweb url                   # print key + sample curl
./dsweb cloudflared           # public tunnel (strong DS_API_KEY required)
```

Auth to the **local** proxy uses `Authorization: Bearer $DS_API_KEY`
(not your DeepSeek userToken). Upstream auth is loaded from XDG / `.env`.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | liveness |
| GET | `/v1/models` | `deepseek-chat`, `deepseek-reasoner` |
| POST | `/v1/chat/completions` | OpenAI chat + tools + thinking |
| POST | `/v1/messages` | minimal Anthropic Messages shim |

## Thinking

- Model id containing `reason` / `think`, or body `"thinking": true`
- Response field: `message.reasoning_content` (streaming delta too)
- Anthropic shim: `thinking` content block

## Tool calls (emulated)

Web upstream ≠ official Tools API. When the request includes `tools`:

1. Schemas are injected into the prompt  
2. Model is instructed to emit `<tool_call>{"name","arguments"}</tool_call>`  
3. Proxy parses → OpenAI `tool_calls` + `finish_reason: "tool_calls"`  
4. Agent sends `role: "tool"` results; proxy folds them into the next prompt  

Streaming with tools **buffers** content until the end so tool_calls can be
emitted cleanly.

Limits: model may ignore the format; multi-tool / exotic `tool_choice` is
best-effort.

## Search

`"search": true` or `"web_search": true` sets upstream `search_enabled`.
