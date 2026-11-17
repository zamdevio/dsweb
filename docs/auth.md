# Auth & config

## Clear rules

| What | Where | How |
|------|--------|-----|
| **Secrets** (`userToken`, cookie) | `~/.config/dsweb/auth.json` | `./dsweb token` / `cookie` / `login` |
| **Settings** (port, API key, model, …) | `~/.config/dsweb/config.json` | `./dsweb config` |
| **One-shot overrides** | process env (`DS_TOKEN=… ./dsweb …`) | wins over files |
| **Repo `.env`** | legacy only | settings OK; **secrets ignored** (setup migrates them) |

Never put `DS_TOKEN` in `.env` or `config.json`. That conflict is what caused stale/invalid auth.

## Getting `userToken`

1. Log into https://chat.deepseek.com  
2. DevTools → **Application** → **Local Storage** → `userToken`  
3. `./dsweb token` and paste  

## Commands

```bash
./dsweb token                 # save → auth.json + verify
./dsweb whoami                # profile (works without jq)
./dsweb logout                # delete auth.json
./dsweb config                # show config.json
./dsweb config set DS_API_KEY sk-mykey
./dsweb config get DS_PORT
./dsweb doctor                # paths + auth validity
```

## jq

Optional. `setup` can install it; otherwise Python JSON helpers are used for
token / whoami / sessions / PoW. Doctor treats missing jq as OK.
