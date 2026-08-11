"""Deterministic score composition persisted with retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedCandidate:
    memory_id: str
    vector_distance: float
    semantic_score: float
    scope_score: float
    confidence_score: float
    security_boost: float
    feedback_score: float
    pre_rerank_score: float
    explanation: str


class HybridRanker:
    """Scores Cockroach vector candidates without opaque post-processing."""

    def rank(self, candidates: list[dict[str, object]], *, changed_paths: list[str]) -> list[RankedCandidate]:
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            distance = float(candidate.get("vector_distance", 1.0))
            semantic = max(0.0, 1.0 - distance)
            scopes = [str(value) for value in candidate.get("scopes", [])]
            scope = 1.0 if any(path in scopes for path in changed_paths) else 0.0
            confidence = float(candidate.get("confidence", 0.5))
            security = 0.15 if bool(candidate.get("security_relevant")) else 0.0
            feedback = float(candidate.get("feedback_score", 0.0))
            total = (0.55 * semantic) + (0.20 * scope) + (0.15 * confidence) + security + (0.10 * feedback)
            ranked.append(RankedCandidate(
                memory_id=str(candidate["display_id"]), vector_distance=distance, semantic_score=semantic,
                scope_score=scope, confidence_score=confidence, security_boost=security,
                feedback_score=feedback, pre_rerank_score=total,
                explanation=(f"semantic={semantic:.2f}; scope={scope:.2f}; confidence={confidence:.2f}; "
                             f"security_boost={security:.2f}; feedback={feedback:.2f}"),
            ))
        return sorted(ranked, key=lambda item: item.pre_rerank_score, reverse=True)
