# apps/web — https://thedsweb.pages.dev/

Vite + React landing for **dsweb**. **pnpm only.**

## Dev

```bash
cd apps/web
pnpm install
pnpm dev
```

## Build

```bash
pnpm build        # → dist/  (includes /dsweb.png from public/)
pnpm preview
```

## Deploy (Cloudflare Pages)

Needs `wrangler` login (`pnpm wrangler login` once).

```bash
pnpm deploy            # production → thedsweb.pages.dev
pnpm deploy:preview    # preview branch deploy
```

Config: [`wrangler.toml`](./wrangler.toml) (`pages_build_output_dir = "dist"`).

### CI / dashboard alternative

| Setting | Value |
|---------|--------|
| Root directory | `apps/web` |
| Install | `pnpm install` |
| Build | `pnpm build` |
| Output | `dist` |

`pnpm-workspace.yaml` allows `esbuild` / `workerd` postinstall scripts (pnpm 12).
