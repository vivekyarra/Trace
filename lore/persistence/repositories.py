"""Visible SQL repositories; CockroachDB remains inspectable in the product."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from lore.domain import Memory, MemoryStatus
from lore.persistence.database import CockroachDatabase


class MemoryRepository:
    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    def create(self, memory: Memory) -> None:
        """Insert immutable decision content; content hash makes imports idempotent."""
        def insert(connection: Connection) -> None:
            connection.execute(text("""
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
            """), memory.model_dump(mode="json"))
        self._database.transaction(insert)

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
                VALUES (:current_id, :replacement_id, 'SUPERSEDES', 'lore-system')
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
