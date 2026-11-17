# Onboarding (agents / new contributors)

1. Read [`docs/overview.md`](../../docs/overview.md) (legal + what this is).  
2. Read [`docs/architecture.md`](../../docs/architecture.md).  
3. Check sprint: [`../phases/focus.md`](../phases/focus.md).  
4. Run `./scripts/setup.sh` then `./dsweb doctor` and `./dsweb selftest`.  
5. Prefer `lib/client/` for Python logic; keep `dsweb` bash thin.  
6. One concern per PR; update `shipped/` when closing a phase slice.  
7. Scratch notes → `maintainer/temp/` only (gitignored).
