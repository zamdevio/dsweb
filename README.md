<div align="center">
  <img src="https://thedsweb.pages.dev/dsweb.png" width="72" height="72" alt="dsweb logo" />

  <h1>dsweb</h1>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
  [![Python >= 3.10](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
  [![Unofficial](https://img.shields.io/badge/status-unofficial-orange)](./docs/overview.md)

  <p><strong>CLI · whoami · serve · tools · think · tunnel</strong></p>
  <p>
    Unofficial DeepSeek <em>web</em> client — talk to chat.deepseek.com from the
    terminal, and expose it as a local OpenAI-compatible API.
  </p>
  <p>
    <a href="https://thedsweb.pages.dev/">Website</a> ·
    <a href="./docs/overview.md">Docs</a> ·
    <a href="./docs/architecture.md">Architecture</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#legal">Legal</a>
  </p>
</div>

---

**Not affiliated with DeepSeek.** This reverse-engineers the public web app
(WAF, PoW, SSE). It can break when they change anything. Official API users
should use `api.deepseek.com` instead.

| Surface | Role |
|---------|------|
| **CLI** | `./dsweb` — auth, ask, chat, whoami, doctor |
| **Proxy** | `./dsweb serve` — `/v1/chat/completions` (+ Anthropic shim) |
| **Docs** | [`docs/`](./docs/) — overview, auth, proxy, architecture |
| **Site** | [`apps/web`](./apps/web) — `pnpm deploy` → [thedsweb.pages.dev](https://thedsweb.pages.dev/) |

## Quick start

Requires **Python ≥ 3.10**, `curl`, `jq`.

```bash
git clone <repo-url> dsweb && cd dsweb
./scripts/setup.sh          # venv + deps + .env (skips what's done)
$EDITOR .env                # set DS_API_KEY; token can wait
./dsweb token               # paste userToken from chat.deepseek.com Local Storage
./dsweb doctor              # must be green
./dsweb whoami
./dsweb ask "hi" --think
./dsweb serve               # http://127.0.0.1:8787/v1
```

Auth cannot be skipped — see [docs/auth.md](./docs/auth.md).

## Layout

```
dsweb                 CLI entry
scripts/              setup.sh · selftest.sh
lib/client/           Python upstream client
lib/                  proxy, style, http, wasm
core/                 bash auth / session / chat
apps/web/             Vite + React → thedsweb.pages.dev
examples/proxy/       sample OpenAI client calls
docs/                 human + agent docs
maintainer/           phases/focus.md
```

XDG defaults: `~/.config/dsweb/` (auth) · `~/.local/share/dsweb/` (data).  
All overridable via `.env` — see [`.env.example`](./.env.example).

## Proxy + tools

Point any OpenAI client at the local server:

```python
from openai import OpenAI
c = OpenAI(base_url="http://127.0.0.1:8787/v1", api_key="your-DS_API_KEY")
print(c.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "hi"}],
).choices[0].message.content)
```

Tool calls are **prompt-emulated** (web has no native tools API) but return
real OpenAI-shaped `tool_calls` for agent loops. Details: [docs/proxy.md](./docs/proxy.md).

## Legal

- **Unofficial.** May violate DeepSeek ToS; use at your own risk.
- **No warranty.** MIT — see [LICENSE](./LICENSE).
- **Don't commit secrets.** `.env` and `auth.json` stay local.
- **Public tunnels:** `cloudflared` requires a non-default `DS_API_KEY`.

## Maintainer

Sprint focus: [`maintainer/phases/focus.md`](./maintainer/phases/focus.md).
