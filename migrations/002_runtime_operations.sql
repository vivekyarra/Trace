-- Durable runtime bookkeeping and least-privilege read model.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version STRING PRIMARY KEY,
    checksum STRING NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS import_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations (id),
    repository_id UUID NOT NULL REFERENCES repositories (id),
    source_name STRING NOT NULL,
    source_checksum STRING NOT NULL,
    imported_count INT NOT NULL DEFAULT 0,
    skipped_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT import_runs_source_unique UNIQUE (repository_id, source_checksum)
);

CREATE INDEX IF NOT EXISTS audit_events_repository_created_idx
    ON audit_events (organization_id, repository_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_tasks_repository_created_idx
    ON agent_tasks (organization_id, repository_id, created_at DESC);

GRANT SELECT ON TABLE schema_migrations TO lore_app;
GRANT SELECT, INSERT ON TABLE import_runs TO lore_app;
