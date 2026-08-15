"""Read-only production Guardkeeper pipeline shared by HTTP and worker entry points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Protocol
from uuid import UUID

from trace_memory.agents import Guardkeeper
from trace_memory.agents.guardkeeper import FindingLayer, GuardkeeperReview
from trace_memory.ai import BedrockEmbedder, BedrockReasoner
from trace_memory.persistence import CockroachDatabase, MemoryRepository, serialize_vector


class Embedder(Protocol):
    model_id: str

    def embed(self, text: str) -> object: ...


@dataclass
class ReadOnlyReviewPipeline:
    """Execute the same Guardkeeper used by production without persisting a demo run."""

    embedder: Embedder
    guardkeeper: Guardkeeper

    def run(self, *, organization_id: UUID, repository_id: UUID, diff: str) -> dict[str, object]:
        if not diff.strip():
            raise ValueError("Paste a pull-request diff or use the PR #5 preset")
        if len(diff) > 15_000:
            raise ValueError("Diff is too large for the public demo (15,000 character limit)")

        started = perf_counter()
        embedding_started = perf_counter()
        embedded = self.embedder.embed(diff)
        embedding_latency_ms = round((perf_counter() - embedding_started) * 1000)
        values = list(getattr(embedded, "values"))
        vector = serialize_vector(values)
        if vector is None:
            raise ValueError("Embedding result was empty")

        review = self.guardkeeper.review(
            organization_id=organization_id,
            repository_id=repository_id,
            embedding=vector,
            diff=diff,
            query_text=diff,
            embedding_model=str(getattr(embedded, "model_id")),
        )
        return _receipt(review, embedded, embedding_latency_ms, started)


def production_read_only_pipeline(
    *,
    database_url: str,
    embedding_model_id: str,
    reasoning_model_id: str,
    fallback_model_id: str,
) -> ReadOnlyReviewPipeline:
    """Construct the production repository, Bedrock adapters, and Guardkeeper."""

    database = CockroachDatabase.from_url(database_url)
    reasoner = BedrockReasoner(model_id=reasoning_model_id, fallback_model_id=fallback_model_id)
    return ReadOnlyReviewPipeline(
        embedder=BedrockEmbedder(model_id=embedding_model_id),
        guardkeeper=Guardkeeper(MemoryRepository(database), reasoner=reasoner),
    )


def _receipt(
    review: GuardkeeperReview,
    embedded: object,
    embedding_latency_ms: int,
    started: float,
) -> dict[str, object]:
    severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    severity = max(
        (finding.severity for finding in review.findings),
        key=lambda value: severity_order[value],
        default="LOW",
    )
    classification = "CONFLICT" if review.findings else "CLEAR"
    summary = review.findings[0].summary if review.findings else "No governed conflict was found."
    selected_findings = [
        {
            "display_id": finding.memory_id,
            "source_url": finding.source_url,
            "evidence": finding.evidence,
        }
        for finding in review.findings
        if finding.layer is FindingLayer.MEMORY_CONFLICT
    ]
    consequence = review.memory_consequence.model_dump(mode="json")
    consequence.update({"retrieved_candidate_count": review.candidate_count, "write_routes": 0})
    values = list(getattr(embedded, "values"))
    return {
        "mode": "LIVE",
        "pipeline": "trace_memory.agents.Guardkeeper",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_ms": round((perf_counter() - started) * 1000),
        "stages": [
            {
                "name": "Live embedding",
                "service": "Amazon Bedrock",
                "model": str(getattr(embedded, "model_id")),
                "dimensions": len(values),
                "elapsed_ms": embedding_latency_ms,
            },
            {
                "name": "Governed memory retrieval",
                "service": "CockroachDB Cloud",
                "candidate_count": review.candidate_count,
                "elapsed_ms": review.retrieval_latency_ms,
            },
            {
                "name": "Guardkeeper reasoning",
                "service": "Amazon Bedrock",
                "model": review.reasoning_model_id,
                "elapsed_ms": review.reasoning_latency_ms,
            },
        ],
        "judgment": {
            "classification": classification,
            "severity": severity,
            "summary": summary,
            "selected_memory_ids": review.selected_memory_ids,
            "final_action": review.final_action,
        },
        "findings": [finding.model_dump(mode="json") for finding in review.findings],
        "candidates": selected_findings,
        "memory_consequence_receipt": consequence,
    }
