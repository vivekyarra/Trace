"""CockroachDB repositories with transactional memory and delivery invariants."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from trace_memory.domain import (
    AgentTask,
    Memory,
    MemoryScope,
    MemorySource,
    OutboxEvent,
    TaskStatus,
)
from trace_memory.persistence.database import CockroachDatabase
from trace_memory.retrieval import RankedCandidate


def serialize_vector(values: list[float] | None) -> str | None:
    return None if values is None else "[" + ",".join(format(value, ".9g") for value in values) + "]"


class MemoryRepository:
    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    @staticmethod
    def _insert_memory(connection: Connection, memory: Memory) -> bool:
        params = memory.model_dump(mode="json")
        params["embedding"] = serialize_vector(memory.embedding)
        result = connection.execute(text("""
            INSERT INTO memories (
                id, organization_id, repository_id, display_id, memory_type, title, decision,
                rationale, rejected_alternative, future_implication, status, confidence,
                confidence_basis, security_relevant, severity, content_hash, semantic_key,
                embedding, embedding_model, embedding_version, embedded_at, valid_from, valid_until,
                superseded_by, version, created_by_actor_type, created_by_actor_id, created_at, updated_at
            ) VALUES (
                :id, :organization_id, :repository_id, :display_id, :memory_type, :title, :decision,
                :rationale, :rejected_alternative, :future_implication, :status, :confidence,
                :confidence_basis, :security_relevant, :severity, :content_hash, :semantic_key,
                CAST(:embedding AS VECTOR), :embedding_model, :embedding_version, :embedded_at,
                :valid_from, :valid_until, :superseded_by, :version, :created_by_actor_type,
                :created_by_actor_id, :created_at, :updated_at
            ) ON CONFLICT (repository_id, content_hash) DO NOTHING RETURNING id
        """), params)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _insert_provenance(connection: Connection, memory: Memory, sources: list[MemorySource],
                           scopes: list[MemoryScope], task_id: UUID | None, *, prompt_version: str | None,
                           model_id: str | None) -> None:
        for source in sources:
            connection.execute(text("""
                INSERT INTO memory_sources (
                    id, memory_id, source_type, source_external_id, source_url, commit_sha, mr_iid,
                    issue_iid, incident_external_id, author_external_id, author_name, source_excerpt,
                    source_hash, captured_at, created_at
                ) VALUES (
                    :id, :memory_id, :source_type, :source_external_id, :source_url, :commit_sha, :mr_iid,
                    :issue_iid, :incident_external_id, :author_external_id, :author_name, :source_excerpt,
                    :source_hash, :captured_at, :created_at
                ) ON CONFLICT (memory_id, source_type, source_hash) DO NOTHING
            """), source.model_dump(mode="json"))
        for scope in scopes:
            connection.execute(text("""
                INSERT INTO memory_scopes (id, memory_id, scope_type, scope_value)
                VALUES (:id, :memory_id, :scope_type, :scope_value)
                ON CONFLICT (memory_id, scope_type, scope_value) DO NOTHING
            """), scope.model_dump(mode="json"))
        if task_id is not None:
            connection.execute(text("""
                INSERT INTO agent_actions (
                    id, task_id, action_type, actor_type, actor_id, prompt_version, model_id,
                    input_summary, output_summary
                ) VALUES (
                    :id, :task_id, 'MEMORY_CREATED', 'AGENT', 'tracekeeper', :prompt_version,
                    :model_id, :input_summary, :output_summary
                )
            """), {"id": uuid4(), "task_id": task_id, "prompt_version": prompt_version,
                   "model_id": model_id, "input_summary": f"source evidence for {memory.display_id}",
                   "output_summary": memory.decision[:1000]})
        connection.execute(text("""
            INSERT INTO audit_events (
                id, organization_id, repository_id, event_type, actor_type, actor_id,
                entity_type, entity_id, details
            ) VALUES (
                :id, :organization_id, :repository_id, 'MEMORY_CREATED', 'AGENT',
                :actor_id, 'memory', :memory_id, CAST(:details AS JSONB)
            )
        """), {"id": uuid4(), "organization_id": memory.organization_id,
               "repository_id": memory.repository_id, "actor_id": memory.created_by_actor_id,
               "memory_id": memory.id, "details": json.dumps({
                   "display_id": memory.display_id, "source_count": len(sources),
                   "scope_count": len(scopes), "embedding_model": memory.embedding_model,
                   "embedding_version": memory.embedding_version,
               })})
        connection.execute(text("""
            INSERT INTO outbox_events (
                id, organization_id, repository_id, aggregate_type, aggregate_id,
                event_type, payload, deduplication_key
            ) VALUES (
                :id, :organization_id, :repository_id, 'memory', :memory_id,
                'memory.created', CAST(:payload AS JSONB), :deduplication_key
            ) ON CONFLICT (repository_id, deduplication_key) DO NOTHING
        """), {"id": uuid4(), "organization_id": memory.organization_id,
               "repository_id": memory.repository_id, "memory_id": memory.id,
               "payload": json.dumps({"display_id": memory.display_id}),
               "deduplication_key": f"memory:{memory.id}:created"})

    def create(self, memory: Memory) -> bool:
        """Insert an embedded memory; retained for idempotent low-level callers."""
        if memory.status.value == "ACTIVE" and memory.embedding is None:
            raise ValueError("ACTIVE memories must be embedded before persistence")
        return self._database.transaction(lambda connection: self._insert_memory(connection, memory))

    def create_with_provenance(self, memory: Memory, *, sources: list[MemorySource],
                               scopes: list[MemoryScope], task_id: UUID | None = None,
                               prompt_version: str | None = None, model_id: str | None = None) -> bool:
        """Create memory, evidence, scopes, action, audit, and outbox in one transaction."""
        if memory.status.value == "ACTIVE" and memory.embedding is None:
            raise ValueError("ACTIVE memories must be embedded before persistence")
        def create(connection: Connection) -> bool:
            if not self._insert_memory(connection, memory):
                return False
            self._insert_provenance(connection, memory, sources, scopes, task_id,
                                    prompt_version=prompt_version, model_id=model_id)
            return True
        return self._database.transaction(create)

    def replace_atomic(self, *, current_id: UUID, replacement: Memory,
                       sources: list[MemorySource] | None = None, scopes: list[MemoryScope] | None = None,
                       task_id: UUID | None = None, prompt_version: str | None = None,
                       model_id: str | None = None) -> None:
        """Create successor and atomically retire the old memory with new -> old SUPERSEDES semantics."""
        if replacement.status.value == "ACTIVE" and replacement.embedding is None:
            raise ValueError("ACTIVE replacement memories must be embedded before persistence")
        def replace(connection: Connection) -> None:
            if not self._insert_memory(connection, replacement):
                raise ValueError("replacement memory already exists; original was not superseded")
            result = connection.execute(text("""
                UPDATE memories SET status = 'SUPERSEDED', superseded_by = :replacement_id,
                    valid_until = now(), updated_at = now()
                WHERE id = :current_id AND organization_id = :organization_id
                  AND repository_id = :repository_id AND status = 'ACTIVE'
            """), {"replacement_id": replacement.id, "current_id": current_id,
                   "organization_id": replacement.organization_id, "repository_id": replacement.repository_id})
            if result.rowcount != 1:
                raise ValueError("memory is not active, not in this tenant, or no longer exists")
            connection.execute(text("""
                INSERT INTO memory_relationships (
                    id, source_memory_id, target_memory_id, relationship, created_by
                ) VALUES (:id, :replacement_id, :current_id, 'SUPERSEDES', 'trace-governor')
            """), {"id": uuid4(), "replacement_id": replacement.id, "current_id": current_id})
            self._insert_provenance(connection, replacement, sources or [], scopes or [], task_id,
                                    prompt_version=prompt_version, model_id=model_id)
            connection.execute(text("""
                INSERT INTO audit_events (
                    id, organization_id, repository_id, event_type, actor_type, actor_id,
                    entity_type, entity_id, details
                ) VALUES (
                    :id, :organization_id, :repository_id, 'MEMORY_SUPERSEDED', 'SYSTEM',
                    'trace-governor', 'memory', :current_id, CAST(:details AS JSONB)
                )
            """), {"id": uuid4(), "organization_id": replacement.organization_id,
                   "repository_id": replacement.repository_id, "current_id": current_id,
                   "details": json.dumps({"replacement_id": str(replacement.id)})})
        self._database.transaction(replace)

    def vector_candidates(self, *, organization_id: UUID, repository_id: UUID, embedding: str,
                          limit: int = 20, include_relationships: bool = True) -> list[dict[str, object]]:
        """Retrieve active indexed candidates, then enrich them with scopes, feedback, and relationships."""
        with self._database.engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text("""
                WITH nearest AS MATERIALIZED (
                    SELECT id, embedding <-> CAST(:embedding AS VECTOR) AS vector_distance
                    FROM memories
                    WHERE organization_id = :organization_id AND repository_id = :repository_id
                    ORDER BY embedding <-> CAST(:embedding AS VECTOR)
                    LIMIT :index_limit
                )
                SELECT m.id, m.display_id, m.title, m.decision, m.rationale, m.confidence,
                       m.security_relevant, nearest.vector_distance
                FROM nearest JOIN memories m ON m.id = nearest.id
                WHERE m.status = 'ACTIVE' AND m.embedding IS NOT NULL
                ORDER BY nearest.vector_distance LIMIT :limit
            """), {"organization_id": organization_id, "repository_id": repository_id,
                   "embedding": embedding, "index_limit": min(max(limit * 5, limit), 100),
                   "limit": limit}).mappings()]
            if not rows:
                return []
            ids = [row["id"] for row in rows]
            enrich = text("""
                SELECT m.id,
                    COALESCE(array_agg(DISTINCT s.scope_value) FILTER (WHERE s.scope_value IS NOT NULL), ARRAY[]) AS scopes,
                    COALESCE(avg(CASE f.feedback_type WHEN 'USEFUL' THEN 1.0 WHEN 'IRRELEVANT' THEN -0.5
                        WHEN 'OUTDATED' THEN -1.0 WHEN 'INCORRECT' THEN -1.0 END), 0.0) AS feedback_score
                FROM memories m
                LEFT JOIN memory_scopes s ON s.memory_id = m.id
                LEFT JOIN memory_feedback f ON f.memory_id = m.id
                WHERE m.id IN :ids GROUP BY m.id
            """).bindparams(bindparam("ids", expanding=True))
            extras = {row["id"]: dict(row) for row in connection.execute(enrich, {"ids": ids}).mappings()}
            source_query = text("""
                SELECT memory_id, source_type, source_external_id, source_url, commit_sha,
                       mr_iid, issue_iid, source_excerpt, captured_at
                FROM memory_sources WHERE memory_id IN :ids ORDER BY captured_at
            """).bindparams(bindparam("ids", expanding=True))
            source_map: dict[UUID, list[dict[str, object]]] = {value: [] for value in ids}
            for source in connection.execute(source_query, {"ids": ids}).mappings():
                source_map[source["memory_id"]].append(dict(source))
            relationship_map: dict[UUID, list[dict[str, object]]] = {value: [] for value in ids}
            if include_relationships:
                relations = text("""
                    SELECT r.source_memory_id, r.target_memory_id, r.relationship,
                           related.id AS related_id, related.display_id, related.decision,
                           related.status, related.confidence, related.security_relevant
                    FROM memory_relationships r
                    JOIN memories related ON related.id = CASE
                        WHEN r.source_memory_id IN :ids THEN r.target_memory_id ELSE r.source_memory_id END
                    WHERE (r.source_memory_id IN :ids OR r.target_memory_id IN :ids)
                      AND related.organization_id = :organization_id AND related.repository_id = :repository_id
                """).bindparams(bindparam("ids", expanding=True))
                for relation in connection.execute(relations, {"ids": ids, "organization_id": organization_id,
                                                               "repository_id": repository_id}).mappings():
                    relation = dict(relation)
                    for memory_id in ids:
                        if memory_id in {relation["source_memory_id"], relation["target_memory_id"]}:
                            relationship_map[memory_id].append(relation)
            for row in rows:
                row.update(extras.get(row["id"], {"scopes": [], "feedback_score": 0.0}))
                row["sources"] = source_map[row["id"]]
                row["relationships"] = relationship_map[row["id"]]
            return rows

    def record_retrieval(self, *, task_id: UUID, query_text: str, embedding_model: str,
                         ranked: list[RankedCandidate], candidates: list[dict[str, object]],
                         selected_ids: set[str], reasons: dict[str, str], llm_scores: dict[str, float],
                         final_action: str,
                         prompt_version: str | None, model_id: str | None) -> UUID:
        event_id = uuid4()
        by_display = {str(candidate["display_id"]): candidate for candidate in candidates}
        def record(connection: Connection) -> UUID:
            connection.execute(text("""
                INSERT INTO retrieval_events (
                    id, task_id, query_text, embedding_model, candidate_count, selected_count,
                    final_action, prompt_version, model_id
                ) VALUES (
                    :id, :task_id, :query_text, :embedding_model, :candidate_count, :selected_count,
                    :final_action, :prompt_version, :model_id
                )
            """), {"id": event_id, "task_id": task_id, "query_text": query_text[:10000],
                   "embedding_model": embedding_model, "candidate_count": len(ranked),
                   "selected_count": len(selected_ids), "final_action": final_action,
                   "prompt_version": prompt_version, "model_id": model_id})
            for item in ranked:
                candidate = by_display[item.memory_id]
                connection.execute(text("""
                    INSERT INTO retrieval_candidates (
                        id, retrieval_event_id, memory_id, vector_distance, semantic_score,
                        scope_score, confidence_score, security_boost, feedback_score,
                        pre_rerank_score, llm_rerank_score, selected, selection_reason
                    ) VALUES (
                        :id, :event_id, :memory_id, :vector_distance, :semantic_score,
                        :scope_score, :confidence_score, :security_boost, :feedback_score,
                        :pre_rerank_score, :llm_rerank_score, :selected, :selection_reason
                    )
                """), {"id": uuid4(), "event_id": event_id, "memory_id": candidate["id"],
                       "vector_distance": item.vector_distance, "semantic_score": item.semantic_score,
                       "scope_score": item.scope_score, "confidence_score": item.confidence_score,
                       "security_boost": item.security_boost, "feedback_score": item.feedback_score,
                       "pre_rerank_score": item.pre_rerank_score,
                       "llm_rerank_score": llm_scores.get(item.memory_id),
                       "selected": item.memory_id in selected_ids,
                       "selection_reason": reasons.get(item.memory_id, item.explanation)})
            return event_id
        return self._database.transaction(record)

    def memories_needing_embedding(self, *, organization_id: UUID, repository_id: UUID,
                                   model_id: str, version: str, limit: int = 100) -> list[dict[str, object]]:
        with self._database.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text("""
                SELECT id, decision, rationale, future_implication FROM memories
                WHERE organization_id = :organization_id AND repository_id = :repository_id
                  AND (embedding IS NULL OR embedding_model != :model_id OR embedding_version != :version)
                ORDER BY created_at LIMIT :limit
            """), {"organization_id": organization_id, "repository_id": repository_id,
                   "model_id": model_id, "version": version, "limit": limit}).mappings()]

    def update_embedding(self, memory_id: UUID, *, embedding: list[float], model_id: str,
                         version: str, embedded_at: datetime) -> None:
        self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE memories SET embedding = CAST(:embedding AS VECTOR), embedding_model = :model_id,
                embedding_version = :version, embedded_at = :embedded_at, updated_at = now()
            WHERE id = :id
        """), {"id": memory_id, "embedding": serialize_vector(embedding), "model_id": model_id,
               "version": version, "embedded_at": embedded_at}))


class RuntimeRepository:
    """Durable task/outbox leases; database attempt_count is retry truth."""

    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    def admit(self, task: AgentTask, event: OutboxEvent) -> bool:
        def insert(connection: Connection) -> bool:
            values = task.model_dump(mode="json")
            values.update(payload=json.dumps(task.payload), checkpoint=json.dumps(task.checkpoint))
            result = connection.execute(text("""
                INSERT INTO agent_tasks (
                    id, organization_id, repository_id, task_type, idempotency_key, status,
                    payload, attempt_count, max_attempts, scheduled_at, locked_until, checkpoint,
                    external_effect_id, created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :repository_id, :task_type, :idempotency_key, :status,
                    CAST(:payload AS JSONB), :attempt_count, :max_attempts, :scheduled_at,
                    :locked_until, CAST(:checkpoint AS JSONB), :external_effect_id, :created_at, :updated_at
                ) ON CONFLICT (repository_id, idempotency_key) DO NOTHING RETURNING id
            """), values)
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

    def claim_outbox(self, *, worker_id: UUID, lease_seconds: int = 60,
                     limit: int = 50) -> list[dict[str, object]]:
        locked_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        def claim(connection: Connection) -> list[dict[str, object]]:
            return [dict(row) for row in connection.execute(text("""
                WITH ready AS (
                    SELECT id FROM outbox_events
                    WHERE published_at IS NULL AND (locked_until IS NULL OR locked_until < now())
                    ORDER BY created_at LIMIT :limit
                )
                UPDATE outbox_events SET claim_token = :worker_id,
                    locked_until = :locked_until,
                    publish_attempts = publish_attempts + 1
                WHERE id IN (SELECT id FROM ready) AND published_at IS NULL
                  AND (locked_until IS NULL OR locked_until < now())
                RETURNING id, organization_id, repository_id, aggregate_type, aggregate_id,
                    event_type, payload, deduplication_key, created_at, claim_token
            """), {"worker_id": worker_id, "locked_until": locked_until, "limit": limit}).mappings()]
        return self._database.transaction(claim)

    def mark_published(self, event_id: UUID, *, worker_id: UUID) -> bool:
        return self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE outbox_events SET published_at = now(), locked_until = NULL, last_error = NULL
            WHERE id = :id AND claim_token = :worker_id AND published_at IS NULL
        """), {"id": event_id, "worker_id": worker_id}).rowcount == 1)

    def release_outbox(self, event_id: UUID, *, worker_id: UUID, error: str) -> None:
        self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE outbox_events SET locked_until = NULL, last_error = :error
            WHERE id = :id AND claim_token = :worker_id AND published_at IS NULL
        """), {"id": event_id, "worker_id": worker_id, "error": error[:2000]}))

    def start_task(self, task_id: UUID, *, lease_seconds: int = 180) -> int | None:
        locked_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        def update(connection: Connection) -> int | None:
            result = connection.execute(text("""
                UPDATE agent_tasks SET status = 'RUNNING', started_at = COALESCE(started_at, now()),
                    locked_until = :locked_until,
                    attempt_count = attempt_count + 1, updated_at = now()
                WHERE id = :id AND scheduled_at <= now() AND attempt_count < max_attempts
                  AND (status IN ('PENDING', 'RETRY_SCHEDULED')
                       OR (status = 'RUNNING' AND locked_until < now()))
                RETURNING attempt_count
            """), {"id": task_id, "locked_until": locked_until})
            return result.scalar_one_or_none()
        return self._database.transaction(update)

    def task_status(self, task_id: UUID) -> str | None:
        with self._database.engine.connect() as connection:
            return connection.execute(text(
                "SELECT status FROM agent_tasks WHERE id = :id"
            ), {"id": task_id}).scalar_one_or_none()

    def checkpoint_task(self, task_id: UUID, checkpoint: dict[str, object], *, lease_seconds: int = 180) -> None:
        locked_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        self._database.transaction(lambda connection: connection.execute(text("""
            UPDATE agent_tasks SET checkpoint = CAST(:checkpoint AS JSONB),
                locked_until = :locked_until, updated_at = now()
            WHERE id = :id AND status = 'RUNNING'
        """), {"id": task_id, "checkpoint": json.dumps(checkpoint), "locked_until": locked_until}))

    def record_external_effect(self, task_id: UUID, *, action_type: str, external_id: str,
                               prompt_version: str | None, model_id: str | None,
                               output_summary: str) -> None:
        def record(connection: Connection) -> None:
            connection.execute(text("""
                UPDATE agent_tasks SET external_effect_id = :external_id,
                    checkpoint = checkpoint || CAST(:checkpoint AS JSONB), updated_at = now()
                WHERE id = :task_id
            """), {"task_id": task_id, "external_id": external_id,
                   "checkpoint": json.dumps({"external_effect_id": external_id})})
            connection.execute(text("""
                INSERT INTO agent_actions (
                    id, task_id, action_type, actor_type, actor_id, prompt_version, model_id,
                    input_summary, output_summary, external_effect_id
                ) VALUES (
                    :id, :task_id, :action_type, 'AGENT', 'trace-runtime', :prompt_version,
                    :model_id, 'deduplicated GitHub publication', :output_summary, :external_id
                )
            """), {"id": uuid4(), "task_id": task_id, "action_type": action_type,
                   "prompt_version": prompt_version, "model_id": model_id,
                   "output_summary": output_summary[:1000], "external_id": external_id})
        self._database.transaction(record)

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
                scheduled_at = :scheduled_at, locked_until = NULL,
                completed_at = CASE WHEN :completed THEN now() ELSE NULL END,
                updated_at = now() WHERE id = :id
        """), {"id": task_id, "status": status.value, "error": error,
               "scheduled_at": scheduled_at, "completed": completed}))
