"""trace validate — check memory format and dependency integrity.

Validates every Trace Memory entry against:
- Required fields presence
- Field value constraints (Confidence, Status, Incident type, etc.)
- ISO date format
- Dependency integrity (forward and back references exist)
- Circular dependency detection
- No active memory depending on a superseded memory
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any

from trace_cli.sync import (
    MEMORY_FIELDS,
    PATTERN_FIELDS,
    load_entries_from_file,
    parse_all_entries,
)

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUS = {"Active", "Superseded", "Overridden"}
VALID_INCIDENT_TYPES = {
    "auth",
    "cache",
    "retry",
    "deployment",
    "config",
    "performance",
    "security",
    "database",
    "network",
    "none",
}
VALID_SOURCE_TYPES = {"discussion", "code", "both"}
VALID_SECURITY = {"yes", "no"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEP_REF_RE = re.compile(r"Memory\s*#(\d+)", re.IGNORECASE)


def _extract_refs(value: str) -> list[int]:
    """Return a list of memory IDs referenced in a dependency string."""
    if not value or value.strip().upper() in ("N/A", "NONE", "-", ""):
        return []
    return [int(m.group(1)) for m in _DEP_REF_RE.finditer(value)]


def _is_valid_date(date_str: str) -> bool:
    """Return True if *date_str* is a valid YYYY-MM-DD date."""
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def validate_memories(
    memories: list[dict[str, Any]],
    patterns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a list of parsed Trace memories.

    Returns a report dict::

        {
            "total": int,
            "valid": int,
            "errors": [{"memory": id, "field": str, "message": str}, ...],
            "warnings": [{"memory": id, "field": str, "message": str}, ...],
        }
    """
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    id_set = {m["id"] for m in memories}
    status_map: dict[int, str] = {}

    # ── per-memory checks ───────────────────────────────────────────────
    for mem in memories:
        mid = mem["id"]
        status_map[mid] = mem.get("Status", "")

        # Required fields
        for field in MEMORY_FIELDS:
            if field == "id":
                continue
            if field not in mem or not mem[field]:
                errors.append({"memory": mid, "field": field, "message": f"Missing required field: {field}"})

        # Confidence
        conf = mem.get("Confidence", "")
        if conf and conf not in VALID_CONFIDENCE:
            errors.append({
                "memory": mid,
                "field": "Confidence",
                "message": f"Invalid Confidence '{conf}'. Must be one of {sorted(VALID_CONFIDENCE)}",
            })

        # Status
        status = mem.get("Status", "")
        if status and status not in VALID_STATUS:
            errors.append({
                "memory": mid,
                "field": "Status",
                "message": f"Invalid Status '{status}'. Must be one of {sorted(VALID_STATUS)}",
            })

        # Incident type
        itype = mem.get("Incident type", "")
        if itype and itype.lower() not in VALID_INCIDENT_TYPES:
            errors.append({
                "memory": mid,
                "field": "Incident type",
                "message": f"Invalid Incident type '{itype}'. Must be one of {sorted(VALID_INCIDENT_TYPES)}",
            })

        # Source type
        stype = mem.get("Source type", "")
        if stype and stype.lower() not in VALID_SOURCE_TYPES:
            errors.append({
                "memory": mid,
                "field": "Source type",
                "message": f"Invalid Source type '{stype}'. Must be one of {sorted(VALID_SOURCE_TYPES)}",
            })

        # Security relevant
        sec = mem.get("Security relevant", "")
        if sec and sec.lower() not in VALID_SECURITY:
            errors.append({
                "memory": mid,
                "field": "Security relevant",
                "message": f"Invalid Security relevant '{sec}'. Must be 'yes' or 'no'",
            })

        # Date
        date_val = mem.get("Date", "")
        if date_val and not _is_valid_date(date_val):
            errors.append({
                "memory": mid,
                "field": "Date",
                "message": f"Invalid date '{date_val}'. Expected ISO format YYYY-MM-DD",
            })

        # Dependency references exist
        for dep_field in ("Depends on", "Blocks"):
            refs = _extract_refs(mem.get(dep_field, ""))
            for ref_id in refs:
                if ref_id not in id_set:
                    errors.append({
                        "memory": mid,
                        "field": dep_field,
                        "message": f"References Memory #{ref_id} which does not exist",
                    })

    # ── cross-memory checks ─────────────────────────────────────────────

    # "Blocks" back-reference: if A blocks B, B should depend on A.
    depends_map: dict[int, set[int]] = {}
    blocks_map: dict[int, set[int]] = {}
    for mem in memories:
        mid = mem["id"]
        depends_map[mid] = set(_extract_refs(mem.get("Depends on", "")))
        blocks_map[mid] = set(_extract_refs(mem.get("Blocks", "")))

    for mid, blocked_ids in blocks_map.items():
        for bid in blocked_ids:
            if bid in id_set and mid not in depends_map.get(bid, set()):
                warnings.append({
                    "memory": mid,
                    "field": "Blocks",
                    "message": f"Memory #{mid:03d} blocks #{bid:03d}, but #{bid:03d} does not list #{mid:03d} in 'Depends on'",
                })

    # Circular dependency detection (DFS).
    cycles = _detect_cycles(depends_map, id_set)
    for cycle in cycles:
        cycle_str = " -> ".join(f"#{c:03d}" for c in cycle)
        errors.append({
            "memory": cycle[0],
            "field": "Depends on",
            "message": f"Circular dependency detected: {cycle_str}",
        })

    # Active memory depending on a superseded memory.
    for mem in memories:
        mid = mem["id"]
        if status_map.get(mid) == "Active":
            for dep_id in depends_map.get(mid, set()):
                if status_map.get(dep_id) == "Superseded":
                    warnings.append({
                        "memory": mid,
                        "field": "Depends on",
                        "message": f"Active memory #{mid:03d} depends on superseded memory #{dep_id:03d}",
                    })

    # ── pattern rules ───────────────────────────────────────────────────
    if patterns:
        for pat in patterns:
            pid = pat["id"]
            for field in PATTERN_FIELDS:
                if field == "id":
                    continue
                if field not in pat or not pat[field]:
                    errors.append({"memory": f"Pattern#{pid}", "field": field, "message": f"Missing required field: {field}"})

    # ── assemble report ─────────────────────────────────────────────────
    total = len(memories) + (len(patterns) if patterns else 0)
    errored_ids = {e["memory"] for e in errors}
    valid = total - len(errored_ids)

    return {
        "total": total,
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
    }


def _detect_cycles(depends_map: dict[int, set[int]], id_set: set[int]) -> list[list[int]]:
    """Return a list of cycles found via DFS on the dependency graph."""
    visited: set[int] = set()
    rec_stack: set[int] = set()
    cycles: list[list[int]] = []
    path: list[int] = []

    def dfs(node: int) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in depends_map.get(node, set()):
            if neighbor not in id_set:
                continue
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                # Extract the cycle from path.
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])

        path.pop()
        rec_stack.discard(node)

    for node in sorted(id_set):
        if node not in visited:
            dfs(node)

    return cycles


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_validate(args: argparse.Namespace) -> int:
    """Execute the ``trace validate`` command."""
    from_file = getattr(args, "from_file", None)

    if from_file:
        memories, patterns = load_entries_from_file(from_file)
    else:
        # Load from GitLab
        from trace_cli.sync import _collect_comments, _find_memory_bank_issue, _get_gitlab

        _gl, project = _get_gitlab(args)
        issue = _find_memory_bank_issue(project)
        if issue is None:
            print("ERROR: Could not find the Trace Memory Bank issue.", file=sys.stderr)
            return 1
        raw_text = _collect_comments(issue)
        memories, patterns = parse_all_entries(raw_text)

    report = validate_memories(memories, patterns)

    print(json.dumps(report, indent=2))

    return 0 if not report["errors"] else 1
