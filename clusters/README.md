# clusters/ — per-cluster values (future OVH phase)

One values set per leg, so the two legs stay identical except role flags (DR +
price-switch become config-only, per timestone.md §7-8).

Phase 1 (Hetzner-only) does NOT consume this directory — every wave Application
carries its values inline. When OVH opens:

```
hetzner/values.yaml    # cnpg: role=primary · temporal: replicas=1 (active)
ovh/values.yaml        # cnpg: role=replica · temporal: replicas=0 (standby)
```

Nothing here yet.
