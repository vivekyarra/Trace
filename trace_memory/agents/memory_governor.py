"""Controlled memory evolution for `trace: intentional` replies."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from trace_memory.domain import Memory


class MemoryWriter(Protocol):
    def replace_atomic(self, *, current_id: UUID, replacement: Memory, **kwargs: object) -> None: ...


class MemoryGovernor:
    """Delegates the entire successor transition to one CockroachDB transaction."""

    def __init__(self, repository: MemoryWriter) -> None:
        self._repository = repository

    def intentional_override(self, *, current_id: UUID, replacement: Memory) -> Memory:
        if replacement.superseded_by is not None:
            raise ValueError("replacement memory must begin active, not pre-superseded")
        self._repository.replace_atomic(current_id=current_id, replacement=replacement)
        return replacement
