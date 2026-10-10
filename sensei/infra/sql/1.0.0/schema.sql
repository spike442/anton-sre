DROP TABLE IF EXISTS reviews;

CREATE TABLE reviews (
    id BIGSERIAL PRIMARY KEY,
    owner TEXT NOT NULL,
    repository TEXT NOT NULL,
    pull_request_number INTEGER NOT NULL,
    base_sha TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    pull_request_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'acknowledged',
    checks JSONB,
    risk TEXT,
    confidence TEXT,
    summary TEXT,
    findings JSONB,
    mergeable BOOLEAN,
    merge BOOLEAN,
    decision_reason TEXT,
    reviewed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    merged_at TIMESTAMPTZ,
    merge_commit_sha TEXT NOT NULL DEFAULT '',
    review_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT reviews_status_check
        CHECK (status IN ('acknowledged', 'pending', 'processing', 'failed', 'merged')),
    CONSTRAINT reviews_pr_head_key
        UNIQUE (owner, repository, pull_request_number, head_sha)
);

CREATE INDEX reviews_repository_pr_idx
    ON reviews (owner, repository, pull_request_number);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE reviews TO sensei;
GRANT USAGE, SELECT ON SEQUENCE reviews_id_seq TO sensei;
