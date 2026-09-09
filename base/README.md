# base/ — shared workload manifests

Plain YAML per component. Each subdirectory here is one ArgoCD child Application
path (see `argocd/wave-N/`). Per-cluster variance for the future OVH phase will
live in `../clusters/<name>/`.

## Phase 1 contents (all ns default)

```
cnpg/cluster.yaml             # CNPG Cluster `timestone` — single instance pinned to
                              #   ts-hz-db via nodeSelector timestone.io/workload=primary;
                              #   local-path storage (8Gi + 4Gi wal); initdb creates
                              #   temporal + temporal_visibility; no backup section
gateway/gateway.yaml          # Gateway `timestone-gateway` — gatewayClassName traefik,
                              #   ONE http:80 listener (TLS at CF edge), ns default
gateway/routes.yaml           # HTTPRoute whoami (→ whoami:80) + temporal (→ temporal-web:8080)
apps/whoami/                  # Deployment (traefik/whoami:v1.10.4, replicas 1) + Service :80
cloudflared/                  # Deployment (cloudflare/cloudflared:2026.8.3, 2 replicas,
                              #   --no-autoupdate) + ConfigMap (tunnel ingress → traefik svc,
                              #   404 fallback); creds from Secret cloudflared-credentials
                              #   (oneshot-created, NOT in this repo)
```

## Absent this phase

- `backups/` — deferred: the wave-5 backup CronJob Application is omitted until
  home-S3 rclone credentials exist (documented gate, plan §0.4.9).
- `clusters/<name>/` values — Phase 1 ships one leg with inline helm values.
