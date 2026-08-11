from uuid import uuid4

from trace_memory.agents.memory_governor import MemoryGovernor
from trace_memory.domain import ActorType, Memory, MemoryStatus, MemoryType


class Repository:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def create(self, memory: Memory) -> None:
        self.events.append(("create", memory.id))

    def supersede(self, *, current_id: object, replacement_id: object) -> None:
        self.events.append(("supersede", current_id, replacement_id))


def replacement() -> Memory:
    return Memory(organization_id=uuid4(), repository_id=uuid4(), display_id="TRACE-MEMORY-100",
                  memory_type=MemoryType.ARCHITECTURAL_DECISION, title="Use pool", decision="Use pooling",
                  rationale="Avoid exhaustion", future_implication="Reuse connections", confidence=0.9,
                  confidence_basis="incident", status=MemoryStatus.ACTIVE, content_hash="a", semantic_key="pool",
                  created_by_actor_type=ActorType.HUMAN, created_by_actor_id="vivek")


def test_intentional_override_preserves_history_by_creating_then_superseding() -> None:
    repository = Repository()
    new = MemoryGovernor(repository).intentional_override(current_id=uuid4(), replacement=replacement())
    assert repository.events[0] == ("create", new.id)
    assert repository.events[1][0] == "supersede"
