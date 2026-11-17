# Phase: chat history & session UX

**Tracker:** [`focus.md`](./focus.md) · **Status:** planned (after foundation)

## Goals

- Persist CLI conversations under XDG data: `~/.local/share/dsweb/sessions/`
- `chat` resumes last session or `-s <id>`
- `chat --once "prompt"` — single turn, print session id, exit 0
- `ask` stays as thin alias or maps to `--once`
- `history` / `sessions` list local history (not only upstream ids)
- Store JSONL turns: `{ts, role, content, thinking?}`

## Non-goals

- Syncing history to DeepSeek cloud beyond what the web session already does  
- Full TUI (belongs in cli phase)

## Acceptance

- New machine with copied `DS_DATA_DIR` sees prior local history  
- No secrets in history files beyond what the user typed  
- `selftest` covers JSONL append/read helpers
