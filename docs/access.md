# Access runbook

## The only path in: the Cloudflare Access tunnel

The Kubernetes API is **not** reachable from the internet directly. The private
endpoint `https://10.26.0.20:6443` is for the nodes and cloudflared, not for a
workstation. Operator access is the named tunnel at `k8s.hero-rehab.xyz`, gated
by a Cloudflare Zero Trust Access application.

Everyday use:

```sh
export KUBECONFIG=/home/john/repos/timestone-tofu/.runtime/kubeconfig-tunnel
kubectl get nodes
```

That kubeconfig points at `https://127.0.0.1:16443` and depends on a local
`cloudflared` process:

```sh
pgrep -af "cloudflared access tcp"
cloudflared access tcp --hostname k8s.hero-rehab.xyz --url 127.0.0.1:16443
```

### When kubectl starts timing out

The failure signature is specific and worth recognising, because it looks like a
cluster outage and is not one:

```
Unable to connect to the server: net/http: TLS handshake timeout
```

That means the Access **session expired** and the local `cloudflared` is sitting
at `Waiting for login...` — the process is running, so `pgrep` alone is
misleading. Check the process output, then re-run the client and complete the
browser login. Only after the tunnel is re-established is a cluster-side
diagnosis meaningful.

Rules that keep this cheap:

- Do not create a Cloudflare Access **service token** for this. The interactive
  session is the deliberate design; a service token is a standing credential on
  a workstation.
- Do not disable the Access application to "fix" access. `k8s.hero-rehab.xyz`
  terminates at `kubernetes.default.svc:443`, so removing the gate publishes the
  Kubernetes API — bearer tokens and all — to the internet.

## The one ungated hostname

`spiffe.hero-rehab.xyz` is the only public hostname in the tunnel config with no
Access application, and it is intentional. It serves the SPIRE OIDC discovery
document and JWKS, which are public key material fetched machine-to-machine:
the home OpenBao reads them to validate JWT-SVIDs, and AWS STS reads them to
validate the identity behind Loki's S3 credentials. Neither can present a
browser session, so gating it would break both.

Do not add an Access application there. It is also pinned in SPIRE's
`jwtIssuer`, so the hostname must not change either.

## Identity: the canonical PocketID is `au.2143.me`

There are two separate PocketID deployments. **`au.2143.me` (appName "2143 Labs")
is canonical**; the in-cluster instance at `id.hero-rehab.xyz` is being retired.

They are genuinely independent, not one instance behind two names:

| | `au.2143.me` (canonical) | `id.hero-rehab.xyz` (retiring) |
|---|---|---|
| Issuer | `https://au.2143.me` | `https://id.hero-rehab.xyz` |
| JWKS key id | `jlrwgdxIu9w` | `2YKEYRfq3Ss` |
| `requireUserEmail` | `true` | `false` |
| `emailVerificationEnabled` | `true` | `false` |
| `emailOneTimeAccessAsAdminEnabled` | `true` | `false` |
| Hosting | residential line, direct A record, no Cloudflare proxy | Hetzner cluster, Cloudflare tunnel |

Different issuers and different signing keys mean different user stores: users,
groups, OIDC clients and passkeys do **not** transfer between them.

Grafana and the Temporal `oauth2-proxy` both authenticate against the canonical
issuer, so their egress allowlists in `workloads/egress/observability.yaml` and
`workloads/egress/default.yaml` permit `au.2143.me:443` as an **FQDN** rule. That
host is a public `world` address from inside the cluster; pointing the rule at
the in-cluster `pocket-id` Service would not work, because those clients dial the
public issuer hostname, not the Service.

### Two consequences worth knowing before you touch this

**Passkeys are bound to the hostname.** PocketID sets
`RPID: utils.GetHostnameFromURL(deps.AppURL)` (`webauthn/service.go:43`), so a
passkey enrolled at one instance cannot be used at the other, and changing
`APP_URL` on a live instance invalidates **every** existing passkey on it —
including your own. Never change `APP_URL` on an instance you are logged into.
Users must re-enrol on the canonical instance.

**Access availability now depends on a home internet circuit.** `au.2143.me`
resolves to a Verizon Fios residential address and serves TLS itself
(`CN=*.2143.me`, Let's Encrypt) with no Cloudflare proxy in front. If that circuit
or the host is down, the Cloudflare edge cannot complete the token exchange and
every Access-gated application becomes unreachable. This is accepted, not
overlooked: the trade is that the org instance is the only one that requires and
verifies email and has admin email recovery enabled — the cluster instance has
neither, which is what made the earlier lockout unrecoverable.

### Do not gate the IdP

Cloudflare's edge must reach the issuer **unauthenticated** to fetch the JWKS and
exchange the authorization code. Putting an Access application on the IdP would be
circular and would break every login. `au.2143.me` must stay anonymous, exactly
like `id.hero-rehab.xyz` before it and `spiffe.hero-rehab.xyz` above.

## Break-glass to the cluster

If a network-policy change makes the tunnel path unusable, the recovery is the
Talos firewall gate rather than the tunnel:

```sh
cd /home/john/repos/timestone-tofu/hetzner
tofu apply -var talos_bootstrap_access=true     # reopens 6443 + 50000 from the office IP
talosctl kubeconfig ~/.kube/timestone.yaml      # re-derive; never read .runtime/rebuild/*
kubectl delete ciliumclusterwidenetworkpolicy default-deny-cluster
tofu apply -var talos_bootstrap_access=false
```

`default-deny-cluster` is the single enforcing object. Every policy in
`workloads/egress-prereqs/` sets `enableDefaultDeny: {ingress: false, egress:
false}`, so deleting that one object returns the cluster to permit-by-default;
there is no second policy to hunt down. Close the gate again immediately.

## Grafana and Temporal UI

> **Not yet exposed.** The `grafana.hero-rehab.xyz` and
> `temporal.hero-rehab.xyz` routes and tunnel entries land with waves 13-15,
> after the Grafana Application and the Temporal oauth2-proxy exist. This
> section will be completed with the exposure step; until then both UIs are
> reachable only by port-forward.

Both will be gated: Grafana by its own PocketID OIDC login, Temporal by an
oauth2-proxy in front of `temporal-web`. The repository's exposure rule is
**no gate, no route** — a hostname is added to the tunnel allowlist only
together with the thing that authenticates it. Consequently `temporal.hero-rehab.xyz`
must always terminate at `oauth2-proxy-temporal:4180`, never at `temporal-web:8080`;
routing to the web Service directly would publish an unauthenticated Temporal UI.

Until those land, reach either UI without exposing it:

```sh
kubectl -n observability port-forward svc/grafana 3000:80        # then http://localhost:3000
kubectl -n default port-forward svc/temporal-web 8080:8080       # then http://localhost:8080
```

`port-forward` bypasses the Gateway entirely, so it is the privileged
break-glass path. Clean up the process explicitly when finished — a forgotten
forward is an open door on a workstation:

```sh
pkill -f "port-forward svc/temporal-web"    # or: kill <pid>
```

The Temporal UI reached this way still needs a namespace to look at. The
`timestone` namespace is created by the `temporal-bootstrap` Application; if it
is missing, that Application's Sync hook Job has failed and the Temporal UI will
load empty rather than error.
