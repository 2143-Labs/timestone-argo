# base/ — shared workload manifests (to be authored during build)

Per-component plain YAML applied to BOTH clusters identically; per-cluster variance
lives in `../clusters/<name>/` overrides.

Planned components (in sync-wave order, see repo README):

- `cnpg/` — CNPG operator install; CNPG Cluster manifests (primary/replica role
  chosen by cluster values: `clusters/hetzner` = primary, `clusters/ovh` = replica)
- `temporal/` — Temporal server values (active on Hetzner; OVH same manifest,
  replicas 0 = DR standby)
- `traefik/` — Gateway API listener + wildcard HTTPRoute for `*.c.hero.rehab`
- `cloudflared/` — tunnel connector Deployment (token Secret by name)
- `apps/` — frontend, matchmaking coordination, admin/tooling (stateless, KEDA
  scale-to-zero annotations)
- `backups/` — CNPG barmanObjectStore + object backup CronJob → home SeaweedFS S3

No manifests exist here yet. First build task is `cnpg/` + a smoke-test namespace.
