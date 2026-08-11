"""Tests for lore_cli.dashboard — HTML dashboard generation."""

from __future__ import annotations

import os
import tempfile
import textwrap

from lore_cli.dashboard import generate_dashboard
from lore_cli.sync import parse_all_entries


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_TEXT = textwrap.dedent("""\
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
    Blocks: Memory #003
    Source type: discussion
    Security relevant: no

    LORE Memory #002
    Source MR: !55 — Cache invalidation
    Date: 2026-02-10
    Governs files: src/cache/redis.py
    Decision: TTL-based cache invalidation
    Rejected: Event-driven invalidation
    Reason: Simplicity over complexity
    Future implication: Must revisit if event bus is adopted
    Decided by: @carol
    Confidence: MEDIUM
    Status: Superseded
    Carbon impact: ~200 kWh/month saved
    Incident type: cache
    Depends on: N/A
    Blocks: N/A
    Source type: code
    Security relevant: yes

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


def _parse_samples():
    return parse_all_entries(SAMPLE_TEXT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardGeneratesHTML:
    def test_generates_valid_html(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "public", "index.html")
            result = generate_dashboard(memories, patterns, output_path=out)
            assert os.path.isfile(result)
            content = open(result, encoding="utf-8").read()
            assert content.startswith("<!DOCTYPE html>")
            assert "</html>" in content

    def test_contains_mermaid_div(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            result = generate_dashboard(memories, patterns, output_path=out)
            content = open(result, encoding="utf-8").read()
            assert 'class="mermaid"' in content
            assert "mermaid.min.js" in content

    def test_correct_memory_count(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            result = generate_dashboard(memories, patterns, output_path=out)
            content = open(result, encoding="utf-8").read()
            # The summary card should show "2" as total memories
            assert '>2<' in content

    def test_empty_memories_generates_valid_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            result = generate_dashboard([], [], output_path=out)
            assert os.path.isfile(result)
            content = open(result, encoding="utf-8").read()
            assert "<!DOCTYPE html>" in content
            assert "LORE" in content
            assert "</html>" in content

    def test_contains_security_section(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            generate_dashboard(memories, patterns, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Security Inventory" in content

    def test_contains_carbon_section(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            generate_dashboard(memories, patterns, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Carbon Impact" in content

    def test_contains_pattern_rules_section(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            generate_dashboard(memories, patterns, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Code Pattern Rules" in content
            assert "typing.Optional[X]" in content

    def test_memory_details_present(self):
        memories, patterns = _parse_samples()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "index.html")
            generate_dashboard(memories, patterns, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Memory Details" in content
            assert "#001" in content
            assert "#002" in content
