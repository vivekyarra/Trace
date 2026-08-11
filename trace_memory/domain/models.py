"""Typed domain records shared by persistence, agents, and transport layers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for domain defaults."""
    return datetime.now(timezone.utc)


class TraceModel(BaseModel):
    """Base model that rejects unrecognised fields at system boundaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MemoryType(StrEnum):
    ARCHITECTURAL_DECISION = "ARCHITECTURAL_DECISION"
    INCIDENT_LESSON = "INCIDENT_LESSON"
    SECURITY_CONSTRAINT = "SECURITY_CONSTRAINT"
    REVIEW_PATTERN = "REVIEW_PATTERN"
    DEVELOPER_COMMITMENT = "DEVELOPER_COMMITMENT"
    CODE_PATTERN = "CODE_PATTERN"


class MemoryStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISPUTED = "DISPUTED"
    SUPERSEDED = "SUPERSEDED"
    DEPRECATED = "DEPRECATED"


class RelationshipType(StrEnum):
    DEPENDS_ON = "DEPENDS_ON"
    BLOCKS = "BLOCKS"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    CAUSED_BY = "CAUSED_BY"
    MITIGATES = "MITIGATES"
    RELATED_TO = "RELATED_TO"
    DERIVED_FROM = "DERIVED_FROM"


class FeedbackType(StrEnum):
    USEFUL = "USEFUL"
    IRRELEVANT = "IRRELEVANT"
    OUTDATED = "OUTDATED"
    INCORRECT = "INCORRECT"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    DEAD_LETTERED = "DEAD_LETTERED"


class SourceType(StrEnum):
    MR = "MR"
    MR_COMMENT = "MR_COMMENT"
    ISSUE = "ISSUE"
    COMMIT = "COMMIT"
    INCIDENT = "INCIDENT"
    ADR = "ADR"
    CODE = "CODE"
    IMPORT = "IMPORT"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"


class ScopeType(StrEnum):
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    SERVICE = "SERVICE"
    DOMAIN = "DOMAIN"
    LANGUAGE = "LANGUAGE"
    REPOSITORY = "REPOSITORY"


class ActorType(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class Memory(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    repository_id: UUID
    display_id: str = Field(pattern=r"^TRACE-MEMORY-[0-9]{3,}$")
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=300)
    decision: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    rejected_alternative: str | None = None
    future_implication: str = Field(min_length=1)
    status: MemoryStatus = MemoryStatus.DRAFT
    confidence: float = Field(ge=0, le=1)
    confidence_basis: str = Field(min_length=1)
    security_relevant: bool = False
    severity: str | None = None
    content_hash: str = Field(min_length=1)
    semantic_key: str = Field(min_length=1)
    embedding_model: str | None = None
    embedding_version: str | None = None
    embedded_at: datetime | None = None
    valid_from: datetime = Field(default_factory=utc_now)
    valid_until: datetime | None = None
    superseded_by: UUID | None = None
    version: int = Field(default=1, ge=1)
    created_by_actor_type: ActorType
    created_by_actor_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Memory:
        if self.status is MemoryStatus.SUPERSEDED and self.superseded_by is None:
            raise ValueError("SUPERSEDED memories require superseded_by")
        if self.status is not MemoryStatus.SUPERSEDED and self.superseded_by is not None:
            raise ValueError("only SUPERSEDED memories may set superseded_by")
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("valid_until cannot precede valid_from")
        if (self.embedding_model is None) != (self.embedding_version is None):
            raise ValueError("embedding model and version must be set together")
        return self


class MemorySource(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    memory_id: UUID
    source_type: SourceType
    source_external_id: str | None = None
    source_url: str | None = None
    commit_sha: str | None = None
    mr_iid: int | None = Field(default=None, ge=1)
    issue_iid: int | None = Field(default=None, ge=1)
    incident_external_id: str | None = None
    author_external_id: str | None = None
    author_name: str | None = None
    source_excerpt: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)


class MemoryScope(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    memory_id: UUID
    scope_type: ScopeType
    scope_value: str = Field(min_length=1)


class MemoryRelationship(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    source_memory_id: UUID
    target_memory_id: UUID
    relationship: RelationshipType
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_distinct_memories(self) -> MemoryRelationship:
        if self.source_memory_id == self.target_memory_id:
            raise ValueError("a memory cannot relate to itself")
        return self


class AgentTask(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    repository_id: UUID
    task_type: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PENDING
    payload: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    scheduled_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RetrievalEvent(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    query_text: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_counts(self) -> RetrievalEvent:
        if self.selected_count > self.candidate_count:
            raise ValueError("selected_count cannot exceed candidate_count")
        return self


class RetrievalCandidate(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    retrieval_event_id: UUID
    memory_id: UUID
    vector_distance: float | None = None
    semantic_score: float = Field(ge=0, le=1)
    scope_score: float = Field(ge=0, le=1)
    confidence_score: float = Field(ge=0, le=1)
    security_boost: float = Field(default=0, ge=0)
    feedback_score: float = Field(default=0, ge=0, le=1)
    pre_rerank_score: float = Field(ge=0)
    llm_rerank_score: float | None = Field(default=None, ge=0, le=1)
    selected: bool = False
    selection_reason: str | None = None


class AgentAction(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    action_type: str = Field(min_length=1)
    actor_type: ActorType
    actor_id: str = Field(min_length=1)
    prompt_version: str | None = None
    input_summary: str = Field(min_length=1)
    output_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class MemoryFeedback(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    memory_id: UUID
    retrieval_event_id: UUID | None = None
    feedback_type: FeedbackType
    actor_id: str = Field(min_length=1)
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AuditEvent(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    repository_id: UUID | None = None
    event_type: str = Field(min_length=1)
    actor_type: ActorType
    actor_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: UUID
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class OutboxEvent(TraceModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    repository_id: UUID
    aggregate_type: str = Field(min_length=1)
    aggregate_id: UUID
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    deduplication_key: str = Field(min_length=1)
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

