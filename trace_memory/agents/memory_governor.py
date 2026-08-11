"""Controlled memory evolution for `trace: intentional` replies."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from trace_memory.domain import Memory


class MemoryWriter(Protocol):
    def create(self, memory: Memory) -> None: ...
    def supersede(self, *, current_id: UUID, replacement_id: UUID) -> None: ...


class MemoryGovernor:
    """Creates first, then supersedes inside the repository's retrying transaction boundary."""

    def __init__(self, repository: MemoryWriter) -> None:
        self._repository = repository

    def intentional_override(self, *, current_id: UUID, replacement: Memory) -> Memory:
        if replacement.superseded_by is not None:
            raise ValueError("replacement memory must begin active, not pre-superseded")
        self._repository.create(replacement)
        self._repository.supersede(current_id=current_id, replacement_id=replacement.id)
        return replacement
