# timestone-argo — Timestone GitOps (ArgoCD)

What runs *in* the Timestone clusters: app-of-apps wave manifests, base workload
manifests, per-cluster values. One repo, two ArgoCD instances (Hetzner leg + OVH
leg), the 59s pattern. Cluster *provisioning* lives in `../timestone-tofu/`.

Canonical architecture & cost: [`../timestone.md`](../timestone.md).

## Fleet

| Cluster | Destination | ArgoCD instance | Syncs |
|---|---|---|---|
| Hetzner (nbg1) | `ts-hz-ctl`/`ts-hz-db` | in-cluster (self-managed) | whole repo, `clusters/hetzner` values |
| OVH (GRA) | `ts-ov-ctl`/`ts-ov-db` | in-cluster (self-managed) | whole repo, `clusters/ovh` values |

Home replay/general-compute workloads remain in the existing `argo/` repo (Temporal
workers attached to the EU Temporal over the tailnet) — NOT in this repo.

## Layout (planned — populated during build)

```
argocd/
  root-app.yaml     # App-of-Apps → path argocd, recurse (applied once per cluster
                    #   at bootstrap; NOT self-managed, like 59s)
  wave--2/          # namespaces
  wave-0/           # cilium, cert-manager(edge-terminated → likely minimal)
  wave-1/           # cnpg-operator, traefik
  wave-2/           # cloudflared (tunnel connector per leg)
  wave-3/           # temporal + temporal standby (OVH: scaled 0)
  wave-4/           # applications: frontend, matchmaking, admin
  wave-5/           # monitoring (ship to home stack), backups
base/               # shared manifests per component (CNPG cluster, Temporal
                    #   values, app deployments, ingress → traefik Gateway)
clusters/
  hetzner/          # values: db-primary=true, temporal-active, cnpg primary
  ovh/              # values: db-replica=true, temporal-standby(scaled 0), apps
```

## Wave ordering notes

- CNPG operator before clusters; CNPG primary/replica role set per cluster values.
- Temporal on Hetzner active; OVH keeps the same manifests with `replicas: 0`
  (pre-staged standby for DR §7 of timestone.md).
- cloudflared last-ish: ingress must exist before the tunnel points at it.

## Conventions (from 59s / home argo)

- No placeholder Secrets anywhere; manifests reference secrets by name only
  (injected by k8s-secrets-bootstrap).
- Per-cluster variance via `clusters/<name>/` values; shared content in `base/`.
- Domain: `*.c.hero.rehab` (CF-terminated TLS — no wildcard cert needed in-cluster).
