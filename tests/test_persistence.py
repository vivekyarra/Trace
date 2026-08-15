from pathlib import Path

from trace_memory.persistence.database import is_retryable_serialization_error


class RetryableError(Exception):
    sqlstate = "40001"


def test_only_cockroach_serialization_conflicts_are_retryable() -> None:
    assert is_retryable_serialization_error(RetryableError())
    assert is_retryable_serialization_error(Exception("restart transaction: TransactionRetryWithProtoRefreshError"))
    assert not is_retryable_serialization_error(Exception("connection refused"))


def test_vector_query_is_tenant_prefixed_and_filters_active_memories() -> None:
    source = Path("trace_memory/persistence/repositories.py").read_text(encoding="utf-8")
    assert "organization_id = :organization_id" in source
    assert "repository_id = :repository_id" in source
    assert "status = 'ACTIVE'" in source
    assert "embedding <-> CAST(:embedding AS VECTOR)" in source
    assert "WITH nearest AS MATERIALIZED" in source


def test_migration_declares_canonical_vector_memory_and_outbox() -> None:
    migration = Path("migrations/001_canonical_memory.sql").read_text(encoding="utf-8")
    assert "embedding VECTOR(1024)" in migration
    assert "CREATE VECTOR INDEX IF NOT EXISTS memories_embedding_vector_idx" in migration
    assert "CREATE INDEX IF NOT EXISTS memories_semantic_key_idx" in migration
    assert "CREATE TABLE IF NOT EXISTS outbox_events" in migration
    assert "CREATE ROLE IF NOT EXISTS trace_app" in migration


def test_runtime_role_has_no_delete_and_only_required_updates() -> None:
    migration = Path("migrations/004_runtime_least_privilege.sql").read_text(
        encoding="utf-8"
    )
    assert "REVOKE DELETE ON TABLE organizations" in migration
    assert "REVOKE UPDATE ON TABLE organizations" in migration
    assert "GRANT UPDATE ON TABLE memories, agent_tasks, outbox_events TO trace_app" in migration
    assert "REVOKE INSERT ON TABLE organizations, repositories" in migration
    assert "GRANT SELECT ON TABLE memory_feedback TO trace_mcp_reader" in migration
