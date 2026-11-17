# Auth

## Required credential

| Method | Reliability | Notes |
|--------|-------------|-------|
| `userToken` (localStorage) | **Best** | `./dsweb token` |
| Full `Cookie` header | Good | Must include extractable `userToken` |
| Email + password | Poor | Often empty `202` from AWS WAF |

### Getting `userToken`

1. Log into https://chat.deepseek.com in a browser  
2. DevTools → **Application** → **Local Storage** → `https://chat.deepseek.com`  
3. Copy `userToken` (raw string or `{"value":"...","__version":"0"}`)  
4. `./dsweb token '<paste>'`

## Where it lives

| Item | Default path |
|------|----------------|
| Auth JSON | `~/.config/dsweb/auth.json` |
| Cookie jar | `~/.local/share/dsweb/cookies.jar` |
| Cache | `~/.local/share/dsweb/cache/` |

Override with `DS_CONFIG_DIR` / `DS_DATA_DIR` / `DS_AUTH_FILE` in `.env`.

`.env` may also set `DS_TOKEN` / `DS_COOKIE` directly (useful for CI). Process
environment wins over `.env` file values.

## Commands

```bash
./dsweb token          # save + verify
./dsweb whoami         # full profile (token redacted in dump)
./dsweb logout         # delete auth.json
./dsweb doctor         # fails non-zero if auth invalid
```

## New machine

1. `./scripts/setup.sh`  
2. Copy `.env` **without** secrets, or start from `.env.example`  
3. Paste a fresh `userToken` (or copy `auth.json` yourself securely)  

There is no automatic cloud sync of credentials by design.
