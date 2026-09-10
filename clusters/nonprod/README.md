# clusters/nonprod — NONPROD environment values (**deferred**, not applied)

- **Cluster:** home cluster (existing hardware/k8s; **no Cloudflare in the path**)
- **Domain:** a home domain or tailnet name (TBD) — nonprod never uses
  `hero-rehab.xyz` (that is prod now) nor `hero.rehab`
- **Tree:** `../nonprod/` (own root app, applied to the home ArgoCD)
- **Data:** SYNTHETIC ONLY — the home cluster is US-resident; never put real
  client data or production PII here (EU data-at-rest rule)

Differences from prod to encode here once nonprod services exist: single-instance
CNPG (no backups), scaled-down Temporal, home ingress instead of the CF tunnel,
relaxed auth (it is an internal/demo environment).
