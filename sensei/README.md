# Sensei

The first agent in the Hive platform. Sensei validates pull requests and decides whether they can be merged.

```text
five-minute polling cycle
        -> configured repositories
        -> open pull requests
        -> isolated repository clone
        -> repository context and review prompt
        -> deterministic checks
        -> structured review decision
```

Sensei does not use GitHub webhooks. It polls the configured repositories every five minutes and skips a PR until its head commit changes. For each PR, it loads project-specific context and review instructions from S3:

```text
hive/sensei/context.md
hive/sensei/<project>/actions/review.md
hive/sensei/<project>/context.md
```

Review state is stored in the shared `hive` PostgreSQL database. The `reviews` table records each reviewed PR head, its checks, risk, confidence, decision, and review timestamp. A new review is triggered only when the PR head SHA changes.

When the deterministic policy returns `merge=true`, Sensei merges the pull request with the configured GitHub merge method. Failed merge attempts are not marked as processed and are retried on the next polling cycle.

Repository tools are declared beside each repository in `config.yaml`. The homelab entry exposes `kubectl`; Sensei passes it to the model as a function tool and executes only the configured binary with argument arrays. Tool output is bounded before it is returned to the model.

The requested policy blocks merging when risk or confidence is high. It also blocks failed checks, merge conflicts, incomplete reviews, and disabled automatic merging.

```text
src/sensei/
  api/            health API
  application/    polling, review orchestration, and policy
  domain/         review models and enums
  infrastructure/ configuration
  integrations/   GitHub, SQL, and isolated workspace adapters
infra/config/     non-secret YAML configuration
infra/sql/        versioned database schema
tests/            unit and startup tests
```

Secrets are supplied by deployment through environment variables or External Secrets, never YAML.

Sensei uses the configured OpenAI model through the Responses API with Structured Outputs. The model receives the PR diff, the repository context loaded from S3, and the repository instruction list. `SENSEI_LLM_API_KEY` supplies the API key and `HIVE_DATABASE_PASSWORD` supplies the shared database credential; review failures always produce a blocked decision.
