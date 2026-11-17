# Phase: apps/web (thedsweb.pages.dev)

**Tracker:** [`focus.md`](./focus.md) · **Status:** scaffolded — content/icon next  
**URL:** https://thedsweb.pages.dev/

## Goals

- Static marketing / docs landing for **dsweb** on Cloudflare Pages
- Brand mark: DeepSeek-*inspired* whale/orb mark with a clear **unofficial / free** cue (not a trademark clone)
- README header pulls `https://thedsweb.pages.dev/icon.svg` (or `/dsweb.svg`)
- Honest copy: unofficial web client, not Platform API, ToS risk link to repo docs
- Quick start → GitHub clone + `./scripts/setup.sh`

## Non-goals

- Hosting the OpenAI proxy on Pages (Pages is static; proxy stays local/`serve`)
- Official affiliation claims

## Acceptance

- [ ] Deployed at thedsweb.pages.dev  
- [ ] SVG (and PNG fallback) icon live  
- [ ] Repo README header uses that icon  
- [ ] Page states unofficial + links to GitHub  

## Notes

Icon generation prompt lives in the human handoff (session) / `apps/web/README.md`.
Drop assets into `apps/web/public/` then Pages publish from `apps/web`.
