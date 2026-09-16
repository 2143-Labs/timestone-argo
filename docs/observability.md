# Observability runbook

Everything below was run against the live cluster. Commands assume the
steady-state kubeconfig:

```sh
export KUBECONFIG=/home/john/repos/timestone-tofu/.runtime/kubeconfig-tunnel
```

## What is deployed

| Component | Where | Notes |
|---|---|---|
| Prometheus Operator + Prometheus + Alertmanager + kube-state-metrics + node-exporter | `observability` | Helm chart `kube-prometheus-stack` 91.4.1 (operator v0.94.0, Prometheus v3.14.0, Alertmanager v0.34.0) |
| Cilium agent + Hubble metrics | `kube-system` | scraper endpoints 9962 and 9965 |
| Application metrics | `default`, `cnpg-system`, `traefik` | Temporal, both CloudNativePG clusters, the CNPG operator, Traefik |
| ntfy alert delivery | external | Alertmanager webhook, no relay service |

## Health

```sh
kubectl -n argocd get applications
kubectl -n observability get pods,pvc
kubectl get ciliumclusterwidenetworkpolicy default-deny-cluster -o jsonpath='{.status.conditions[0].status}'
```

A healthy stack is: every Application `Synced/Healthy`, seven pods Running in
`observability`, both PVCs `Bound`, and `default-deny-cluster` reporting `True`.

### Targets — the check that catches most mistakes

A target that is down is the primary symptom of a network or label mistake, and
it is invisible in the Application list. Port-forward, never expose:

```sh
kubectl -n observability port-forward svc/kube-prometheus-stack-prometheus 19090:9090 &
curl -s 'localhost:19090/api/v1/targets?state=any' \
  | jq -r '.data.activeTargets|group_by(.labels.job)|map("\(.[0].labels.job)\t\(length)\t\([.[].health]|unique|join(","))")|.[]' | sort
curl -s 'localhost:19090/api/v1/targets?state=any' \
  | jq -r '.data.activeTargets[]|select(.health!="up")|"\(.labels.job) \(.scrapeUrl) \(.health) \(.lastError)"'
```

The expected set is 13 jobs and zero down: `apiserver`, `cilium-agent`,
`coredns`, `hubble-metrics`, `kube-prometheus-stack-alertmanager`,
`kube-prometheus-stack-prometheus`, `kube-state-metrics`, `kubelet`,
`node-exporter`, `observability/cnpg-databases`, `observability/cnpg-operator`,
`observability/temporal`, `observability/traefik`.

**A job that is absent is not the same as a job that is down.** If a job is
missing from that list entirely, the ServiceMonitor or PodMonitor was not
selected — almost always because it lacks the `release: kube-prometheus-stack`
label that Prometheus selects on. If the job is present but has no targets, the
selector matched no pods, or named a container port that does not exist on them.

If the ServiceMonitor or PodMonitor itself is missing, confirm the monitoring
CRDs are Established first: `kubectl get crd | grep monitoring.coreos`.

### Alerts

```sh
curl -s localhost:19090/api/v1/rules \
  | jq -r '.data.groups[]|.rules[]|select(.type=="alerting")|"\(.state)\t\(.name)\t\(.lastEvaluation)"' | sort | uniq -c | sort -rn | head
curl -s localhost:19090/api/v1/alerts | jq -r '.data.alerts[]|"\(.labels.alertname) \(.state) \(.labels.severity // "-")"'
```

Alertmanager holds the firing set, the silences and the notification log:

```sh
kubectl -n observability port-forward svc/kube-prometheus-stack-alertmanager 19093:9093 &
curl -s localhost:19093/api/v2/alerts | jq -r '.[]|"\(.labels.alertname) \(.status.state)"'
curl -s localhost:19093/api/v2/status | jq -r '.config.original'   # the loaded route/receivers
```

Two alerts are routed to the `null` receiver on purpose and must never reach a
human: `Watchdog` (a permanently-firing heartbeat) and `InfoInhibitor`
(bookkeeping that an inhibition hid something). If either appears in ntfy, the
route config has been altered.

### The ntfy path

Alertmanager reads the topic URL from a mounted Secret file, not from the
rendered config:

```sh
kubectl -n observability get secret alertmanager-ntfy \
  -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'   # key name only
```

The URL is `https://ntfy.sh/<topic>?template=alertmanager`. The
`?template=alertmanager` suffix is ntfy's own transformation that renders the
webhook payload into a readable title and body — that is why there is no relay
service in this stack. To read messages back without a subscribed device:

```sh
curl -s "https://ntfy.sh/<topic>/json?poll=1&since=15m" \
  | jq -r 'select(.message!=null)|"\(.time|todate) \(.title) | \(.message|split("\n")[0])"'
```

If alerts fire in Prometheus but never arrive:

1. `curl -s localhost:19090/api/v1/alertmanagers | jq '.data'` — must show one
   active alertmanager. A `droppedAlertmanagers` count with no `active` means
   Prometheus cannot reach Alertmanager, which under the cluster-wide deny is a
   missing ingress allow rather than a crash.
2. `curl -s localhost:19093/api/v2/alerts` — if Alertmanager has it, the problem
   is delivery, not ingestion.
3. Check the Alertmanager pod's egress to `ntfy.sh:443`. It is an FQDN rule, so
   Cilium only permits it after observing a DNS answer through its DNS proxy: a
   cold FQDN cache looks identical to a blocked destination.

### Firing and resolving an alert by hand

Useful for testing the path without waiting for a real condition:

```sh
kubectl -n observability port-forward svc/kube-prometheus-stack-alertmanager 19093:9093 &
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"probe"}}]' \
  localhost:19093/api/v2/alerts
```

A resolved notification is **not** immediate even with `send_resolved: true`:
`group_interval: 5m` means the resolution can lag by up to 5 minutes after the
alert clears. An operator waiting on it should expect that delay rather than
conclude delivery is broken.

## Hubble drops — triage, in order

This is the alert that matters most, because the cluster enforces a
cluster-wide default-deny: a missing allow rule presents as a timeout, not as a
refused connection, and everything downstream reports Healthy while a workload
silently cannot reach its destination.

```sh
kubectl -n observability port-forward svc/kube-prometheus-stack-prometheus 19090:9090 &
curl -s --get --data-urlencode \
  'query=sum by (source_namespace, source_workload, destination_namespace, destination_workload, traffic_direction) (rate(hubble_flows_processed_total{type="PolicyVerdict",verdict="DROPPED"}[5m])) > 0' \
  localhost:19090/api/v1/query | jq -r '.data.result[]|.metric'
```

Then, for the reason as Cilium categorised it:

```sh
curl -s --get --data-urlencode 'query=sum by (reason) (rate(hubble_drop_total[5m]))' \
  localhost:19090/api/v1/query | jq -r '.data.result[]|"\(.metric.reason) \(.value[1])"'
```

`POLICY_DENIED` is a policy verdict. `UNSUPPORTED_L3_PROTOCOL` is a non-IP
protocol and is not actionable.

Read the five context labels as: source namespace and workload, destination
namespace and workload, and the direction. Then:

1. Find the owning policy. Egress rules are in `workloads/egress/<namespace>.yaml`;
   intra-namespace ingress is in `workloads/east-west/`; the cluster-wide deny
   itself is `workloads/east-west-stage4/`.
2. Add the **narrowest** rule that restores the flow: a named destination pod or
   FQDN on a named port, in the source's own policy file.
3. **Never widen to `world` or to a bare CIDR to make an alert stop.** The whole
   point of the deny is that every destination is enumerated; a `world` rule
   converts a five-minute investigation into a permanent hole.
4. Commit the policy separately from the workload change that needs it, and
   verify with a labelled probe before relying on it.

**A caveat worth knowing before interpreting labels.** Cilium only populates
`source_workload`/`destination_workload` when it can resolve a workload name for
the endpoint. A bare Pod — no owner, no `app.kubernetes.io/name` — produces a
verdict with both namespaces and the direction set and **both workload labels
absent**. `HubblePolicyDrops` summaries are therefore written to read correctly
either way. Absent workload labels do not mean the drop is unimportant.

## Prometheus capacity

Prometheus is one replica on one 20Gi attached volume, with `retention: 15d` and
`retentionSize: 16GB`; whichever limit is reached first wins.

```sh
curl -s --get --data-urlencode 'query=prometheus_tsdb_head_series' localhost:19090/api/v1/query | jq -r '.data.result[0].value[1]'
curl -s --get --data-urlencode 'query=rate(prometheus_tsdb_head_samples_appended_total[5m])' localhost:19090/api/v1/query | jq -r '.data.result[0].value[1]'
curl -s --get --data-urlencode 'query=prometheus_tsdb_storage_blocks_bytes' localhost:19090/api/v1/query | jq -r '.data.result[0].value[1]'
kubectl -n observability exec prometheus-kube-prometheus-stack-prometheus-0 -c prometheus -- df -h /prometheus
```

Order of response when the volume approaches 80%:

1. Lower `retention` first (`retentionSize` is the hard stop that protects the
   volume, so lower retention costs history, not availability).
2. Expand the 20Gi claim through the Helm values — `hcloud-volumes` supports
   online expansion, verified live — and let the StatefulSet roll.
3. Only then consider a second replica, and note that a second replica against a
   single RWO claim is not possible; it needs a remote-write or object-store
   design as a separate piece of work.

## Durability — what is and is not protected

Stated plainly because the failure modes are quiet:

- **Prometheus, Alertmanager and Loki are single-replica on location-bound
  attached volumes.** There is no failover. A volume loss or a node loss means
  the affected history is gone, and Prometheus cannot be rescheduled elsewhere
  while its claim is bound to a node.
- **Alertmanager silences live on its volume.** Losing it loses every silence,
  which means previously-acknowledged alerts begin firing again.
- **Prometheus's PVC is Retain/Retain**, so deleting or reverting its
  Application does not delete the TSDB. That protection is deliberate and should
  not be relaxed.
- **Loki's durable half is S3, not the volume.** Chunks and the TSDB index live
  in the object store; the attached volume holds WAL and compactor state only,
  so a volume loss can lose unflushed data while flushed chunks survive.
- **`hcloud-volumes` is `WaitForFirstConsumer`.** A newly created claim sits
  `Pending` until its pod is scheduled. `Pending` before scheduling is normal;
  `Pending` for minutes *after* the pod schedules is not, and is the signal to
  inspect CSI events.

## Rollback order

Reverse of deployment, and deliberately ordered so that the most reversible
things come off first:

1. cloudflared hostname entries (the exposure)
2. HTTPRoutes / Gateway listener namespaces
3. Temporal oauth2-proxy, then Grafana
4. Alloy, then Loki
5. PodMonitors and PrometheusRules
6. the Cilium Hubble/metrics change — keep `maxUnavailable: 1`
7. kube-prometheus-stack, into its **CRD-only rollback values** (see below)
8. the policy layer in `workloads/egress/` and `workloads/east-west/`

Two rules that are easy to get wrong:

- **Never revert or delete the `kube-prometheus-stack` Application manifest.**
  It carries the `resources-finalizer`, so removing it from Git makes Argo
  cascade-delete the chart's CRDs *and every instance of them*. Roll it back by
  pushing a values commit that keeps the Application and `crds.enabled: true`
  while disabling `prometheus`, `alertmanager`, `prometheusOperator`,
  `kubeStateMetrics`, `nodeExporter`, `kubeApiServer`, `kubelet`, `coreDns` and
  `defaultRules.create`. Verify the CRDs remain Established and the PVC UIDs are
  unchanged. Full CRD removal is a separate, explicitly-approved operation after
  proving no Prometheus, Alertmanager, ServiceMonitor, PodMonitor or
  PrometheusRule instances remain.
- **Do not delete the `observability` namespace, its PVCs/PVs, the S3 buckets,
  the Secrets, the PocketID clients, or the AWS role.** They are the data and
  the credentials; a rollback that removes them turns a bad afternoon into a
  data-loss incident.

Use Git revert/push for ordinary units. Do **not** use `argocd app rollback`
under auto-sync: selfHeal will immediately re-sync to the Git state and the
rollback will appear to have done nothing.

## Break-glass

If policy changes make the API unreachable, the operator's only path in is the
Cloudflare tunnel to `kubernetes.default.svc:443`. See
`timestone-tofu` `bootstrap/README.md` for the firewall break-glass sequence:
reopen the bootstrap access gate with `tofu apply -var
talos_bootstrap_access=true`, re-derive the kubeconfig with `talosctl`, delete
`ciliumclusterwidenetworkpolicy/default-deny-cluster` (it is the single enforcing
object — every policy in `workloads/egress-prereqs/` is non-enforcing by
construction), then re-apply with bootstrap access false. Never read
`.runtime/rebuild/*` for this; re-derive instead.
