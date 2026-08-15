-- Trace canonical institutional-memory schema for CockroachDB v26.2+.
-- Apply with a migration runner using a DDL-capable deployment role; the runtime
-- role is intentionally restricted to application tables.

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT organizations_name_unique UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations (id),
    provider STRING NOT NULL,
    external_project_id STRING NOT NULL,
    name STRING NOT NULL,
    default_branch STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT repositories_provider_project_unique UNIQUE (provider, external_project_id)
);

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations (id),
    repository_id UUID NOT NULL REFERENCES repositories (id),
    display_id STRING NOT NULL,
    memory_type STRING NOT NULL,
    title STRING NOT NULL,
    decision STRING NOT NULL,
    rationale STRING NOT NULL,
    rejected_alternative STRING NULL,
    future_implication STRING NOT NULL,
    status STRING NOT NULL,
    confidence DECIMAL(3, 2) NOT NULL,
    confidence_basis STRING NOT NULL,
    security_relevant BOOL NOT NULL DEFAULT false,
    severity STRING NULL,
    content_hash STRING NOT NULL,
    semantic_key STRING NOT NULL,
    embedding VECTOR(1024) NULL,
    embedding_model STRING NULL,
    embedding_version STRING NULL,
    embedded_at TIMESTAMPTZ NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NULL,
    superseded_by UUID NULL REFERENCES memories (id),
    version INT NOT NULL DEFAULT 1,
    created_by_actor_type STRING NOT NULL,
    created_by_actor_id STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT memories_display_id_unique UNIQUE (organization_id, repository_id, display_id),
    CONSTRAINT memories_content_unique UNIQUE (repository_id, content_hash),
    CONSTRAINT memories_lifecycle_valid CHECK (
        (status = 'SUPERSEDED' AND superseded_by IS NOT NULL)
        OR (status != 'SUPERSEDED' AND superseded_by IS NULL)
    ),
    CONSTRAINT memories_validity_valid CHECK (valid_until IS NULL OR valid_until >= valid_from),
    CONSTRAINT memories_embedding_metadata_valid CHECK (
        (embedding_model IS NULL AND embedding_version IS NULL)
        OR (embedding_model IS NOT NULL AND embedding_version IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS memories_repository_status_idx
    ON memories (organization_id, repository_id, status, valid_from DESC);
CREATE INVERTED INDEX IF NOT EXISTS memories_semantic_key_idx ON memories (semantic_key);
-- Prefix columns enforce tenant and repository filtering in vector retrieval.
CREATE VECTOR INDEX IF NOT EXISTS memories_embedding_vector_idx
    ON memories (organization_id, repository_id, embedding);

CREATE TABLE IF NOT EXISTS memory_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories (id) ON DELETE CASCADE,
    source_type STRING NOT NULL,
    source_external_id STRING NULL,
    source_url STRING NULL,
    commit_sha STRING NULL,
    mr_iid INT NULL,
    issue_iid INT NULL,
    incident_external_id STRING NULL,
    author_external_id STRING NULL,
    author_name STRING NULL,
    source_excerpt STRING NOT NULL,
    source_hash STRING NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT memory_sources_dedupe UNIQUE (memory_id, source_type, source_hash)
);

CREATE TABLE IF NOT EXISTS memory_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories (id) ON DELETE CASCADE,
    scope_type STRING NOT NULL,
    scope_value STRING NOT NULL,
    CONSTRAINT memory_scopes_dedupe UNIQUE (memory_id, scope_type, scope_value)
);

CREATE TABLE IF NOT EXISTS memory_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_memory_id UUID NOT NULL REFERENCES memories (id) ON DELETE CASCADE,
    target_memory_id UUID NOT NULL REFERENCES memories (id) ON DELETE CASCADE,
    relationship STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by STRING NOT NULL,
    CONSTRAINT memory_relationships_distinct CHECK (source_memory_id != target_memory_id),
    CONSTRAINT memory_relationships_dedupe UNIQUE (source_memory_id, target_memory_id, relationship)
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations (id),
    repository_id UUID NOT NULL REFERENCES repositories (id),
    task_type STRING NOT NULL,
    idempotency_key STRING NOT NULL,
    status STRING NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    last_error STRING NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT agent_tasks_idempotency_unique UNIQUE (repository_id, idempotency_key),
    CONSTRAINT agent_tasks_attempts_valid CHECK (attempt_count <= max_attempts)
);
CREATE INDEX IF NOT EXISTS agent_tasks_ready_idx ON agent_tasks (status, scheduled_at);

CREATE TABLE IF NOT EXISTS retrieval_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), task_id UUID NOT NULL REFERENCES agent_tasks (id),
    query_text STRING NOT NULL, embedding_model STRING NOT NULL, candidate_count INT NOT NULL,
    selected_count INT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT retrieval_events_counts_valid CHECK (selected_count <= candidate_count)
);
CREATE TABLE IF NOT EXISTS retrieval_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), retrieval_event_id UUID NOT NULL REFERENCES retrieval_events (id) ON DELETE CASCADE,
    memory_id UUID NOT NULL REFERENCES memories (id), vector_distance FLOAT8 NULL,
    semantic_score FLOAT8 NOT NULL, scope_score FLOAT8 NOT NULL, confidence_score FLOAT8 NOT NULL,
    security_boost FLOAT8 NOT NULL DEFAULT 0, feedback_score FLOAT8 NOT NULL DEFAULT 0,
    pre_rerank_score FLOAT8 NOT NULL, llm_rerank_score FLOAT8 NULL, selected BOOL NOT NULL DEFAULT false,
    selection_reason STRING NULL
);
CREATE TABLE IF NOT EXISTS agent_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), task_id UUID NOT NULL REFERENCES agent_tasks (id),
    action_type STRING NOT NULL, actor_type STRING NOT NULL, actor_id STRING NOT NULL,
    prompt_version STRING NULL, input_summary STRING NOT NULL, output_summary STRING NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), memory_id UUID NOT NULL REFERENCES memories (id),
    retrieval_event_id UUID NULL REFERENCES retrieval_events (id), feedback_type STRING NOT NULL,
    actor_id STRING NOT NULL, note STRING NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations (id),
    repository_id UUID NULL REFERENCES repositories (id), event_type STRING NOT NULL,
    actor_type STRING NOT NULL, actor_id STRING NOT NULL, entity_type STRING NOT NULL,
    entity_id UUID NOT NULL, details JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations (id),
    repository_id UUID NOT NULL REFERENCES repositories (id), aggregate_type STRING NOT NULL,
    aggregate_id UUID NOT NULL, event_type STRING NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
    deduplication_key STRING NOT NULL, published_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT outbox_events_dedupe UNIQUE (repository_id, deduplication_key)
);
CREATE INDEX IF NOT EXISTS outbox_events_pending_idx ON outbox_events (published_at, created_at);

-- Provision separately with a deployment identity.  Application code must use
-- trace_app, never the cluster owner.  The grants are intentionally explicit.
CREATE ROLE IF NOT EXISTS trace_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE organizations, repositories, memories,
    memory_sources, memory_scopes, memory_relationships, agent_tasks, retrieval_events,
    retrieval_candidates, agent_actions, memory_feedback, audit_events, outbox_events TO trace_app;
