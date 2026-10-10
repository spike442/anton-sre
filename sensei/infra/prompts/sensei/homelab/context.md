# Homelab repository context

## Mission and source of truth

This public repository is the declarative source of truth for a personal K3s homelab. An accepted change is not applied directly with `kubectl`; Flux reconciles the `main` branch into the cluster. Review the repository as production infrastructure: a syntactically valid manifest can still cause an outage, data loss, an inaccessible ingress, or a broken reconciliation graph.

The repository contains both Kubernetes GitOps configuration and Ansible host/bootstrap automation. Keep those concerns separate:

- `kubernetes/` describes the running cluster and applications.
- `kubernetes/flux/cluster/ks.yaml` is the Flux root Kustomization for `./kubernetes/apps`.
- `ansible/` prepares machines and manages host-level services such as Pi-hole on TrueNAS.
- `bootstrap/` contains initial cluster/bootstrap resources.
- `.taskfiles/` contains the project automation entry points.

## Physical and cluster topology

The environment is a small K3s cluster with control-plane nodes that also run workloads, plus an external NAS host. The NAS is outside Kubernetes and provides NFS storage, bulk data, backups, and host-level services. A change to NFS paths, NAS-backed storage, or host services can affect systems outside the cluster.

Core cluster infrastructure:

- Cilium provides the CNI, service routing, and LAN LoadBalancer behavior.
- Envoy Gateway provides HTTPRoute ingress for internal `*.timcasa.me` services.
- External Secrets reads the Homelab vault from the OnePassword ClusterSecretStore.
- OpenEBS `openebs-hostpath` provides local, node-bound application storage.
- CloudNativePG manages PostgreSQL cluster `postgres0` in namespace `database`.
- Flux source, kustomize, helm, and notification controllers reconcile the repository.
- Kyverno provides cluster policy enforcement.
- Tailscale provides remote LAN access through a subnet router.

## Flux reconciliation model

`kubernetes/flux/cluster/ks.yaml` reconciles `kubernetes/apps` from the `main` branch every hour with pruning enabled. Its patches apply Helm remediation defaults to child Kustomizations and HelmReleases. Most child Kustomizations also reconcile hourly and use `prune: true`; many application Kustomizations set `wait: false`, while platform dependencies commonly use `wait: true`.

Application structure normally follows:

```text
kubernetes/apps/<area>/<application>/ks.yaml
kubernetes/apps/<area>/<application>/app/
  kustomization.yaml
  helmrelease.yaml or native manifests
  ocirepository.yaml when using an OCI Helm chart
```

Namespace-level `kustomization.yaml` files compose application Kustomizations and commonly include `../../components/alerts`. Application dependencies are expressed with Flux `dependsOn`; do not replace that graph with implicit startup assumptions.

Important reconciliation implications:

- A merge to `main` can delete resources because pruning is enabled.
- Removing or renaming a Flux Kustomization can remove the entire application.
- `dependsOn`, `targetNamespace`, `path`, `sourceRef`, and `healthChecks` are operational fields, not cosmetic metadata.
- Helm chart upgrades can be changed by both the chart version and the values structure.
- A GitHub PR can be merged before the cluster has successfully reconciled; validation must include the expected post-merge state and rollback path.

## Repository domains

The repository is organized by namespace and application domain. The exact application set is intentionally not duplicated here because it changes as services are added or retired. Treat the namespace-level and application-level Kustomizations as the authoritative inventory.

The important architectural domains are:

- cluster/platform services: Flux, Cilium, CoreDNS, Kyverno, metrics, and certificate management;
- secrets and access: External Secrets with OnePassword;
- networking: Envoy Gateway, HTTPRoutes, DNS, and Tailscale;
- observability: Prometheus/Alertmanager, Gatus, logs, dashboards, and exporters;
- data services: CloudNativePG, Valkey, RustFS, and persistent volumes;
- workloads: media, productivity, backup, data-processing, and agent applications.

A directory in the working tree is not necessarily deployed. Confirm inclusion through the relevant `kustomization.yaml`, Flux Kustomization, and live cluster resources.

## Storage and data safety

Storage is heterogeneous and changes must identify which class is affected:

- OpenEBS hostpath volumes are local to a node and are not equivalent to replicated storage. A pod rescheduled to another node may not see the same local data.
- RustFS runs as an S3-compatible service and depends on persistent storage backed by the NAS. Hive prompts and other objects depend on RustFS availability.
- CloudNativePG manages the PostgreSQL service and uses object storage for database backups.
- Some application data uses retained NFS-backed volumes, while other data uses local OpenEBS volumes. These storage classes have different failure and recovery characteristics.
- The backup component uses NAS-backed repositories and snapshot policy/schedule resources. Inspect the live policy and schedule instead of assuming their current cadence or retention.

Treat changes to PVCs, PVs, `storageClassName`, reclaim policies, NFS paths, backup repository configuration, retention, snapshot schedules, or PostgreSQL bootstrap/backup settings as high risk. Never approve a destructive storage change without an explicit recovery and validation plan.

## Networking and ingress

Internal web applications use Envoy Gateway `HTTPRoute` resources and `*.timcasa.me` hostnames. Validate the route parent reference, namespace, backend service/port, TLS certificate source, and DNS expectation together. Cluster-local service names use the form `<service>.<namespace>.svc.cluster.local`.

The cluster has a mixture of ClusterIP services and LAN-facing LoadBalancer behavior through Cilium. Do not expose a service publicly merely to make an internal integration work. Prefer cluster-local routes for Alertmanager, Gatus, PostgreSQL, RustFS, Prometheus, and agent-to-agent traffic.

## Observability and alert flow

Prometheus and Alertmanager run in namespace `observability`. Alertmanager sends firing and resolved alerts to Anton at:

```text
http://anton.agents.svc.cluster.local:8080/webhooks/alerts?source=alertmanager
```

Gatus sends custom firing and resolved endpoint events to the same Anton service with `source=gatus`. The Gatus custom payload includes endpoint group, name, URL, description, and triggered/resolved status. The alert token is sourced from OnePassword; it must not be placed in a ConfigMap or committed manifest.

Alertmanager grouping, repeat intervals, inhibition rules, and alert expressions are configuration, not permanent platform facts. Inspect the live configuration and the changed manifests before relying on them. Resolved notifications are intentional and must not be removed when changing receivers.

A monitoring rule change must be reviewed for expression correctness, label cardinality, firing/resolution behavior, and whether it can create alert storms.

## Agents and permissions

Hive is the agent control plane. It owns the shared `agent` table, performs health checks, and exposes the authenticated idle/active controls used by the UI. Hive is the only component that writes agent lifecycle state.

Anton is the alert-driven remediation agent. It receives Alertmanager and Gatus events, reads live state, synchronizes the Homelab repository, and can create GitHub fix branches/PRs through its dedicated GitHub identity. Its Kubernetes role is mostly read-only, with narrowly scoped deletion of batch Jobs and CronJobs. Anton reads its lifecycle state from the shared database but does not manage it.

Sensei polls configured GitHub pull requests and reviews the diff with repository context and read-only Kubernetes tools. Its Kubernetes service account is read-only. Sensei merges only after its deterministic policy accepts the review; the GitHub App installation token, not Kubernetes RBAC, grants merge capability. Sensei reads its lifecycle state from the shared database but does not manage it.

Hive UI is the central UI in namespace `agents`. It calls Hive for agent status and lifecycle controls, and reads Anton incidents and Sensei review records through their APIs. UI actions that mutate state must remain authenticated and should not receive cluster credentials or GitHub write tokens.

## Secrets and credentials

Secrets are stored in OnePassword and synchronized by External Secrets. Do not add credentials, tokens, private keys, kubeconfigs, or generated secret values to Git. Secret references should use the existing `onepassword` ClusterSecretStore and application-specific ExternalSecret resources.

Important secret boundaries:

- `anton` contains Anton’s LLM, GitHub App, SSH, alert, Discord, and RustFS credentials.
- `sensei` contains Sensei’s LLM, GitHub merge, control API, and RustFS credentials.
- `hive` contains Hive’s `CONTROL_TOKEN` and shared PostgreSQL password.
- `sre-alertmanager` supplies the Alertmanager webhook bearer token.
- Gatus reads its alert token from the Anton secret flow.

Review any new secret reference for namespace, `remoteRef.key`, property name, target Secret name, and pod `secretKeyRef` consistency. A Secret name or key mismatch causes a runtime failure even when the manifest applies successfully.

## Review rules for this repository

For every PR, first identify the affected Flux Kustomization and its dependencies. Then inspect the rendered relationship between source, HelmRelease/native resources, Service, HTTPRoute, PVC, Secret, ServiceAccount, and monitoring resources.

Require extra evidence for:

- RBAC, service accounts, `automountServiceAccountToken`, security contexts, or public routes.
- Image/tag changes, chart upgrades, CRD changes, or Helm values migrations.
- PVC/PV/NFS/OpenEBS/RustFS/PostgreSQL/Kopiur changes.
- Alert expressions, Alertmanager routing, Gatus notifications, or resolved-event behavior.
- Flux paths, pruning, `dependsOn`, health checks, or namespace moves.
- Changes to secrets, ExternalSecret mappings, OnePassword integration, or private key handling.
- Changes that remove resources, rename identifiers, alter retention, or modify backup schedules.

Use the configured read-only `kubectl` tool to verify live status when the PR depends on current cluster state. Useful evidence includes Flux Kustomization and HelmRelease conditions, pod events/logs, PVC binding, service endpoints, HTTPRoute status, ExternalSecret readiness, Alertmanager configuration, and backup/snapshot status. Do not mutate the cluster during review.

A safe review must state the expected reconciliation result, the validation commands or observations, and the rollback path. If repository evidence and live read-only evidence are insufficient, use high risk or low confidence rather than assuming success.
