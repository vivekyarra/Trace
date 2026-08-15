"""trace sync — read memories from GitLab issues and write wiki pages.

The sync command:
1. Connects to the GitLab API.
2. Finds the "Trace Memory Bank" issue (by title or the ``trace-memory-bank`` label).
3. Parses every comment for Trace Memory and Trace Pattern entries.
4. Creates / updates one wiki page per memory (``TRACE-MEMORY-{id}``).
5. Rebuilds the ``TRACE-INDEX`` wiki page (a markdown table mapping governed
   files to the memories that reference them).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Parsing helpers (used by validate / stats too — importable stand-alone)
# ---------------------------------------------------------------------------

# Required fields for a Trace Memory entry.
MEMORY_FIELDS: list[str] = [
    "id",
    "Source MR",
    "Date",
    "Governs files",
    "Decision",
    "Rejected",
    "Reason",
    "Future implication",
    "Decided by",
    "Confidence",
    "Status",
    "Carbon impact",
    "Incident type",
    "Depends on",
    "Blocks",
    "Source type",
    "Security relevant",
]

# Fields for a Trace Pattern Rule.
PATTERN_FIELDS: list[str] = [
    "id",
    "Source MR",
    "Date",
    "Rule",
    "Anti-pattern",
    "Language",
    "Reason",
    "Established by",
    "Status",
    "Examples",
]

_MEMORY_HEADER_RE = re.compile(r"^Trace\s+Memory\s+#(\d+)", re.MULTILINE)
_PATTERN_HEADER_RE = re.compile(r"^Trace\s+Pattern\s+#(\d+)", re.MULTILINE)


def parse_memory(text: str) -> dict[str, Any] | None:
    """Extract a single Trace Memory from *text*.

    Returns a dict keyed by field name (including ``"id"`` as an ``int``), or
    ``None`` if the text does not contain a valid memory header.
    """
    header = _MEMORY_HEADER_RE.search(text)
    if header is None:
        return None

    result: dict[str, Any] = {"id": int(header.group(1))}

    # Build a mapping of field-name -> value by walking the lines that follow
    # the header.  Each line is expected to look like ``Field: value``.
    lines = text[header.end() :].splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Match "Key: value" — the key may contain spaces.
        match = re.match(r"^([A-Za-z][A-Za-z /\-]+?):\s*(.+)$", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            result[key] = value

    return result


def parse_pattern_rule(text: str) -> dict[str, Any] | None:
    """Extract a single Trace Pattern Rule from *text*.

    Returns a dict keyed by field name (including ``"id"`` as an ``int``), or
    ``None`` if the text does not contain a valid pattern header.
    """
    header = _PATTERN_HEADER_RE.search(text)
    if header is None:
        return None

    result: dict[str, Any] = {"id": int(header.group(1))}

    lines = text[header.end() :].splitlines()
    examples_lines: list[str] = []
    in_examples = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("Examples:"):
            in_examples = True
            continue

        if in_examples:
            examples_lines.append(stripped)
            continue

        match = re.match(r"^([A-Za-z][A-Za-z /\-]+?):\s*(.+)$", stripped)
        if match:
            result[match.group(1).strip()] = match.group(2).strip()

    if examples_lines:
        result["Examples"] = "\n".join(examples_lines)

    return result


def parse_all_entries(text: str) -> tuple[list[dict], list[dict]]:
    """Split *text* into individual memory and pattern blocks and parse each.

    Returns ``(memories, patterns)`` where each is a list of parsed dicts.
    """
    memories: list[dict] = []
    patterns: list[dict] = []

    # Split on the header lines so each block contains exactly one entry.
    # We use a lookahead so the header itself is included in each chunk.
    chunks = re.split(r"(?=^Trace\s+(?:Memory|Pattern)\s+#\d+)", text, flags=re.MULTILINE)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        mem = parse_memory(chunk)
        if mem is not None:
            memories.append(mem)
            continue

        pat = parse_pattern_rule(chunk)
        if pat is not None:
            patterns.append(pat)

    return memories, patterns


def load_entries_from_file(path: str) -> tuple[list[dict], list[dict]]:
    """Read a local file and return parsed ``(memories, patterns)``."""
    with open(path, encoding="utf-8") as fh:
        return parse_all_entries(fh.read())


# ---------------------------------------------------------------------------
# GitLab interaction
# ---------------------------------------------------------------------------


def _get_gitlab(args: argparse.Namespace):  # type: ignore[return]
    """Return an authenticated ``gitlab.Gitlab`` instance and project."""
    try:
        import gitlab  # type: ignore[import-untyped]
    except ImportError:
        print("ERROR: python-gitlab is required.  Install with:  pip install python-gitlab>=4.0.0", file=sys.stderr)
        sys.exit(1)

    if args.project_id is None:
        print("ERROR: --project-id (or TRACE_PROJECT_ID) is required for sync.", file=sys.stderr)
        sys.exit(1)
    if args.token is None:
        print("ERROR: --token (or GITLAB_TOKEN) is required for sync.", file=sys.stderr)
        sys.exit(1)

    gl = gitlab.Gitlab(args.gitlab_url, private_token=args.token)
    project = gl.projects.get(args.project_id)
    return gl, project


def _find_memory_bank_issue(project):  # type: ignore[return]
    """Locate the Trace Memory Bank issue by title or label."""
    # Try label first (fast).
    issues = project.issues.list(labels=["trace-memory-bank"], state="opened", per_page=1)
    if issues:
        return issues[0]

    # Fall back to title search.
    issues = project.issues.list(search="Trace Memory Bank", state="opened", per_page=5)
    for issue in issues:
        if "Trace Memory Bank" in issue.title:
            return issue

    return None


def _collect_comments(issue) -> str:
    """Concatenate all note bodies from *issue* into a single string."""
    notes = issue.notes.list(all=True)
    return "\n\n".join(note.body for note in notes)


def _sync_wiki(project, memories: list[dict], patterns: list[dict]) -> tuple[int, int]:
    """Create / update wiki pages.  Returns ``(synced_count, index_entries)``."""
    synced = 0

    # ── individual memory pages ─────────────────────────────────────────
    for mem in memories:
        slug = f"TRACE-MEMORY-{mem['id']:03d}"
        content = _render_memory_page(mem)
        _upsert_wiki_page(project, slug, f"Trace Memory #{mem['id']:03d}", content)
        synced += 1

    for pat in patterns:
        slug = f"Trace-PATTERN-{pat['id']:03d}"
        content = _render_pattern_page(pat)
        _upsert_wiki_page(project, slug, f"Trace Pattern #{pat['id']:03d}", content)
        synced += 1

    # ── TRACE-INDEX ──────────────────────────────────────────────────────
    index_entries = _rebuild_index(project, memories)

    return synced, index_entries


def _render_memory_page(mem: dict) -> str:
    """Render a Trace Memory dict as a Markdown wiki page."""
    lines = [f"# Trace Memory #{mem['id']:03d}", ""]
    for field in MEMORY_FIELDS:
        if field == "id":
            continue
        lines.append(f"**{field}:** {mem.get(field, 'N/A')}")
    return "\n".join(lines) + "\n"


def _render_pattern_page(pat: dict) -> str:
    """Render a Trace Pattern dict as a Markdown wiki page."""
    lines = [f"# Trace Pattern #{pat['id']:03d}", ""]
    for field in PATTERN_FIELDS:
        if field == "id":
            continue
        value = pat.get(field, "N/A")
        if field == "Examples" and value != "N/A":
            lines.append(f"**{field}:**")
            lines.append(f"```")
            lines.append(value)
            lines.append(f"```")
        else:
            lines.append(f"**{field}:** {value}")
    return "\n".join(lines) + "\n"


def _upsert_wiki_page(project, slug: str, title: str, content: str) -> None:
    """Create a wiki page or update it if it already exists."""
    try:
        page = project.wikis.get(slug)
        page.content = content
        page.title = title
        page.save()
    except Exception:
        project.wikis.create({"title": title, "slug": slug, "content": content})


def _rebuild_index(project, memories: list[dict]) -> int:
    """Rebuild the TRACE-INDEX wiki page.  Returns number of index entries."""
    file_map: dict[str, list[int]] = defaultdict(list)
    for mem in memories:
        paths_raw = mem.get("Governs files", "")
        for path in re.split(r"[,;\s]+", paths_raw):
            path = path.strip()
            if path:
                file_map[path].append(mem["id"])

    lines = [
        "# Trace Index",
        "",
        "| File Path | Memory IDs |",
        "|-----------|------------|",
    ]
    for path in sorted(file_map):
        ids = ", ".join(f"#{mid:03d}" for mid in sorted(file_map[path]))
        lines.append(f"| `{path}` | {ids} |")

    _upsert_wiki_page(project, "TRACE-INDEX", "Trace Index", "\n".join(lines) + "\n")
    return len(file_map)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_sync(args: argparse.Namespace) -> int:
    """Execute the ``trace sync`` command."""
    _gl, project = _get_gitlab(args)

    issue = _find_memory_bank_issue(project)
    if issue is None:
        print("ERROR: Could not find the Trace Memory Bank issue.", file=sys.stderr)
        print("  Create an issue titled 'Trace Memory Bank' or add the label 'trace-memory-bank'.", file=sys.stderr)
        return 1

    raw_text = _collect_comments(issue)
    memories, patterns = parse_all_entries(raw_text)

    if not memories and not patterns:
        print("No Trace memories or patterns found in issue comments.")
        return 0

    synced, index_entries = _sync_wiki(project, memories, patterns)
    print(f"{synced} memories synced to wiki, {index_entries} index entries updated")
    return 0
