from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trace_memory.domain import (
    ActorType,
    Memory,
    MemoryRelationship,
    MemoryStatus,
    MemoryType,
    RelationshipType,
    RetrievalEvent,
)


def make_memory(**overrides: object) -> Memory:
    values: dict[str, object] = {
        "organization_id": uuid4(),
        "repository_id": uuid4(),
        "display_id": "TRACE-MEMORY-001",
        "memory_type": MemoryType.ARCHITECTURAL_DECISION,
        "title": "Use fixed retry intervals",
        "decision": "Use fixed retry intervals for webhook retries.",
        "rationale": "Fixed intervals prevent retry storms.",
        "future_implication": "New webhook retries use fixed intervals.",
        "confidence": 0.9,
        "confidence_basis": "Incident review and MR discussion.",
        "content_hash": "sha256:example",
        "semantic_key": "retry.fixed-interval",
        "created_by_actor_type": ActorType.HUMAN,
        "created_by_actor_id": "vivek",
    }
    values.update(overrides)
    return Memory(**values)


def test_memory_defaults_are_timezone_aware() -> None:
    memory = make_memory()

    assert memory.created_at.tzinfo is not None
    assert memory.updated_at.tzinfo is not None
    assert memory.status is MemoryStatus.DRAFT


def test_superseded_memory_requires_replacement() -> None:
    with pytest.raises(ValidationError, match="require superseded_by"):
        make_memory(status=MemoryStatus.SUPERSEDED)


def test_memory_rejects_incompatible_embedding_metadata() -> None:
    with pytest.raises(ValidationError, match="model and version"):
        make_memory(embedding_model="amazon.titan-embed-text-v2:0")


def test_memory_rejects_invalid_validity_window() -> None:
    memory = make_memory()

    with pytest.raises(ValidationError, match="valid_until"):
        make_memory(valid_until=memory.valid_from - timedelta(seconds=1))


def test_relationship_cannot_target_itself() -> None:
    memory_id = uuid4()

    with pytest.raises(ValidationError, match="cannot relate to itself"):
        MemoryRelationship(
            source_memory_id=memory_id,
            target_memory_id=memory_id,
            relationship=RelationshipType.RELATED_TO,
            created_by="tracekeeper",
        )


def test_retrieval_event_requires_selected_count_to_be_bounded() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        RetrievalEvent(
            task_id=uuid4(),
            query_text="Check authorization cache policy",
            embedding_model="amazon.titan-embed-text-v2:0",
            candidate_count=2,
            selected_count=3,
        )
