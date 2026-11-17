# Agent rules

- **Scope from `phases/focus.md`** — don't invent parallel roadmaps mid-PR.
- **No secrets in git** — `.env`, `auth.json`, tokens, cookie jars.
- **Don't clobber real auth in tests** — use temp `DS_AUTH_FILE`.
- **Portable config** — paths via env/XDG; no hardcoded `/home/...`.
- **Unofficial product** — say so in user-facing docs; don't imply affiliation.
- **cloudflared** — refuse weak `DS_API_KEY`.
- **Tools honesty** — proxy tools are prompt-emulated; document limits.
- **Python stays** for WAF/`curl_cffi` unless a phase explicitly rewrites stack.
- Session noise → `maintainer/temp/`. Durable facts → `systems/` or `docs/`.
