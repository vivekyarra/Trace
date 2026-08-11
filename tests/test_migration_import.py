from pathlib import Path
from uuid import uuid4

import pytest

from lore.domain import MemoryStatus, MemoryType
from lore.migration import LegacyMemoryImporter, _sql_statements


class Sink:
    def __init__(self):
        self.memories = []

    def create(self, memory):
        self.memories.append(memory)
        return True


LEGACY = """LORE Memory #12
Source MR: !42 — Fix auth
Decision: Use signed sessions
Rejected: Plain cookies
Reason: Prevent tampering
Future implication: All sessions must be signed
Confidence: HIGH
Status: Active
Incident type: auth
Security relevant: yes
"""


def test_legacy_import_preserves_governance_fields() -> None:
    sink = Sink()
    report = LegacyMemoryImporter(sink, uuid4(), uuid4()).import_text(LEGACY)
    assert report.imported == 1 and report.skipped == 0
    memory = sink.memories[0]
    assert memory.display_id == "LORE-MEMORY-012"
    assert memory.memory_type is MemoryType.SECURITY_CONSTRAINT
    assert memory.status is MemoryStatus.ACTIVE and memory.confidence == 0.9


def test_import_rejects_incomplete_memory_in_strict_mode() -> None:
    sink = Sink()
    content = LEGACY + "\nLORE Memory #13\nDecision: X"
    with pytest.raises(ValueError, match="before writes"):
        LegacyMemoryImporter(sink, uuid4(), uuid4()).import_text(content)
    assert sink.memories == []


def test_duplicate_memory_is_reported_as_skipped() -> None:
    class DuplicateSink(Sink):
        def create(self, memory):
            return False

    report = LegacyMemoryImporter(DuplicateSink(), uuid4(), uuid4()).import_text(LEGACY)
    assert report.imported == 0 and report.skipped == 1


def test_all_migrations_are_split_into_statements() -> None:
    for path in Path("migrations").glob("*.sql"):
        assert _sql_statements(path.read_text(encoding="utf-8"))
