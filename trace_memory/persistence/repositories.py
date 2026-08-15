"""Visible SQL repositories; CockroachDB remains inspectable in the product."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from trace_memory.domain import AgentTask, Memory, MemoryStatus, OutboxEvent, TaskStatus
from trace_memory.persistence.database import CockroachDatabase


class MemoryRepository:
    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    def create(self, memory: Memory) -> bool:
        """Insert immutable decision content; content hash makes imports idempotent."""
        def insert(connection: Connection) -> bool:
            result = connection.execute(text("""
                INSERT INTO memories (
                    id, organization_id, repository_id, display_id, memory_type, title, decision,
                    rationale, rejected_alternative, future_implication, status, confidence,
                    confidence_basis, security_relevant, severity, content_hash, semantic_key,
                    embedding_model, embedding_version, embedded_at, valid_from, valid_until,
                    superseded_by, version, created_by_actor_type, created_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :repository_id, :display_id, :memory_type, :title, :decision,
                    :rationale, :rejected_alternative, :future_implication, :status, :confidence,
                    :confidence_basis, :security_relevant, :severity, :content_hash, :semantic_key,
                    :embedding_model, :embedding_version, :embedded_at, :valid_from, :valid_until,
                    :superseded_by, :version, :created_by_actor_type, :created_by_actor_id, :created_at, :updated_at
                ) ON CONFLICT (repository_id, content_hash) DO NOTHING
                RETURNING id
            """), memory.model_dump(mode="json"))
            return result.scalar_one_or_none() is not None
        return self._database.transaction(insert)

    def supersede(self, *, current_id: UUID, replacement_id: UUID) -> None:
        """Atomically make a replacement govern; concurrent attempts serialize safely."""
        def update(connection: Connection) -> None:
            result = connection.execute(text("""
                UPDATE memories SET status = :status, superseded_by = :replacement_id, updated_at = now()
                WHERE id = :current_id AND status = :active_status
            """), {"status": MemoryStatus.SUPERSEDED.value, "replacement_id": replacement_id,
                  "current_id": current_id, "active_status": MemoryStatus.ACTIVE.value})
            if result.rowcount != 1:
                raise ValueError("memory is not active or no longer exists")
            connection.execute(text("""
                INSERT INTO memory_relationships (source_memory_id, target_memory_id, relationship, created_by)
                VALUES (:current_id, :replacement_id, 'SUPERSEDES', 'trace-system')
                ON CONFLICT (source_memory_id, target_memory_id, relationship) DO NOTHING
            """), {"current_id": current_id, "replacement_id": replacement_id})
        self._database.transaction(update)

    def vector_candidates(self, *, organization_id: UUID, repository_id: UUID, embedding: str, limit: int = 20) -> list[dict[str, object]]:
        """Tenant-prefixed nearest-neighbour query used by retrieval, not a demo path."""
        statement = text("""
            SELECT id, display_id, title, decision, rationale, confidence, security_relevant,
                   embedding <=> CAST(:embedding AS VECTOR) AS vector_distance
            FROM memories
            WHERE organization_id = :organization_id
              AND repository_id = :repository_id
              AND status = 'ACTIVE'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS VECTOR)
            LIMIT :limit
        """)
        with self._database.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement, {
                "organization_id": organization_id, "repository_id": repository_id,
                "embedding": embedding, "limit": limit,
            }).mappings()]


class RuntimeRepository:
    """Durable task and outbox operations; delivery is always separate from commit."""

    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    def admit(self, task: AgentTask, event: OutboxEvent) -> bool:
        """Atomically persist one provider delivery and its dispatch event."""
        def insert(connection: Connection) -> bool:
            result = connection.execute(text("""
                INSERT INTO agent_tasks (
                    id, organization_id, repository_id, task_type, idempotency_key, status,
                    payload, attempt_count, max_attempts, scheduled_at, created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :repository_id, :task_type, :idempotency_key, :status,
                    CAST(:payload AS JSONB), :attempt_count, :max_attempts, :scheduled_at, :created_at, :updated_at
                ) ON CONFLICT (repository_id, idempotency_key) DO NOTHING
                RETURNING id
            """), {**task.model_dump(mode="json"), "payload": json.dumps(task.payload)})
            if result.scalar_one_or_none() is None:
                return False
            connection.execute(text("""
                INSERT INTO outbox_events (
                    id, organization_id, repository_id, aggregate_type, aggregate_id,
                    event_type, payload, deduplication_key, created_at
                ) VALUES (
                    :id, :organization_id, :repository_id, :aggregate_type, :aggregate_id,
                    :event_type, CAST(:payload AS JSONB), :deduplication_key, :created_at
                ) ON CONFLICT (repository_id, deduplication_key) DO NOTHING
            """), {**event.model_dump(mode="json"), "payload": json.dumps(event.payload)})
            return True
        return self._database.transaction(insert)

    def pending_outbox(self, *, limit: int = 50) -> list[dict[str, object]]:
        with self._database.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text("""
                SELECT id, organization_id, repository_id, aggregate_type, aggregate_id,
                       event_type, payload, deduplication_key, created_at
                FROM outbox_events WHERE published_at IS NULL
                ORDER BY created_at LIMIT :limit
            """), {"limit": limit}).mappings()]

    def mark_published(self, event_id: UUID) -> None:
        self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE outbox_events SET published_at = now()
            WHERE id = :id AND published_at IS NULL
        """), {"id": event_id}))

    def start_task(self, task_id: UUID) -> bool:
        def update(connection: Connection) -> bool:
            result = connection.execute(text("""
                UPDATE agent_tasks SET status = 'RUNNING', started_at = now(),
                    attempt_count = attempt_count + 1, updated_at = now()
                WHERE id = :id AND status IN ('PENDING', 'RETRY_SCHEDULED')
                    AND scheduled_at <= now() AND attempt_count < max_attempts
            """), {"id": task_id})
            return result.rowcount == 1
        return self._database.transaction(update)

    def finish_task(self, task_id: UUID) -> None:
        self._set_task_state(task_id, TaskStatus.SUCCEEDED, None, None)

    def fail_task(self, task_id: UUID, *, error: str, retry_at: datetime | None) -> None:
        status = TaskStatus.RETRY_SCHEDULED if retry_at else TaskStatus.DEAD_LETTERED
        self._set_task_state(task_id, status, error[:2000], retry_at)

    def _set_task_state(self, task_id: UUID, status: TaskStatus, error: str | None,
                        retry_at: datetime | None) -> None:
        scheduled_at = retry_at or datetime.now(timezone.utc)
        completed = status in {TaskStatus.SUCCEEDED, TaskStatus.DEAD_LETTERED}
        self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE agent_tasks SET status = :status, last_error = :error,
                scheduled_at = :scheduled_at,
                completed_at = CASE WHEN :completed THEN now() ELSE NULL END,
                updated_at = now() WHERE id = :id
        """), {"id": task_id, "status": status.value, "error": error,
               "scheduled_at": scheduled_at, "completed": completed}))


class ImportRunRepository:
    def __init__(self, database: CockroachDatabase, *, organization_id: UUID, repository_id: UUID) -> None:
        self._database = database
        self._organization_id = organization_id
        self._repository_id = repository_id

    def record(self, *, source_name: str, source_checksum: str, imported: int, skipped: int) -> None:
        self._database.transaction(lambda connection: connection.execute(text("""
            INSERT INTO import_runs (
                id, organization_id, repository_id, source_name, source_checksum, imported_count, skipped_count
            ) VALUES (
                :id, :organization_id, :repository_id, :source_name, :source_checksum, :imported, :skipped
            ) ON CONFLICT (repository_id, source_checksum) DO NOTHING
        """), {"id": uuid4(), "organization_id": self._organization_id,
               "repository_id": self._repository_id, "source_name": source_name,
               "source_checksum": source_checksum, "imported": imported, "skipped": skipped}))
