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

> **Warning — do not use your primary DeepSeek account.**  
> dsweb talks to **chat.deepseek.com** like a browser, not the official Platform
> API. DeepSeek’s risk control regularly **suspends accounts** used this way
> (temporary policy locks are common). Use a disposable / secondary account only,
> or use [`api.deepseek.com`](https://platform.deepseek.com) for anything you care about.  
> Details: [docs/overview.md § Risk](./docs/overview.md#legal--risk-read-this).

**Not affiliated with DeepSeek.** This reverse-engineers the public web app
(WAF, PoW, SSE). It can break when they change anything.

| Surface | Role |
|---------|------|
| **CLI** | `./dsweb` — auth, ask, chat, whoami, doctor |
| **Proxy** | `./dsweb serve` — `/v1/chat/completions` (+ Anthropic shim) |
| **Docs** | [`docs/`](./docs/) — overview, auth, proxy, architecture |
| **Site** | [`apps/web`](./apps/web) — `pnpm deploy` → [thedsweb.pages.dev](https://thedsweb.pages.dev/) |

## Quick start

Requires **Python ≥ 3.10** and `curl`. `jq` is optional (Python JSON fallback).

```bash
git clone <repo-url> dsweb && cd dsweb
./scripts/setup.sh          # venv + deps + ~/.config/dsweb/config.json
./dsweb token               # paste userToken → ~/.config/dsweb/auth.json
./dsweb config set DS_API_KEY sk-your-local-key
./dsweb doctor              # must be green
./dsweb whoami
./dsweb ask "hi" --think
./dsweb serve               # http://127.0.0.1:8787/v1
```

Secrets → `auth.json`. Settings → `config.json`. See [docs/auth.md](./docs/auth.md).

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

XDG: `~/.config/dsweb/{auth,config}.json` · `~/.local/share/dsweb/` (data).  
Process env overrides config. Repo `.env` is legacy (settings only — no secrets).

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

## Legal / account risk

- **Unofficial.** Likely violates DeepSeek ToS; **account suspension is expected**,
  not a bug. Prefer a throwaway login — never your main / paid / work account.
- **Detection (high level).** Automated clients stand out vs a normal browser:
  high request rate, many parallel completions, PoW + session churn, non-browser
  TLS/JA3 fingerprints, agent/tool prompt shapes. DeepSeek can revoke `userToken`
  quickly and issue temporary policy suspensions.
- **No warranty.** MIT — see [LICENSE](./LICENSE). Authors are not liable for bans.
- **Don't commit secrets.** `auth.json` / `.env` stay local.
- **Public tunnels:** `cloudflared` requires a non-default `DS_API_KEY`.

## Maintainer

Sprint focus: [`maintainer/phases/focus.md`](./maintainer/phases/focus.md).
