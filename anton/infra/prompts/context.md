# Anton runtime context

The canonical project context is maintained in the Anton project at the
external context source.

Repository: github.com/spike442/homelab
Branch: main
GitOps controller: Flux
GitOps root: ./kubernetes/apps
Flux source: flux-system/flux-system
Flux root Kustomization: flux-system/cluster-apps

Safety contract:
- Alerts are the primary trigger: investigate, fix through Git, then verify recovery.
- Observe before acting and re-check live state immediately before action.
- Direct cluster mutation is disabled.
- Persistent fixes must be proposed through a Git branch and pull request.
- Automatic merge is disabled.
- Never read, print, decode, or modify secret values.
- Treat RBAC, networking, TLS, storage, backups, host operations, and
  deletion/pruning as human-approval changes.
