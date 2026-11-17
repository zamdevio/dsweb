# Paths & config portability

| Kind | Env | Default |
|------|-----|---------|
| Config dir | `DS_CONFIG_DIR` | `$XDG_CONFIG_HOME/dsweb` or `~/.config/dsweb` |
| Data dir | `DS_DATA_DIR` | `$XDG_DATA_HOME/dsweb` or `~/.local/share/dsweb` |
| Auth | `DS_AUTH_FILE` | `$DS_CONFIG_DIR/auth.json` |
| Cookie jar | `DS_COOKIE_JAR` | `$DS_DATA_DIR/cookies.jar` |
| Cache | `DS_CACHE_DIR` | `$DS_DATA_DIR/cache` |
| Project root | derived | directory containing `dsweb` |
| Venv | — | `$DS_ROOT/.venv` |
| Deps stamp | — | `$DS_ROOT/.venv/.dsweb-deps-stamp` |

`.env` at repo root is the portable knobs file. Process env wins over `.env`.

No legacy path fallbacks — only `dsweb` XDG dirs (or explicit `DS_*` overrides).
