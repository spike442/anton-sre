DROP TABLE IF EXISTS agent;

CREATE TABLE agent (
    agent_name TEXT PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO agent (agent_name, active)
VALUES
    ('anton', FALSE),
    ('sensei', FALSE);

GRANT USAGE ON SCHEMA public TO anton, sensei;
GRANT SELECT ON TABLE agent TO anton, sensei;
