-- Trace production hardening. All lifecycle and delivery state remains append-only
-- or lease-controlled; normal runtime roles never receive DELETE.

ALTER TABLE memories ADD CONSTRAINT memories_type_enum CHECK (memory_type IN (
    'ARCHITECTURAL_DECISION', 'INCIDENT_LESSON', 'SECURITY_CONSTRAINT',
    'REVIEW_PATTERN', 'DEVELOPER_COMMITMENT', 'CODE_PATTERN'
));
ALTER TABLE memories ADD CONSTRAINT memories_status_enum CHECK (
    status IN ('DRAFT', 'ACTIVE', 'DISPUTED', 'SUPERSEDED', 'DEPRECATED')
);
ALTER TABLE memories ADD CONSTRAINT memories_confidence_range CHECK (confidence >= 0 AND confidence <= 1);
ALTER TABLE memory_relationships ADD CONSTRAINT memory_relationships_type_enum CHECK (relationship IN (
    'DEPENDS_ON', 'BLOCKS', 'CONTRADICTS', 'SUPERSEDES', 'CAUSED_BY',
    'MITIGATES', 'RELATED_TO', 'DERIVED_FROM'
));
ALTER TABLE memory_feedback ADD CONSTRAINT memory_feedback_type_enum CHECK (
    feedback_type IN ('USEFUL', 'IRRELEVANT', 'OUTDATED', 'INCORRECT')
);
ALTER TABLE agent_tasks ADD CONSTRAINT agent_tasks_status_enum CHECK (status IN (
    'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRY_SCHEDULED', 'DEAD_LETTERED'
));

ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL;
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS checkpoint JSONB NOT NULL DEFAULT '{}';
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS external_effect_id STRING NULL;
CREATE INDEX IF NOT EXISTS agent_tasks_lease_idx ON agent_tasks (status, locked_until, scheduled_at);

ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS claim_token UUID NULL;
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL;
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS publish_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS last_error STRING NULL;
CREATE INDEX IF NOT EXISTS outbox_events_claim_idx
    ON outbox_events (published_at, locked_until, created_at);

ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS model_id STRING NULL;
ALTER TABLE agent_actions ADD COLUMN IF NOT EXISTS external_effect_id STRING NULL;
ALTER TABLE retrieval_events ADD COLUMN IF NOT EXISTS final_action STRING NULL;
ALTER TABLE retrieval_events ADD COLUMN IF NOT EXISTS prompt_version STRING NULL;
ALTER TABLE retrieval_events ADD COLUMN IF NOT EXISTS model_id STRING NULL;

CREATE ROLE IF NOT EXISTS trace_guardkeeper;
CREATE ROLE IF NOT EXISTS trace_keeper;
CREATE ROLE IF NOT EXISTS trace_governor;
CREATE ROLE IF NOT EXISTS trace_mcp_reader;

GRANT SELECT ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships, memory_feedback TO trace_guardkeeper;
GRANT SELECT, INSERT, UPDATE ON TABLE agent_tasks, retrieval_events, retrieval_candidates,
    agent_actions, audit_events, outbox_events TO trace_guardkeeper;

GRANT SELECT ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships TO trace_keeper;
GRANT INSERT ON TABLE memories, memory_sources, memory_scopes, memory_relationships,
    agent_actions, audit_events, outbox_events TO trace_keeper;

GRANT SELECT ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships TO trace_governor;
GRANT INSERT ON TABLE memories, memory_sources, memory_scopes, memory_relationships,
    agent_actions, audit_events, outbox_events TO trace_governor;
GRANT UPDATE ON TABLE memories TO trace_governor;

GRANT SELECT ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships, retrieval_events, retrieval_candidates,
    agent_actions, audit_events TO trace_mcp_reader;

REVOKE DELETE ON TABLE memories, memory_sources, memory_scopes, memory_relationships,
    agent_actions, audit_events, retrieval_events, retrieval_candidates FROM trace_app;
