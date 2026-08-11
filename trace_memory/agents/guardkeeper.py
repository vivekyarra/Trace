"""Deterministic guardrails around Bedrock reasoning and CockroachDB retrieval."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class FindingLayer(StrEnum):
    MEMORY_CONFLICT = "MEMORY_CONFLICT"
    PROMISE = "PROMISE"
    SECURITY = "SECURITY"
    CODE_INTELLIGENCE = "CODE_INTELLIGENCE"
    PATTERN_RULE = "PATTERN_RULE"


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer: FindingLayer
    severity: str = Field(pattern=r"^(LOW|MEDIUM|HIGH)$")
    summary: str
    evidence: str
    memory_id: str | None = None


class GuardkeeperReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[ReviewFinding] = Field(default_factory=list)
    prompt_version: str = "guardkeeper-review-v1"


class CandidateSource(Protocol):
    def vector_candidates(self, **kwargs: object) -> list[dict[str, object]]: ...


class Guardkeeper:
    """Fail-safe review: deterministic security checks run even if reasoning fails."""

    _security_tokens = ("eval(", "md5(", "password=", "api_key=", "secret=")

    def __init__(self, candidates: CandidateSource) -> None:
        self._candidates = candidates

    def review(self, *, organization_id: object, repository_id: object, embedding: str,
               diff: str, promises: list[str] | None = None) -> GuardkeeperReview:
        findings: list[ReviewFinding] = []
        normalized = diff.lower()
        for token in self._security_tokens:
            if token in normalized:
                findings.append(ReviewFinding(
                    layer=FindingLayer.SECURITY, severity="HIGH",
                    summary=f"Potential security regression: {token}",
                    evidence="Detected directly in the proposed diff.",
                ))
        for candidate in self._candidates.vector_candidates(
            organization_id=organization_id, repository_id=repository_id, embedding=embedding, limit=20
        ):
            decision = str(candidate.get("decision", ""))
            if decision and any(word in normalized for word in decision.lower().split() if len(word) > 6):
                findings.append(ReviewFinding(
                    layer=FindingLayer.MEMORY_CONFLICT,
                    severity="HIGH" if bool(candidate.get("security_relevant")) else "MEDIUM",
                    summary=f"May conflict with {candidate.get('display_id', 'stored memory')}",
                    evidence=decision,
                    memory_id=str(candidate.get("display_id", "")) or None,
                ))
        for promise in promises or []:
            if promise.lower() not in normalized:
                findings.append(ReviewFinding(
                    layer=FindingLayer.PROMISE, severity="MEDIUM",
                    summary="Declared implementation promise is not visible in the diff.", evidence=promise,
                ))
        return GuardkeeperReview(findings=findings)
