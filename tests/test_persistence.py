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
    assert "embedding <=> CAST(:embedding AS VECTOR)" in source


def test_migration_declares_canonical_vector_memory_and_outbox() -> None:
    migration = Path("migrations/001_canonical_memory.sql").read_text(encoding="utf-8")
    assert "embedding VECTOR(1024)" in migration
    assert "CREATE VECTOR INDEX IF NOT EXISTS memories_embedding_vector_idx" in migration
    assert "CREATE TABLE IF NOT EXISTS outbox_events" in migration
    assert "CREATE ROLE IF NOT EXISTS trace_app" in migration
