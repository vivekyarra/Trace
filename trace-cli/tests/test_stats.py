"""Tests for trace_cli.stats — statistics computation."""

from __future__ import annotations

import textwrap

from trace_cli.stats import compute_stats
from trace_cli.sync import parse_all_entries, parse_memory

# ---------------------------------------------------------------------------
# Sample memories
# ---------------------------------------------------------------------------

SAMPLE_MEMORIES_TEXT = textwrap.dedent("""\
    Trace Memory #001
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
    Blocks: Memory #003
    Source type: discussion
    Security relevant: no

    Trace Memory #002
    Source MR: !55 — Cache invalidation
    Date: 2026-02-10
    Governs files: src/api/auth.py, src/cache/redis.py
    Decision: TTL-based cache invalidation
    Rejected: Event-driven invalidation
    Reason: Simplicity over complexity for current scale
    Future implication: Must revisit if event bus is adopted
    Decided by: @carol
    Confidence: MEDIUM
    Status: Active
    Carbon impact: ~200 kWh/month saved
    Incident type: cache
    Depends on: N/A
    Blocks: N/A
    Source type: code
    Security relevant: yes

    Trace Memory #003
    Source MR: !60 — Auth token rotation
    Date: 2026-03-01
    Governs files: src/api/auth.py, src/auth/tokens.py
    Decision: Rotate tokens every 24h
    Rejected: 1h rotation
    Reason: Balance between security and UX
    Future implication: Token store must handle overlap window
    Decided by: @alice
    Confidence: HIGH
    Status: Superseded
    Carbon impact: ~150 kWh/month saved
    Incident type: auth
    Depends on: Memory #001
    Blocks: N/A
    Source type: both
    Security relevant: yes

    Trace Pattern #001
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


def _parse_samples():
    return parse_all_entries(SAMPLE_MEMORIES_TEXT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatsFromSamples:
    def test_total_memories(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["total_memories"] == 3

    def test_active_superseded_counts(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["active"] == 2
        assert stats["superseded"] == 1

    def test_by_status(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["by_status"]["Active"] == 2
        assert stats["by_status"]["Superseded"] == 1

    def test_by_confidence(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["by_confidence"]["HIGH"] == 2
        assert stats["by_confidence"]["MEDIUM"] == 1
        assert stats["by_confidence"]["LOW"] == 0

    def test_by_source_type(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["by_source_type"]["discussion"] == 1
        assert stats["by_source_type"]["code"] == 1
        assert stats["by_source_type"]["both"] == 1

    def test_by_incident_type(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["by_incident_type"]["retry"] == 1
        assert stats["by_incident_type"]["cache"] == 1
        assert stats["by_incident_type"]["auth"] == 1

    def test_security_relevant(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["security_relevant"] == 2

    def test_files_governed(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        # src/api/auth.py, src/cache/redis.py, src/auth/tokens.py
        assert stats["files_governed"] == 3

    def test_most_governed_file(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["most_governed_file"]["path"] == "src/api/auth.py"
        assert stats["most_governed_file"]["memory_count"] == 3

    def test_pattern_rules_count(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["pattern_rules"] == 1

    def test_dependency_chains(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        # Memory #003 depends on #001, forming one chain.
        assert stats["dependency_chains"] >= 1


class TestCarbonAggregation:
    def test_total_savings(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        carbon = stats["carbon_impact"]
        # 300 + 200 + 150 = 650
        assert carbon["total_savings_kwh"] == 650.0

    def test_net_kwh(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        carbon = stats["carbon_impact"]
        assert carbon["net_kwh"] == 650.0

    def test_co2_calculation(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        carbon = stats["carbon_impact"]
        # 650 * 0.4 = 260.0
        assert carbon["co2_kg_month"] == 260.0

    def test_trees_calculation(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        carbon = stats["carbon_impact"]
        # (260 * 12) / 22 = 141.8...
        assert carbon["trees_year"] > 0

    def test_cost_kwh_is_zero_for_savings(self):
        memories, patterns = _parse_samples()
        stats = compute_stats(memories, patterns)
        assert stats["carbon_impact"]["total_cost_kwh"] == 0.0


class TestEmptyInput:
    def test_empty_memories(self):
        stats = compute_stats([], [])
        assert stats["total_memories"] == 0
        assert stats["active"] == 0
        assert stats["superseded"] == 0
        assert stats["files_governed"] == 0
        assert stats["security_relevant"] == 0
        assert stats["pattern_rules"] == 0
        assert stats["carbon_impact"]["net_kwh"] == 0.0
        assert stats["coverage_gaps"] == []

    def test_most_governed_file_empty(self):
        stats = compute_stats([], [])
        assert stats["most_governed_file"]["path"] == ""
        assert stats["most_governed_file"]["memory_count"] == 0
