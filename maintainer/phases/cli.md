# Phase: CLI style overhaul

**Tracker:** [`focus.md`](./focus.md) · **Status:** in progress (style slice started)

## Goals

- Consistent help, flags, exit codes (0 ok, 1 usage/auth, 2 network/WAF)
- Streaming UX: clearer think vs answer separation when `--think`
- Progress/spinners only when stderr is a TTY
- `dsweb help <cmd>` long help
- Consider thin Python Typer/click entry later — **bash wrapper can stay**
- Colored logs via `DS_COLOR=auto|always|never` + `--no-color`
- **`lib/style/unix.sh`** — shared ANSI / banners (not `ascii.sh`)
- **serve / cloudflared UX** — request counters; hide cloudflared noise; `--raw`

### Shipped in this slice

- [x] `lib/style/unix.sh` + styled `lib/log.sh`
- [x] proxy request `#n METHOD path status ms` log + `/health.requests`
- [x] `cloudflared` filters tunnel logs, prints public URL banner; `--raw` escape hatch

## Non-goals

- Rewriting the whole stack to TypeScript in this phase  
- GUI / web dashboard

## Acceptance

- `./dsweb --help` and subcommand help feel coherent  
- Doctor / auth errors are actionable one-liners  
- Documented in `docs/cli.md`
