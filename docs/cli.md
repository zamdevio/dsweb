# CLI cheat sheet

```bash
./dsweb <command> [flags]
```

Global-ish flags:  
`-s/--session ID` · `--think` · `--search` · `--model NAME` · `--port N` · `--no-color` · `--raw` (cloudflared)

Style lives in `lib/style/unix.sh` (`DS_COLOR=auto|always|never`).

`serve` / `cloudflared` print a request log (`#n METHOD path status ms`).  
`cloudflared` hides tunnel noise and surfaces the `*.trycloudflare.com` URL; pass `--raw` to see everything.

| Command | Purpose |
|---------|---------|
| `setup` | Idempotent bootstrap → `scripts/setup.sh` |
| `doctor` | Deps, paths, auth; exit 1 on critical fail |
| `selftest` | Offline unit-ish checks |
| `token` | Save userToken |
| `cookie` | Save Cookie header (extracts userToken) |
| `login` | Email/password (often WAF-blocked) |
| `whoami` | Print profile |
| `logout` | Remove auth.json |
| `ask "…"` | One-shot completion |
| `chat` | Interactive REPL |
| `sessions` / `rm` | List / delete upstream sessions |
| `serve` | Local OpenAI proxy |
| `cloudflared` | Public tunnel |
| `url` | Print proxy base URL + samples |
