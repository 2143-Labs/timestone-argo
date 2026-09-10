# clusters/prod — PROD environment values

- **Cluster:** Hetzner `ts-hz-ctl` / `ts-hz-db` (EU compute; Cloudflare is the edge only)
- **Domain:** `hero-rehab.xyz` now → `hero.rehab` after the demo migration
- **Tree:** `../argocd/` (root app, `recurse: true`) + `../base/`
- **Data:** REAL — HA and backups are mandatory (CNPG replica + offsite dumps)

Phase 1 keeps values inline per wave Application. When variance grows, put an
overlay here (`kustomization.yaml`) and point the wave Applications at it.
