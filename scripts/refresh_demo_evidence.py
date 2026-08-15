"""Regenerate the PR #4 -> memory -> PR #5 conflict proof with live cloud services.

This proof runner is intentionally separate from the public read-only Lambda. It uses
the production automation, Bedrock adapters, and CockroachDB repositories while
capturing the two GitHub comment bodies for an authenticated publisher to post.
"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy import text

from trace_memory.agents import Guardkeeper
from trace_memory.ai import BedrockEmbedder, BedrockReasoner
from trace_memory.domain import AgentTask, OutboxEvent
from trace_memory.persistence import CockroachDatabase, MemoryRepository, RuntimeRepository
from trace_memory.runtime.automation import GitHubAutomation


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required")
    return value


class PublicGitHubCapture:
    """Read public PR evidence and capture, but never publish, agent comments."""

    def __init__(self, repository: str) -> None:
        self.repository = repository
        self.comments: dict[int, str] = {}

    def _get(self, path: str, *, accept: str = "application/vnd.github+json") -> object:
        request = Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            headers={"Accept": accept, "User-Agent": "trace-proof-runner"},
        )
        with urlopen(request, timeout=20) as response:
            body = response.read()
        if accept == "application/vnd.github.diff":
            return body.decode("utf-8", errors="replace")
        return json.loads(body)

    def pull_request(self, number: int) -> dict[str, object]:
        return dict(self._get(f"pulls/{number}"))

    def pull_request_files(self, number: int) -> list[dict[str, object]]:
        return list(self._get(f"pulls/{number}/files?per_page=100"))

    def complete_pull_request_diff(
        self, number: int, files: list[dict[str, object]]
    ) -> tuple[str, bool]:
        incomplete = len(files) >= 100 or any(
            not item.get("patch") or bool(item.get("previous_filename"))
            for item in files
            if str(item.get("status", "")) != "removed"
        )
        patch = "\n".join(str(item.get("patch", "")) for item in files)
        if incomplete:
            full = str(self._get(f"pulls/{number}", accept="application/vnd.github.diff"))
            return full[:500_000], len(full) <= 500_000
        return patch[:500_000], len(patch) <= 500_000

    def post_comment_once(self, number: int, task_id: UUID, body: str) -> dict[str, object]:
        self.comments[number] = f"<!-- trace-task:{task_id} -->\n{body}"
        return {"id": f"CAPTURED-PR-{number}"}


class LiveProofReasoner(BedrockReasoner):
    """Production proof reasoner with the same primary/fallback path as Trace."""


def admit_task(
    runtime: RuntimeRepository,
    *,
    organization_id: UUID,
    repository_id: UUID,
    task_id: UUID,
    task_type: str,
    pr_number: int,
) -> None:
    task = AgentTask(
        id=task_id,
        organization_id=organization_id,
        repository_id=repository_id,
        task_type=task_type,
        idempotency_key=f"proof-2026-08-15-pr-{pr_number}-{task_id}",
        payload={"pull_request_number": pr_number, "delivery_id": f"proof-pr-{pr_number}"},
    )
    event = OutboxEvent(
        organization_id=organization_id,
        repository_id=repository_id,
        aggregate_type="agent_task",
        aggregate_id=task.id,
        event_type="task.admitted",
        payload=task.payload,
        deduplication_key=f"proof-2026-08-15-pr-{pr_number}-{task_id}:task.admitted",
    )
    if not runtime.admit(task, event) or runtime.start_task(task_id) is None:
        raise RuntimeError(f"could not admit proof task for PR #{pr_number}")


def main() -> int:
    database = CockroachDatabase.from_url(required("DATABASE_URL"))
    organization_id = UUID(required("TRACE_ORGANIZATION_ID"))
    repository_id = UUID(required("TRACE_REPOSITORY_ID"))
    pr_a = int(os.environ.get("TRACE_PR_A", "4"))
    pr_b = int(os.environ.get("TRACE_PR_B", "5"))
    task_a, task_b = uuid4(), uuid4()
    runtime = RuntimeRepository(database)
    memories = MemoryRepository(database)
    reasoner = LiveProofReasoner()
    github = PublicGitHubCapture(os.environ.get("TRACE_GITHUB_REPOSITORY", "vivekyarra/Trace"))
    automation = GitHubAutomation(
        github=github,
        reasoner=reasoner,
        embedder=BedrockEmbedder(),
        guardkeeper=Guardkeeper(memories, reasoner=reasoner),
        memories=memories,
        organization_id=organization_id,
        repository_id=repository_id,
        effects=runtime,
    )

    admit_task(
        runtime,
        organization_id=organization_id,
        repository_id=repository_id,
        task_id=task_a,
        task_type="tracekeeper",
        pr_number=pr_a,
    )
    automation({"aggregate_id": str(task_a), "payload": {"pull_request_number": pr_a, "delivery_id": "proof-pr-a"}})
    runtime.finish_task(task_a)

    admit_task(
        runtime,
        organization_id=organization_id,
        repository_id=repository_id,
        task_id=task_b,
        task_type="guardkeeper",
        pr_number=pr_b,
    )
    automation({"aggregate_id": str(task_b), "payload": {"pull_request_number": pr_b, "delivery_id": "proof-pr-b"}})
    runtime.finish_task(task_b)

    with database.engine.connect() as connection:
        evidence = dict(
            connection.execute(
                text(
                    """
                    SELECT a.id AS memory_task_id, b.id AS review_task_id,
                           m.id AS memory_id, m.display_id, m.created_at AS memory_created_at,
                           m.embedded_at, m.embedding_model, s.source_url, s.commit_sha,
                           r.id AS retrieval_id, r.created_at AS retrieval_created_at,
                           r.model_id AS reasoning_model, r.final_action,
                           c.selected, c.llm_rerank_score, c.selection_reason
                    FROM agent_tasks a
                    JOIN agent_tasks b ON b.id = :task_b
                    JOIN memories m ON m.repository_id = a.repository_id
                    JOIN memory_sources s ON s.memory_id = m.id AND s.mr_iid = :pr_a
                    JOIN retrieval_events r ON r.task_id = b.id
                    JOIN retrieval_candidates c ON c.retrieval_event_id = r.id AND c.memory_id = m.id
                    WHERE a.id = :task_a
                    ORDER BY r.created_at DESC LIMIT 1
                    """
                ),
                {"task_a": task_a, "task_b": task_b, "pr_a": pr_a},
            ).mappings().one()
        )
    evidence["comments"] = github.comments
    print(json.dumps(evidence, default=str, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
