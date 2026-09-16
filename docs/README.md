# Operator documentation — timestone-argo

Runbooks for the live Timestone cluster. These exist because the failure modes
in this stack are unusual: the cluster enforces a **cluster-wide default-deny
network policy**, so a missing rule presents as a silent timeout rather than a
refused connection, and several components are deliberately single-replica, so
"add another replica" is not the answer to an availability question.

| Doc | Covers |
|---|---|
| [`observability.md`](observability.md) | Metrics, alerting, the ntfy path, capacity, durability, and the rollback order |
| [`access.md`](access.md) | Reaching the cluster and its UIs; tunnel expiry; break-glass |

## Application map

`argocd/root-app.yaml` is the ONE Application ArgoCD does not manage: it is
applied imperatively once per cluster at bring-up (`timestone-tofu`'s
`bin/bootstrap-cluster.sh`). It syncs `path: argocd` with `recurse: true` and
`exclude: root-app.yaml`, which is why every child lives under `argocd/wave-N/`
and the map below is generated from those directories.

Child sync waves order **first creation** only. They do not serialize ongoing
reconciliation: each child is an independent auto-sync Application, so a change
pushed into an already-created child reconciles on its own schedule. Where
ordering genuinely matters across a change, this repository uses separate
commits with a verification gate between them rather than relying on waves.

The 27 children (generated from `argocd/wave-*/`; `root` itself is excluded):

| Application | Wave | Defined in | Source | Target | Destination ns |
|---|---|---|---|---|---|
| `gateway-api-crds` | -5 | `argocd/wave-0/` | git | `config/crd/standard` | `default` |
| `cilium` | 0 | `argocd/wave-0/` | helm | `cilium 1.20.1` | `kube-system` |
| `hcloud-ccm` | 0 | `argocd/wave-0/` | git | `base/hcloud-ccm` | `kube-system` |
| `hcloud-csi` | 0 | `argocd/wave-0/` | helm | `hcloud-csi 2.23.0` | `kube-system` |
| `traefik` | 0 | `argocd/wave-0/` | helm | `traefik 41.5.0` | `traefik` |
| `cnpg-operator` | 1 | `argocd/wave-1/` | helm | `cloudnative-pg 0.29.0` | `cnpg-system` |
| `spire-crds` | 1 | `argocd/wave-1/` | helm | `spire-crds 0.6.1` | `default` |
| `cnpg-cluster` | 2 | `argocd/wave-2/` | git | `base/cnpg` | `default` |
| `spire` | 3 | `argocd/wave-3/` | helm | `spire 0.30.2` | `default` |
| `temporal` | 3 | `argocd/wave-3/` | helm | `temporal 1.5.0` | `default` |
| `gateway` | 4 | `argocd/wave-4/` | git | `base/gateway` | `default` |
| `openbao-secret-sync` | 4 | `argocd/wave-4/` | git | `workloads/openbao-sync` | `openbao-sync` |
| `pocket-id` | 4 | `argocd/wave-4/` | git | `base/apps/pocket-id` | `default` |
| `spire-identities` | 4 | `argocd/wave-4/` | git | `base/spire` | `default` |
| `spire-policies` | 4 | `argocd/wave-4/` | git | `workloads/spire-policies` | `spire-server` |
| `spire-route` | 4 | `argocd/wave-4/` | git | `workloads/spire` | `spire-server` |
| `temporal-bootstrap` | 4 | `argocd/wave-4/` | git | `base/temporal-bootstrap` | `default` |
| `whoami` | 4 | `argocd/wave-4/` | git | `base/apps/whoami` | `default` |
| `cloudflared` | 5 | `argocd/wave-5/` | git | `base/cloudflared` | `default` |
| `umvc3` | 5 | `argocd/wave-5/` | git | `base/apps/umvc3` | `default` |
| `east-west` | 6 | `argocd/wave-6/` | git | `workloads/east-west` | `default` |
| `east-west-stage4` | 7 | `argocd/wave-7/` | git | `workloads/east-west-stage4` | `default` |
| `egress` | 7 | `argocd/wave-7/` | git | `workloads/egress` | `default` |
| `egress-prereqs` | 7 | `argocd/wave-7/` | git | `workloads/egress-prereqs` | `default` |
| `observability-namespace` | 8 | `argocd/wave-8/` | git | `workloads/observability-namespace` | `observability` |
| `kube-prometheus-stack` | 10 | `argocd/wave-10/` | helm | `kube-prometheus-stack 91.4.1` | `observability` |
| `observability-monitors` | 11 | `argocd/wave-11/` | git | `workloads/observability-monitors` | `observability` |

### Directory layout

```
argocd/            # one child Application per directory, ordered by sync wave
  root-app.yaml    #   applied once at bring-up; recurses argocd/, excludes itself
  wave--5..15/     #   the children, incl. Helm-sourced ones (cilium, traefik, ...)
base/              # plain YAML, one directory per component (= one child Application)
  cnpg/ gateway/ apps/{whoami,umvc3,pocket-id}/ cloudflared/ hcloud-ccm/ spire/
workloads/         # policy and workload directories that are NOT "base platform"
  east-west/       #   ingress allows per namespace (wave 6)
  east-west-stage4/#   the cluster-wide default-deny itself (wave 7)
  egress/          #   per-namespace egress deny + allows (wave 7)
  egress-prereqs/  #   non-enforcing cluster-wide allows that no namespace policy can express
  observability-*/ #   the observability stack: namespace, policies live in egress/,
                   #   monitors, and (waves 12-15) loki, alloy, grafana, temporal-ui, ui-routes
spire-policies/    #   SPIRE admission policy support
docs/              # this directory
nonprod/           # scaffolded, NOT applied. Sibling of argocd/ on purpose: the prod
                   #   root recurses argocd/ and can therefore never sync it.
```

### Why two roots of "base" and "workloads"

`base/` holds components that exist in every cluster (CNI-adjacent pieces, the
database, the gateway, the apps). `workloads/` holds the policy layer and the
observability stack, which are shaped by *this* cluster's security posture — the
enforced cluster-wide deny — rather than being generic platform. Keeping them
separate means the policy layer can be reverted without touching the platform
that must keep running.

## Credentials

Nothing in this repository contains a credential. Two mechanisms supply them:

- `timestone-tofu/bin/bootstrap-cluster.sh` creates the bring-up Secrets
  (`hcloud`, `cloudflared-tunnel-token`, `temporal-db-password`,
  `cloudflare-api-token`).
- `timestone-tofu/bin/apply-cluster-secrets.sh` creates the steady-state
  observability Secrets (`grafana-oidc`, `oauth2-proxy-temporal`,
  `alertmanager-ntfy`) from environment variables. See
  `timestone-tofu/bootstrap/README.md` for its inputs and rotation modes.

Loki is the exception: it holds no static object-storage credential at all and
authenticates to AWS S3 through a SPIFFE JWT-SVID exchanged at STS. That
mechanism, and the three places the identity must agree, are documented in
`timestone-tofu/bootstrap/README.md`.
