from uuid import uuid4

from trace_memory.agents.memory_governor import MemoryGovernor
from trace_memory.domain import ActorType, Memory, MemoryStatus, MemoryType


class Repository:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def replace_atomic(self, *, current_id: object, replacement: Memory) -> None:
        self.events.append(("replace_atomic", current_id, replacement.id))


def replacement() -> Memory:
    return Memory(organization_id=uuid4(), repository_id=uuid4(), display_id="TRACE-MEMORY-100",
                  memory_type=MemoryType.ARCHITECTURAL_DECISION, title="Use pool", decision="Use pooling",
                  rationale="Avoid exhaustion", future_implication="Reuse connections", confidence=0.9,
                  confidence_basis="incident", status=MemoryStatus.ACTIVE, content_hash="a", semantic_key="pool",
                  created_by_actor_type=ActorType.HUMAN, created_by_actor_id="vivek")


def test_intentional_override_uses_one_atomic_repository_operation() -> None:
    repository = Repository()
    new = MemoryGovernor(repository).intentional_override(current_id=uuid4(), replacement=replacement())
    assert repository.events == [("replace_atomic", repository.events[0][1], new.id)]
