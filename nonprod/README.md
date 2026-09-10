# nonprod/ — the NONPROD environment (home cluster)

This tree is the *home-cluster* environment. It is deliberately OUTSIDE
`argocd/`: the prod root Application syncs `path: argocd` with `recurse: true`,
so anything placed under `argocd/` is automatically applied to **prod**. Keeping
nonprod here means the two environments can never cross-contaminate.

## Environment matrix

| Env | Cluster | Domain | ArgoCD | Provisioned by |
|---|---|---|---|---|
| **prod** | Hetzner `ts-hz-ctl`/`ts-hz-db` | `hero-rehab.xyz` now → `hero.rehab` after the demo | in-cluster (installed by NixOS oneshot) | `timestone-tofu` (tofu + nixos) |
| **nonprod** | home cluster (existing) | TBD (a home domain, e.g. under `ts.2143.me`) | the existing home ArgoCD | nothing — apps only (no tofu) |

## Data residency rule

The home cluster is **US-resident**. Because of the EU data-at-rest rule,
nonprod must only ever hold **synthetic/demo data** — never real client data or
production PII. Product workloads that need real data belong in prod.

## Bootstrap (once, on the home cluster)

```sh
KUBECONFIG=~/.kube/home kubectl -n argocd apply -f nonprod/root-app.yaml
# then the nonprod Applications appear in the home ArgoCD and sync from this repo
```

## Status: scaffold only

`root-app.yaml` exists; per-service wave Applications under `nonprod/wave-N/`
are added as nonprod services are defined (with their own hostnames and values —
see `../clusters/nonprod/`). Nothing here is applied until the bootstrap above
is run.
