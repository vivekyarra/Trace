"""Run the real PR A -> memory -> PR B retrieval proof against configured cloud services."""

from __future__ import annotations

import json
import os
from uuid import UUID

from sqlalchemy import text

from trace_memory.agents import Guardkeeper
from trace_memory.ai import BedrockEmbedder, BedrockReasoner
from trace_memory.persistence import CockroachDatabase, MemoryRepository, RuntimeRepository
from trace_memory.runtime.automation import GitHubAutomation
from trace_memory.runtime.github import GitHubClient
from trace_memory.security import validate_database_url


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> int:
    database_url = required("DATABASE_URL")
    validate_database_url(database_url)
    organization_id = UUID(required("TRACE_ORGANIZATION_ID"))
    repository_id = UUID(required("TRACE_REPOSITORY_ID"))
    task_a = UUID(required("TRACE_TASK_A"))
    task_b = UUID(required("TRACE_TASK_B"))
    pr_a = int(required("TRACE_PR_A"))
    pr_b = int(required("TRACE_PR_B"))

    database = CockroachDatabase.from_url(database_url)
    memories = MemoryRepository(database)
    runtime = RuntimeRepository(database)
    reasoner = BedrockReasoner()
    embedder = BedrockEmbedder()
    automation = GitHubAutomation(
        github=GitHubClient(required("TRACE_GITHUB_TOKEN"), required("TRACE_GITHUB_REPOSITORY")),
        reasoner=reasoner,
        embedder=embedder,
        guardkeeper=Guardkeeper(memories, reasoner=reasoner),
        memories=memories,
        organization_id=organization_id,
        repository_id=repository_id,
        effects=runtime,
    )

    automation({"aggregate_id": str(task_a), "payload": {"pull_request_number": pr_a,
                                                           "delivery_id": "trace-live-pr-a"}})
    runtime.finish_task(task_a)
    automation({"aggregate_id": str(task_b), "payload": {"pull_request_number": pr_b,
                                                           "delivery_id": "trace-live-pr-b"}})
    runtime.finish_task(task_b)

    with database.engine.connect() as connection:
        evidence = dict(connection.execute(text("""
            SELECT
              a.id AS task_a_id,
              a.external_effect_id AS pr_a_comment_id,
              b.id AS task_b_id,
              b.external_effect_id AS pr_b_comment_id,
              m.id AS memory_id,
              m.display_id,
              m.embedding IS NOT NULL AS titan_vector_stored,
              m.embedding_model,
              s.source_url,
              r.id AS retrieval_id,
              c.pre_rerank_score,
              c.selected,
              c.selection_reason
            FROM agent_tasks a
            JOIN agent_tasks b ON b.id = :task_b
            JOIN memories m ON m.repository_id = a.repository_id
            JOIN memory_sources s ON s.memory_id = m.id AND s.mr_iid = :pr_a
            JOIN retrieval_events r ON r.task_id = b.id
            JOIN retrieval_candidates c ON c.retrieval_event_id = r.id AND c.memory_id = m.id
            WHERE a.id = :task_a
            ORDER BY r.created_at DESC LIMIT 1
        """), {"task_a": task_a, "task_b": task_b, "pr_a": pr_a}).mappings().one())
    print(json.dumps(evidence, default=str, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
