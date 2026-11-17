# Sprint focus

**Shipped receipts:** [`../shipped/README.md`](../shipped/README.md)

---

## Focus now

| Priority | Vertical | Doc |
|----------|----------|-----|
| **Now** | Repo foundation as **dsweb** (XDG, setup, docs, maintainer, doctor) | this sprint — in progress |
| **Next** | CLI chat history / resume / `--once` | [`chat.md`](./chat.md) |
| **Then** | CLI style & UX overhaul | [`cli.md`](./cli.md) |
| **Also** | Marketing site `apps/web` → thedsweb.pages.dev | [`web.md`](./web.md) |
| **Later** | Completions via Python client only (drop plain curl in chat path) | systems note |
| **Maybe** | Full TypeScript rewrite | **not recommended** — see note below |

---

## Dependency chain

```txt
dsweb foundation (XDG + setup + docs + doctor)   ← done-ish
  → chat history / --once
  → CLI style overhaul
  → apps/web (thedsweb.pages.dev) — can ship in parallel
  → (optional) harden proxy tools + streaming
```

---

## Stack note (TS vs Python)

Full TS without Python is *possible* but **risky**: WAF bypass today depends on
`curl_cffi` Chrome impersonation. Node alternatives (`curl-impersonate` binary,
custom JA3) are weaker/ops-heavier. **Stay on Python** unless a dedicated phase
proves a reliable WAF path in Node first.

---

## Guiding rules

- One concern per PR.  
- `./dsweb doctor` + `./dsweb selftest` green before merge when touching runtime.  
- User docs in `docs/`; plans here.
