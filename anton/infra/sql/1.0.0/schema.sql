DROP TABLE IF EXISTS incidents;

CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    alert JSONB NOT NULL,
    diagnosis JSONB NOT NULL,
    pr_url TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL,
    replayed_at TIMESTAMPTZ,
    replay_prompts JSONB NOT NULL DEFAULT '[]'::jsonb,
    manual_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    diagnosis_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeline JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX incidents_status_updated_idx
    ON incidents (status, updated_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE incidents TO anton;
