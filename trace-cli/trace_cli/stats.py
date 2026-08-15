"""trace stats — output JSON statistics about the Trace memory bank.

Aggregates counts by status, confidence, source type, incident type, and
computes carbon-impact estimates and dependency chain metrics.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from typing import Any

from trace_cli.sync import load_entries_from_file, parse_all_entries

# ---------------------------------------------------------------------------
# Carbon constants
# ---------------------------------------------------------------------------

# Average CO2 emission factor: 0.4 kg CO2 per kWh (global grid average).
_CO2_KG_PER_KWH = 0.4

# A mature tree absorbs roughly 22 kg CO2 per year.
_KG_CO2_PER_TREE_YEAR = 22.0

# Regex to pull a numeric kWh value from a "Carbon impact" field.
_KWH_RE = re.compile(r"~?\s*([\d,.]+)\s*kWh", re.IGNORECASE)
_SAVED_RE = re.compile(r"saved|reduction|avoided|less", re.IGNORECASE)
_COST_RE = re.compile(r"cost|increase|added|more", re.IGNORECASE)


def _parse_carbon(raw: str) -> tuple[float, float]:
    """Return ``(savings_kwh, cost_kwh)`` parsed from a Carbon impact string.

    Positive values are savings; negative values are additional cost.  If the
    field does not contain a parseable number, both values are ``0.0``.
    """
    match = _KWH_RE.search(raw)
    if not match:
        return 0.0, 0.0

    value = float(match.group(1).replace(",", ""))

    if _COST_RE.search(raw):
        return 0.0, value
    # Default assumption: savings.
    return value, 0.0


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------


def compute_stats(
    memories: list[dict[str, Any]],
    patterns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute aggregate statistics from a list of parsed memories."""
    status_counter: Counter[str] = Counter()
    confidence_counter: Counter[str] = Counter()
    source_type_counter: Counter[str] = Counter()
    incident_type_counter: Counter[str] = Counter()
    security_count = 0
    file_counter: Counter[str] = Counter()
    total_savings = 0.0
    total_cost = 0.0
    dependency_roots: set[int] = set()

    id_set = {m["id"] for m in memories}
    depends_map: dict[int, set[int]] = {}

    for mem in memories:
        mid = mem["id"]

        # Status
        status = mem.get("Status", "Unknown")
        status_counter[status] += 1

        # Confidence
        confidence_counter[mem.get("Confidence", "Unknown")] += 1

        # Source type
        source_type_counter[mem.get("Source type", "unknown")] += 1

        # Incident type
        incident_type_counter[mem.get("Incident type", "none")] += 1

        # Security
        if mem.get("Security relevant", "no").lower() == "yes":
            security_count += 1

        # Governed files
        paths_raw = mem.get("Governs files", "")
        for path in re.split(r"[,;\s]+", paths_raw):
            path = path.strip()
            if path:
                file_counter[path] += 1

        # Carbon
        carbon_raw = mem.get("Carbon impact", "")
        savings, cost = _parse_carbon(carbon_raw)
        total_savings += savings
        total_cost += cost

        # Dependencies
        deps_raw = mem.get("Depends on", "")
        dep_ids: set[int] = set()
        for m in re.finditer(r"Memory\s*#(\d+)", deps_raw, re.IGNORECASE):
            dep_ids.add(int(m.group(1)))
        depends_map[mid] = dep_ids

    # ── dependency chains ───────────────────────────────────────────────
    # A "chain" starts at a memory that nothing else depends on (a root) and
    # has at least one dependency.
    all_depended_on: set[int] = set()
    for deps in depends_map.values():
        all_depended_on.update(deps)

    chain_count = 0
    for mid in id_set:
        if mid not in all_depended_on and depends_map.get(mid):
            chain_count += 1
    # Also count isolated memories that are depended upon but depend on
    # nothing as chain roots (length-1 chains are not interesting).
    # We already count only mids with outgoing deps, so this is fine.

    # ── most governed file ──────────────────────────────────────────────
    most_governed: dict[str, Any] = {"path": "", "memory_count": 0}
    if file_counter:
        top_path, top_count = file_counter.most_common(1)[0]
        most_governed = {"path": top_path, "memory_count": top_count}

    # ── coverage gaps (governed files that appear only once) ────────────
    coverage_gaps = sorted(p for p, c in file_counter.items() if c < 2) if file_counter else []

    # ── carbon impact ───────────────────────────────────────────────────
    net_kwh = total_savings - total_cost
    # Monthly figures.
    co2_kg_month = round(net_kwh * _CO2_KG_PER_KWH, 1)
    trees_year = round((co2_kg_month * 12) / _KG_CO2_PER_TREE_YEAR, 1) if _KG_CO2_PER_TREE_YEAR else 0

    return {
        "total_memories": len(memories),
        "active": status_counter.get("Active", 0),
        "superseded": status_counter.get("Superseded", 0),
        "by_status": dict(status_counter),
        "by_confidence": {
            "HIGH": confidence_counter.get("HIGH", 0),
            "MEDIUM": confidence_counter.get("MEDIUM", 0),
            "LOW": confidence_counter.get("LOW", 0),
        },
        "by_source_type": dict(source_type_counter),
        "by_incident_type": dict(incident_type_counter),
        "security_relevant": security_count,
        "files_governed": len(file_counter),
        "most_governed_file": most_governed,
        "carbon_impact": {
            "total_savings_kwh": total_savings,
            "total_cost_kwh": total_cost,
            "net_kwh": net_kwh,
            "co2_kg_month": co2_kg_month,
            "trees_year": trees_year,
        },
        "dependency_chains": chain_count,
        "pattern_rules": len(patterns) if patterns else 0,
        "coverage_gaps": coverage_gaps,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_stats(args: argparse.Namespace) -> int:
    """Execute the ``trace stats`` command."""
    from_file = getattr(args, "from_file", None)

    if from_file:
        memories, patterns = load_entries_from_file(from_file)
    else:
        from trace_cli.sync import _collect_comments, _find_memory_bank_issue, _get_gitlab

        _gl, project = _get_gitlab(args)
        issue = _find_memory_bank_issue(project)
        if issue is None:
            print("ERROR: Could not find the Trace Memory Bank issue.", file=sys.stderr)
            return 1
        raw_text = _collect_comments(issue)
        memories, patterns = parse_all_entries(raw_text)

    report = compute_stats(memories, patterns)
    print(json.dumps(report, indent=2))
    return 0
