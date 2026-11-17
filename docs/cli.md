# CLI cheat sheet

```bash
./dsweb <command> [flags]
```

Flags: `-s/--session ID` · `--think` · `--search` · `--model NAME` · `--port N` · `--no-color` · `--raw`

| Command | Purpose |
|---------|---------|
| `setup` | Bootstrap (venv, deps, config.json; optional jq) |
| `doctor` | Deps / paths / auth |
| `config` | Show / get / set `~/.config/dsweb/config.json` |
| `token` / `whoami` / `logout` | Auth → `auth.json` |
| `ask` / `chat` | Completions (temp sessions by default) |
| `sessions` / `rm` | List / delete upstream chats |
| `serve` / `cloudflared` / `url` | Local OpenAI proxy (+ tunnel) |
| `selftest` | Offline checks |

Temp sessions keep chat.deepseek.com clean (`DS_SAVE_CHATS=true` or `-s` to keep).  
`jq` is optional. Style: `lib/style/unix.sh` (`DS_COLOR=auto|always|never`).

OpenCode / any OpenAI client:

```bash
./dsweb serve
# provider baseURL http://127.0.0.1:8787/v1  apiKey = DS_API_KEY from config
```
