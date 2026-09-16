# base/ — shared workload manifests

Plain YAML per component. Each subdirectory here is one ArgoCD child Application
path (see `argocd/wave-N/` and the map in [`../docs/README.md`](../docs/README.md)).

```
cnpg/cluster.yaml      # CNPG Cluster `timestone` — one instance on hcloud-volumes
                       #   (separate data and WAL claims). No nodeSelector: the
                       #   Talos nodes carry no workload label, so pinning by
                       #   `timestone.io/workload` would leave the pod unschedulable.
gateway/gateway.yaml   # Gateway `timestone-gateway` — gatewayClassName traefik,
                       #   ONE http:80 listener (TLS terminates at the CF edge).
                       #   Selects allowed route namespaces explicitly: `default`
                       #   and `spire-server`, plus `observability` once the Grafana
                       #   route lands. `same` and selector are alternatives, not
                       #   additive, which is why they are listed rather than defaulted.
gateway/routes.yaml    # HTTPRoutes in ns default: whoami (-> whoami:80) and
                       #   pocket-id (-> pocket-id:80). Pocket-ID is intentionally
                       #   gated by nothing: gating the IdP behind the IdP is circular.
                       #   There is NO temporal route here — the Temporal UI is reached
                       #   through the oauth2-proxy gate in `workloads/temporal-ui/`,
                       #   and routing to temporal-web directly would publish an
                       #   unauthenticated UI.
apps/whoami/           # Deployment (traefik/whoami:v1.10.4) + Service :80 + its
                       #   ingress NetworkPolicy
apps/umvc3/            # the ranked workload + its db client config
apps/pocket-id/        # Pocket-ID SSO IdP (ghcr.io/pocket-id/pocket-id) + Service
                       #   :80 -> :1411 + the Traefik ingress allow + RWO PVC.
                       #   Secret `pocket-id-secrets` (key ENCRYPTION_KEY) is created
                       #   imperatively at bootstrap, NOT in this repo.
cloudflared/           # Deployment (cloudflare/cloudflared, 2 replicas,
                       #   --no-autoupdate) + the tunnel ConfigMap. Auth uses
                       #   TUNNEL_TOKEN in token mode — there is no credentials file
                       #   and no `cloudflared-credentials` Secret. The token comes
                       #   from Secret `cloudflared-tunnel-token`, key `token`.
hcloud-ccm/            # Hetzner cloud-controller-manager (ns kube-system)
spire/                 # ClusterSPIFFEID registrations — the workload identities for
                       #   this trust domain. Namespace- AND ServiceAccount-scoped on
                       #   purpose: the SPIFFE ID embeds both.
temporal-bootstrap/    # the Sync hook Job that creates the `timestone` Temporal
                       #   namespace, plus its ServiceAccount/RBAC
```

## Exposure model

A hostname reaches the public internet only if it appears in
`base/cloudflared/configmap.yaml` **and** has an HTTPRoute. The rule is
**no gate, no route**: a browser-facing service gets a route only together with
the thing that authenticates it. Two ungated exceptions exist, each because a
gate would be circular or unusable — the Pocket-ID IdP itself, and the SPIRE
OIDC discovery endpoint whose key material is fetched machine-to-machine — and
both are commented as such at the route.

Everything else is ClusterIP-only and reached in-cluster by Service DNS or by
`kubectl port-forward`.

## Absent

- `backups/` — deferred: the backup CronJob Application is omitted until its
  object-storage credentials exist.
- `clusters/<name>/` values — the cluster ships one leg with inline Helm values.
