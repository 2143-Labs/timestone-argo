# clusters/ — per-environment values

One directory per environment. The env determines *where* the manifests land and
*which* hostnames/values they use; the manifests themselves live in `base/`
(shared shape) and are referenced from each env's tree.

| Env | Tree | Cluster | Domain | Notes |
|---|---|---|---|---|
| `prod/` | `../argocd/` (root app, recurse) | Hetzner `ts-hz-*` | `hero-rehab.xyz` → `hero.rehab` after demo | real data — HA + backups required |
| `nonprod/` | `../nonprod/` (root app, recurse) | home cluster | a home domain (TBD) | synthetic data only (home is US-resident) |

## Values that differ per environment

- `hostname` / domain suffix (prod: `hero-rehab.xyz`; nonprod: home domain)
- CNPG shape: prod = replica(s) + backups; nonprod = single instance, no backups
- Temporal replicas: prod ≥ 1 per service; nonprod may scale down / share
- ingress: prod = Cloudflare tunnel allowlist; nonprod = home Gateway/ingress
- image pins: same tags across envs (promotion = a commit that bumps the pin)

Nothing is templated yet: Phase 1 ships inline values per wave Application.
When env-specific variance grows, introduce a kustomize overlay per env here
(`clusters/<env>/kustomization.yaml`) and point the env trees at it.
