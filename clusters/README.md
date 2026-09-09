# clusters/ — per-cluster values

One values file set per leg. Populated during build; keeps the two legs identical
except for role flags (so DR and price-switch are config-only, per timestone.md §7-8).

```
hetzner/values.yaml    # cnpg: role=primary · temporal: replicas=1 (active)
ovh/values.yaml        # cnpg: role=replica · temporal: replicas=0 (standby)
```

Intended contents (matching the 59s `clusters/<name>/*-values.yaml` convention):

- `cnpg-role`: primary | replica (replica = streaming from other leg)
- `temporal-replicas`: 1 | 0 (standby pre-staged for DR)
- `cloudflared`: local Traefik Gateway endpoint each leg proxies to
- region labels for cost attribution (public cost post)

Nothing here yet.
