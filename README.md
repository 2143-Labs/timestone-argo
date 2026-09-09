# timestone-argo — Timestone GitOps (ArgoCD)

What runs *in* the Timestone clusters: app-of-apps wave Applications, base
workload manifests. One repo, two ArgoCD instances (Hetzner leg + OVH leg), the
59s pattern. Cluster *provisioning* lives in `../timestone-tofu/`.

Canonical architecture & cost: [`../timestone.md`](../timestone.md).

## Fleet

| Cluster | Destination | ArgoCD instance | Syncs |
|---|---|---|---|
| Hetzner (nbg1) | `ts-hz-ctl`/`ts-hz-db` | in-cluster (installed by a NixOS oneshot) | whole repo via `argocd/root-app.yaml` |
| OVH (GRA) | `ts-ov-ctl`/`ts-ov-db` | future phase | whole repo (per-leg values) |

Home replay/general-compute workloads stay in the existing `argo/` repo — NOT here.

## Layout

```
argocd/
  root-app.yaml     # App-of-Apps → path argocd, recurse (applied ONCE per cluster
                    #   at bootstrap by the argocd-bootstrap oneshot; NOT
                    #   self-managed, mirrors the 59s pattern)
  wave--5..0/       # sync-wave annotation ordering:
                    #   -5 gateway-api-crds (external repo, v1.5.1)
                    #    0 traefik (helm 41.5.0 → v3.7.13, kubernetesGateway provider)
                    #    1 cnpg-operator (helm 0.29.0 → operator 1.30.0)
                    #    2 cnpg-cluster (base/cnpg)
                    #    3 temporal (helm 1.5.0)
                    #    4 gateway (base/gateway) + whoami (base/apps/whoami)
                    #    5 cloudflared (base/cloudflared)
base/               # shared plain YAML per component (dir = one ArgoCD child app)
  cnpg/cluster.yaml             # CNPG Cluster `timestone` (single instance, db node)
  gateway/gateway.yaml          # Gateway `timestone-gateway` (http :80, ns default)
  gateway/routes.yaml           # HTTPRoutes whoami + temporal → web UI :8080
  apps/whoami/{deployment,service}.yaml
  cloudflared/{configmap,deployment}.yaml
clusters/           # per-leg values for the future OVH phase (see its README)
```

## Phase 1 live checklist

- [ ] `https://whoami.hero-rehab.xyz` → 200 + Hostname body (Hetzner)
- [ ] `https://temporal.hero-rehab.xyz` → 200
- [ ] Gateway `timestone-gateway` `Programmed=True`
- [ ] `https://doesnotexist.hero-rehab.xyz` → 404 (tunnel fallback)
- [ ] Both nodes survive rolling `nixos-rebuild switch`; auto-update timer armed
- [ ] Backups wave: intentionally omitted (no home-S3 rclone age file this phase)

## Conventions (from 59s / home argo)

- No placeholder Secrets anywhere — manifests reference secrets by name only
  (injected by the `k8s-secrets-bootstrap` oneshot from agenix files).
- Every helm `targetRevision` + container image is pinned to a resolved version
  (never `:latest`); upgrades are separate follow-up commits.
- Wave order is annotation-driven (`argocd.argoproj.io/sync-wave`); file location
  under `wave-N/` is cosmetic (`root-app` recurses).
- Domain: `*.hero-rehab.xyz` (CF-terminated TLS — no cert-manager in-cluster).
- Cluster content targets ns `default`; helm charts create `argocd`/`cnpg-system`/
  `traefik`.

## Applied versions (2026-09-09)

| Component | Pin |
|---|---|
| Gateway API CRDs | v1.5.1 (home-proven) |
| Traefik chart | 41.5.0 (app v3.7.13) |
| CNPG chart | 0.29.0 (operator 1.30.0) |
| CNPG postgres | ghcr.io/cloudnative-pg/postgresql:16.15 |
| Temporal chart | 1.5.0 |
| whoami | traefik/whoami:v1.10.4 |
| cloudflared | 2026.8.3 |

## CI & multi-user

- `.github/workflows/validate.yml` — structural manifest check on every PR +
  push (YAML parse, sync-wave annotations, repoURLs, base/ namespaces). No
  secrets needed.
- **A push to `main` IS the deploy**: ArgoCD syncs this repo automatically, so
  any 2143-Labs member with write access can ship cluster content — the CI
  validator is the gate before merge. No per-user machine or key setup.
