-- Remove the broad bootstrap grants from migration 001. Runtime identities are
-- append-only except for the three lease/lifecycle tables they must advance.

REVOKE DELETE ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships, agent_tasks, retrieval_events,
    retrieval_candidates, agent_actions, memory_feedback, audit_events,
    outbox_events, import_runs, schema_migrations FROM trace_app;

REVOKE UPDATE ON TABLE organizations, repositories, memories, memory_sources,
    memory_scopes, memory_relationships, agent_tasks, retrieval_events,
    retrieval_candidates, agent_actions, memory_feedback, audit_events,
    outbox_events, import_runs, schema_migrations FROM trace_app;
GRANT UPDATE ON TABLE memories, agent_tasks, outbox_events TO trace_app;

-- Tenant bootstrap and bulk import use a deployment identity, never trace_app.
REVOKE INSERT ON TABLE organizations, repositories, import_runs, schema_migrations
    FROM trace_app;

-- Guardkeeper advances task/outbox leases; retrieval evidence and actions are
-- immutable receipts once inserted.
REVOKE UPDATE, DELETE ON TABLE retrieval_events, retrieval_candidates,
    agent_actions, audit_events, memory_feedback FROM trace_guardkeeper;
REVOKE DELETE ON TABLE agent_tasks, outbox_events FROM trace_guardkeeper;

REVOKE DELETE ON TABLE memories, memory_sources, memory_scopes,
    memory_relationships, agent_actions, audit_events, outbox_events
    FROM trace_keeper, trace_governor;

-- Read-only review and Managed MCP enrichment both use feedback while ranking;
-- the reader role receives no INSERT, UPDATE, or DELETE privileges.
GRANT SELECT ON TABLE memory_feedback TO trace_mcp_reader;
