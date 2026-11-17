# Overview

**dsweb** is an unofficial client for [chat.deepseek.com](https://chat.deepseek.com):
a CLI plus a local OpenAI/Anthropic-compatible proxy.

It is **not** the official DeepSeek Platform API (`api.deepseek.com`), and it is
**not affiliated with, endorsed by, or related to DeepSeek** beyond speaking to
the same public web app that a browser would.

## What you get

| Surface | Role |
|---------|------|
| `./dsweb` CLI | Auth, one-shot ask, interactive chat, sessions, doctor |
| `./dsweb serve` | Local OpenAI-compatible `/v1/chat/completions` (+ Anthropic shim) |
| `./dsweb cloudflared` | Optional public tunnel to that proxy |

## What you must provide

A **userToken** (or cookie) from a logged-in browser session. Password login is
best-effort and often blocked by AWS WAF. There is no way around credentials —
they are account-bound.

**Use a secondary / disposable DeepSeek account.** Do not paste a token from the
account you rely on for chat, billing, or work. Suspensions of the form
*“violation of user policies… suspended until <date>”* are returned by
DeepSeek upstream and are outside this tool’s control.

## Legal / risk (read this)

- **Unofficial / reverse-engineered.** Endpoints, payloads, PoW, and WAF rules
  can change without notice and will break this tool.
- **Terms of Service.** Automating chat.deepseek.com may violate DeepSeek’s ToS.
  You use this software **at your own risk**.
- **Account suspension.** DeepSeek’s risk control can invalidate `userToken`
  within minutes under load and lock the account for days. Prefer the official
  Platform API (`api.deepseek.com`) for reliability.
- **How detection tends to work (informational).** Signals are the usual
  anti-abuse ones — not magic:
  - volume / burstiness (many completions in parallel, agent tool loops)
  - session patterns (rapid `chat_session` create/delete, no real browser UI)
  - client fingerprint (curl_cffi / non-browser stacks still differ from Chrome)
  - PoW + API shape used outside the official web/app clients  
  There is no supported “stealth mode.” Rate limits and secondary accounts only
  reduce chance; they do not make this ToS-safe.
- **No warranty.** See [LICENSE](../LICENSE) (MIT). Authors are not liable for
  account bans, data loss, or downstream damage.
- **Secrets.** Never commit `.env` or `auth.json`. Rotate tokens if exposed.
- **Public tunnels.** `cloudflared` exposes your proxy. A weak `DS_API_KEY`
  will be refused; still treat the URL as sensitive.

## Quick path (new machine)

```bash
git clone <this-repo> dsweb && cd dsweb
./scripts/setup.sh
./dsweb token                 # → ~/.config/dsweb/auth.json
./dsweb config set DS_API_KEY sk-your-local-key
./dsweb doctor && ./dsweb whoami
./dsweb serve                 # http://127.0.0.1:8787/v1
```

OpenCode: provider `deepseek-local` → that base URL + same API key. Prefer a lean MCP set;
huge tool catalogs (100+) make every turn slow because schemas are prompt-injected.

## Docs map

| Doc | Contents |
|-----|----------|
| [architecture.md](./architecture.md) | How pieces fit (client, PoW, SSE, proxy, tools) |
| [auth.md](./auth.md) | Token/cookie, XDG `auth.json` + `config.json` |
| [proxy.md](./proxy.md) | OpenAI compat, thinking, tool emulation |
| [cli.md](./cli.md) | Command cheat sheet |
