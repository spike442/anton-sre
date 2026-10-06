# Anton SRE agent

Anton is alert-mode:

```text
Alertmanager alert -> incident -> targeted read-only tool investigation -> create safe GitHub PR
-> Telegram status
```

Before each investigation, Anton synchronizes the default branch into
`/data/repo`. That checkout is the desired-state source of truth used by local shell commands;
the configured context file and Kubernetes API provide operating context and live state.

Anton currently exposes only alert mode. The alert path does not send a whole cluster snapshot
to the model: Anton starts with the alert and uses one bounded
read-only shell tool to run `kubectl`, `flux`, `helm`, `git`, or Linux inspection commands only
when needed. It also has OpenAI's hosted `web_search` tool for public documentation and current
external incidents; web search is optional and is invoked only when relevant. Additional tools
include read-only Prometheus queries and safe GitHub reads.

Agent branches use `anton/fix/<alert>/<scope>-<incident-id>` and commit
subjects use Conventional Commits, for example `fix(media): correct Sonarr probe timeout`.

Anton synchronizes the public repository anonymously, then commits and pushes fix branches over
SSH as the dedicated `antonsre` GitHub account. The SSH private key is supplied through the
ExternalSecret field `github-ssh-private-key`; direct GitHub API calls create the PR and labels.
The SSH key and pinned GitHub host key are mounted directly under the container user's `~/.ssh` directory.

The system and action prompts are stored in configured S3/RustFS objects. Tool definitions and
descriptions are loaded from `infra/config/llm.yaml` at process startup. A missing bucket/credential,
failed download, or system-prompt checksum mismatch is a fail-closed error. OpenAI requests use
a stable prompt-cache key for the static instructions and tool definitions.

Configuration uses `pydantic-settings`: YAML provides non-secret properties and ExternalSecret
environment variables provide credentials.

The service loads configuration and runtime prompts during FastAPI startup, stores them in an
application runtime object, and closes owned clients during shutdown. Configuration or prompt
changes require a pod restart.

The first release is fail-closed:

- Kubernetes access is read-only.
- Direct cluster mutation is not implemented.
- Automatic merge is not implemented.
- Alerts are persisted as incidents; there is no AlertRun model.
- Risk and confidence do not prevent PR creation; both are attached as PR labels.
- Incomplete or unsupported diagnoses stop at `blocked`; Anton does not wait for a human during the alert workflow.
- A pull request is created when the diagnosis contains a complete, validated, reversible, secret-free fix.

Incident endpoints:

```text
POST /webhooks/alerts?source=alertmanager
GET  /incidents
GET  /incidents/{incident_id}
```

The Kubernetes integration lives in the homelab repository under
`kubernetes/apps/anton` and targets namespace `sre`.
