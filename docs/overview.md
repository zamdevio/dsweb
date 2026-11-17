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

## Legal / risk (read this)

- **Unofficial / reverse-engineered.** Endpoints, payloads, PoW, and WAF rules
  can change without notice and will break this tool.
- **Terms of Service.** Using automation against chat.deepseek.com may violate
  DeepSeek’s ToS. You use this software **at your own risk**.
- **No warranty.** See [LICENSE](../LICENSE) (MIT). Authors are not liable for
  account bans, data loss, or downstream damage.
- **Secrets.** Never commit `.env` or `auth.json`. Rotate tokens if exposed.
- **Public tunnels.** `cloudflared` exposes your proxy. A weak `DS_API_KEY`
  will be refused; still treat the URL as sensitive.

## Quick path (new machine)

```bash
git clone <this-repo> dsweb && cd dsweb
./scripts/setup.sh
cp .env.example .env   # if setup didn't already
# paste userToken from DevTools Local Storage
./dsweb token
./dsweb doctor
./dsweb whoami
./dsweb ask "hi"
```

## Docs map

| Doc | Contents |
|-----|----------|
| [architecture.md](./architecture.md) | How pieces fit (client, PoW, SSE, proxy, tools) |
| [auth.md](./auth.md) | Token/cookie, XDG paths, `.env` |
| [proxy.md](./proxy.md) | OpenAI compat, thinking, tool emulation |
| [cli.md](./cli.md) | Command cheat sheet |
