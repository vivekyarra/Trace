"""Tests for lore_cli.validate — memory validation logic."""

from __future__ import annotations

import textwrap

from lore_cli.sync import parse_all_entries, parse_memory, parse_pattern_rule
from lore_cli.validate import validate_memories


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_MEMORY = textwrap.dedent("""\
    LORE Memory #001
    Source MR: !42 — Add retry logic
    Date: 2026-01-15
    Governs files: src/api/auth.py
    Decision: Use fixed retry intervals
    Rejected: Exponential backoff
    Reason: Thundering herd at 1000+ concurrent requests
    Future implication: No exponential backoff in retry logic
    Decided by: @alice, @bob
    Confidence: HIGH
    Status: Active
    Carbon impact: ~300 kWh/month saved
    Incident type: retry
    Depends on: N/A
    Blocks: N/A
    Source type: discussion
    Security relevant: no
""")

VALID_PATTERN = textwrap.dedent("""\
    LORE Pattern #001
    Source MR: !42 — Modernize type hints
    Date: 2026-01-20
    Rule: Use X | None instead of Optional
    Anti-pattern: typing.Optional[X]
    Language: python
    Reason: Optional is soft-deprecated in Python 3.10+
    Established by: @alice
    Status: Active
    Examples:
      Bad:  def get_user(id: int) -> Optional[User]:
      Good: def get_user(id: int) -> User | None:
""")


def _make_memory(**overrides: str) -> dict:
    """Parse the standard valid memory, then override specific fields."""
    mem = parse_memory(VALID_MEMORY)
    assert mem is not None
    mem.update(overrides)
    return mem


# ---------------------------------------------------------------------------
# Tests — valid inputs
# ---------------------------------------------------------------------------


class TestValidMemory:
    def test_valid_memory_passes(self):
        mem = _make_memory()
        report = validate_memories([mem])
        assert report["total"] == 1
        assert report["valid"] == 1
        assert report["errors"] == []

    def test_valid_pattern_passes(self):
        pat = parse_pattern_rule(VALID_PATTERN)
        assert pat is not None
        report = validate_memories([], patterns=[pat])
        assert report["total"] == 1
        assert report["errors"] == []


# ---------------------------------------------------------------------------
# Tests — field presence
# ---------------------------------------------------------------------------


class TestMissingFields:
    def test_missing_field_caught(self):
        mem = _make_memory()
        del mem["Decision"]
        report = validate_memories([mem])
        assert report["valid"] == 0
        assert any(
            e["field"] == "Decision" and "Missing" in e["message"]
            for e in report["errors"]
        )

    def test_missing_multiple_fields(self):
        mem = _make_memory()
        del mem["Confidence"]
        del mem["Status"]
        report = validate_memories([mem])
        fields_reported = {e["field"] for e in report["errors"]}
        assert "Confidence" in fields_reported
        assert "Status" in fields_reported


# ---------------------------------------------------------------------------
# Tests — field value constraints
# ---------------------------------------------------------------------------


class TestFieldValues:
    def test_invalid_confidence(self):
        mem = _make_memory(Confidence="VERY_HIGH")
        report = validate_memories([mem])
        assert any(
            e["field"] == "Confidence" for e in report["errors"]
        )

    def test_invalid_status(self):
        mem = _make_memory(Status="Deleted")
        report = validate_memories([mem])
        assert any(
            e["field"] == "Status" for e in report["errors"]
        )

    def test_invalid_date(self):
        mem = _make_memory(Date="15-01-2026")
        report = validate_memories([mem])
        assert any(
            e["field"] == "Date" for e in report["errors"]
        )

    def test_invalid_source_type(self):
        mem = _make_memory(**{"Source type": "email"})
        report = validate_memories([mem])
        assert any(e["field"] == "Source type" for e in report["errors"])

    def test_invalid_security_relevant(self):
        mem = _make_memory(**{"Security relevant": "maybe"})
        report = validate_memories([mem])
        assert any(e["field"] == "Security relevant" for e in report["errors"])


# ---------------------------------------------------------------------------
# Tests — dependency integrity
# ---------------------------------------------------------------------------


class TestDependencies:
    def test_broken_dependency(self):
        mem = _make_memory(**{"Depends on": "Memory #099"})
        report = validate_memories([mem])
        assert any(
            "does not exist" in e["message"] for e in report["errors"]
        )

    def test_broken_blocks_reference(self):
        mem = _make_memory(Blocks="Memory #099")
        report = validate_memories([mem])
        assert any(
            "does not exist" in e["message"] for e in report["errors"]
        )

    def test_circular_dependency(self):
        """Memory #001 depends on #002, and #002 depends on #001."""
        mem1 = _make_memory(**{"Depends on": "Memory #002"})
        mem1["id"] = 1
        mem1["Blocks"] = "N/A"

        mem2 = _make_memory(**{"Depends on": "Memory #001"})
        mem2["id"] = 2
        mem2["Blocks"] = "N/A"

        report = validate_memories([mem1, mem2])
        assert any(
            "Circular" in e["message"] for e in report["errors"]
        )

    def test_superseded_dependency_warning(self):
        """An active memory depending on a superseded one should warn."""
        mem1 = _make_memory(**{"Depends on": "Memory #002"})
        mem1["id"] = 1
        mem1["Status"] = "Active"
        mem1["Blocks"] = "N/A"

        mem2 = _make_memory()
        mem2["id"] = 2
        mem2["Status"] = "Superseded"
        mem2["Depends on"] = "N/A"
        mem2["Blocks"] = "N/A"

        report = validate_memories([mem1, mem2])
        assert any(
            "superseded" in w["message"] for w in report["warnings"]
        )


# ---------------------------------------------------------------------------
# Tests — parsing
# ---------------------------------------------------------------------------


class TestParsing:
    def test_parse_memory_returns_none_for_garbage(self):
        assert parse_memory("not a memory") is None

    def test_parse_pattern_rule_returns_none_for_garbage(self):
        assert parse_pattern_rule("not a pattern") is None

    def test_parse_all_entries_mixed(self):
        combined = VALID_MEMORY + "\n\n" + VALID_PATTERN
        memories, patterns = parse_all_entries(combined)
        assert len(memories) == 1
        assert len(patterns) == 1

    def test_parse_pattern_has_examples(self):
        pat = parse_pattern_rule(VALID_PATTERN)
        assert pat is not None
        assert "Examples" in pat
        assert "Bad:" in pat["Examples"]
        assert "Good:" in pat["Examples"]
