"""trace dashboard -- generate a self-contained GitLab Pages HTML dashboard.

Reads parsed Trace memories and pattern rules, then produces a single
``public/index.html`` file with summary cards, a Mermaid dependency graph,
carbon-impact tables, file coverage, security inventory, pattern rules,
and expandable memory detail cards.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime, date
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(value: Any) -> str:
    """HTML-escape a value, converting non-strings first."""
    return html.escape(str(value))


def _parse_carbon(raw: str) -> tuple[float, float]:
    """Return ``(savings_kwh, cost_kwh)`` from a carbon-impact string.

    Recognised formats:
      ``~300 kWh/month saved``  -> (300, 0)
      ``+50 kWh/month cost``    -> (0, 50)
      ``N/A``                   -> (0, 0)
    """
    if not raw or raw.strip().upper() == "N/A":
        return 0.0, 0.0
    m = re.search(r"[~+]?\s*(\d+(?:\.\d+)?)", raw)
    if m is None:
        return 0.0, 0.0
    value = float(m.group(1))
    if "cost" in raw.lower():
        return 0.0, value
    return value, 0.0


def _extract_ids(raw: str) -> list[int]:
    """Pull ``#NNN`` or ``Memory #NNN`` references out of a string."""
    return [int(x) for x in re.findall(r"#(\d+)", raw)]


def _age_days(date_str: str) -> int:
    """Days between *date_str* (YYYY-MM-DD) and today.  Returns -1 on error."""
    try:
        d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, AttributeError):
        return -1


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_CO2_FACTOR = 0.4   # kg CO2 per kWh (global-average grid)
_KG_PER_TREE_YEAR = 22.0


def generate_dashboard(
    memories: list[dict],
    patterns: list[dict],
    output_path: str = "public/index.html",
) -> str:
    """Build an HTML dashboard and write it to *output_path*.

    Returns the absolute path of the generated file.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── compute stats ────────────────────────────────────────────────────
    total = len(memories)
    active = sum(1 for m in memories if m.get("Status", "").lower() == "active")
    superseded = sum(1 for m in memories if m.get("Status", "").lower() == "superseded")
    overridden = sum(1 for m in memories if m.get("Status", "").lower() == "overridden")
    security_count = sum(
        1 for m in memories if m.get("Security relevant", "").lower() in ("yes", "true")
    )

    # files governed
    file_map: dict[str, list[int]] = {}
    for m in memories:
        for fp in re.split(r"[,;\s]+", m.get("Governs files", "")):
            fp = fp.strip()
            if fp:
                file_map.setdefault(fp, []).append(m["id"])
    files_governed = len(file_map)

    # carbon
    total_savings = 0.0
    total_cost = 0.0
    for m in memories:
        s, c = _parse_carbon(m.get("Carbon impact", ""))
        total_savings += s
        total_cost += c
    net_kwh = total_savings - total_cost
    co2_kg = net_kwh * _CO2_FACTOR
    trees_year = (co2_kg * 12) / _KG_PER_TREE_YEAR if _KG_PER_TREE_YEAR else 0

    pattern_count = len(patterns)

    # ── build sections ───────────────────────────────────────────────────
    sections: list[str] = []

    # Section 1: Summary cards
    sections.append(_section_summary_cards(
        total, active, superseded, overridden, security_count,
        files_governed, net_kwh, pattern_count,
    ))

    # Section 2: Decision graph (Mermaid)
    sections.append(_section_mermaid_graph(memories))

    # Section 3: Carbon impact table
    sections.append(_section_carbon_table(memories, total_savings, total_cost, net_kwh, co2_kg, trees_year))

    # Section 4: File coverage map
    sections.append(_section_file_coverage(file_map, memories))

    # Section 5: Security inventory
    sections.append(_section_security_inventory(memories))

    # Section 6: Code pattern rules
    sections.append(_section_pattern_rules(patterns))

    # Section 7: Memory detail cards
    sections.append(_section_memory_details(memories))

    body = "\n".join(sections)

    page = _wrap_page(body, now)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_summary_cards(
    total: int, active: int, superseded: int, overridden: int,
    security: int, files: int, net_kwh: float, patterns: int,
) -> str:
    def _card(label: str, value: str | int, color: str = "#0f3460") -> str:
        return (
            f'<div class="card" style="border-top:4px solid {color}">'
            f'<div class="card-value">{value}</div>'
            f'<div class="card-label">{label}</div>'
            f'</div>'
        )
    cards = [
        _card("Total Memories", total),
        _card("Active", active, "#00b894"),
        _card("Superseded", superseded, "#fdcb6e"),
        _card("Overridden", overridden, "#e17055"),
        _card("Security Decisions", security, "#e94560"),
        _card("Files Governed", files, "#6c5ce7"),
        _card("Net Carbon Impact", f"{net_kwh:+.0f} kWh/mo", "#00cec9"),
        _card("Pattern Rules", patterns, "#a29bfe"),
    ]
    return (
        '<section><h2>Summary</h2>'
        '<div class="card-row">' + "".join(cards) + '</div>'
        '</section>'
    )


def _section_mermaid_graph(memories: list[dict]) -> str:
    if not memories:
        return '<section><h2>Decision Graph</h2><p class="muted">No memories to graph.</p></section>'

    lines = ["graph LR"]
    for m in memories:
        mid = m["id"]
        label = _esc(m.get("Decision", "?")[:50])
        node_id = f"M{mid}"
        is_superseded = m.get("Status", "").lower() == "superseded"
        is_security = m.get("Security relevant", "").lower() in ("yes", "true")

        # node
        lines.append(f'  {node_id}["#{mid:03d}: {label}"]')

        # styling
        if is_security and is_superseded:
            lines.append(f"  style {node_id} stroke:#e94560,stroke-width:3px,stroke-dasharray:5 5")
        elif is_security:
            lines.append(f"  style {node_id} stroke:#e94560,stroke-width:3px")
        elif is_superseded:
            lines.append(f"  style {node_id} stroke-dasharray:5 5")

    # edges
    for m in memories:
        mid = m["id"]
        for dep_id in _extract_ids(m.get("Depends on", "")):
            lines.append(f"  M{dep_id} --> M{mid}")
        for blk_id in _extract_ids(m.get("Blocks", "")):
            lines.append(f"  M{mid} -.->|blocks| M{blk_id}")

    mermaid_code = "\n".join(lines)
    return (
        '<section><h2>Decision Graph</h2>'
        f'<div class="mermaid">\n{mermaid_code}\n</div>'
        '</section>'
    )


def _section_carbon_table(
    memories: list[dict],
    total_savings: float, total_cost: float,
    net_kwh: float, co2_kg: float, trees_year: float,
) -> str:
    rows: list[str] = []
    for m in memories:
        s, c = _parse_carbon(m.get("Carbon impact", ""))
        if s == 0 and c == 0:
            continue
        color = "#00b894" if s > 0 else "#e94560"
        rows.append(
            f'<tr>'
            f'<td>#{m["id"]:03d}</td>'
            f'<td>{_esc(m.get("Decision", "N/A"))}</td>'
            f'<td style="color:{color}">{_esc(m.get("Carbon impact", "N/A"))}</td>'
            f'</tr>'
        )
    if not rows:
        return '<section><h2>Carbon Impact</h2><p class="muted">No carbon data.</p></section>'

    summary_row = (
        f'<tr class="summary-row">'
        f'<td colspan="2"><strong>Totals</strong></td>'
        f'<td>'
        f'<span style="color:#00b894">Savings: {total_savings:.0f} kWh</span> &nbsp;|&nbsp; '
        f'<span style="color:#e94560">Costs: {total_cost:.0f} kWh</span> &nbsp;|&nbsp; '
        f'Net: {net_kwh:+.0f} kWh &nbsp;|&nbsp; '
        f'CO2: {co2_kg:.1f} kg/mo &nbsp;|&nbsp; '
        f'Trees: {trees_year:.1f}/yr'
        f'</td></tr>'
    )

    return (
        '<section><h2>Carbon Impact</h2>'
        '<table><thead><tr><th>ID</th><th>Decision</th><th>Impact</th></tr></thead>'
        '<tbody>' + "".join(rows) + summary_row + '</tbody></table>'
        '</section>'
    )


def _section_file_coverage(file_map: dict[str, list[int]], memories: list[dict]) -> str:
    if not file_map:
        return '<section><h2>File Coverage Map</h2><p class="muted">No governed files.</p></section>'

    mem_lookup = {m["id"]: m for m in memories}
    rows: list[str] = []
    for fp in sorted(file_map):
        ids = file_map[fp]
        ids_str = ", ".join(f"#{mid:03d}" for mid in sorted(ids))
        has_security = any(
            mem_lookup.get(mid, {}).get("Security relevant", "").lower() in ("yes", "true")
            for mid in ids
        )
        sec_badge = '<span class="badge badge-red">SEC</span>' if has_security else ""
        statuses = set(mem_lookup.get(mid, {}).get("Status", "?") for mid in ids)
        status_str = ", ".join(sorted(statuses))
        rows.append(
            f'<tr><td><code>{_esc(fp)}</code></td>'
            f'<td>{ids_str}</td><td>{sec_badge}</td><td>{status_str}</td></tr>'
        )

    return (
        '<section><h2>File Coverage Map</h2>'
        '<table><thead><tr><th>File Path</th><th>Governing Memories</th>'
        '<th>Security</th><th>Status</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table>'
        '</section>'
    )


def _section_security_inventory(memories: list[dict]) -> str:
    sec_mems = [
        m for m in memories
        if m.get("Security relevant", "").lower() in ("yes", "true")
    ]
    if not sec_mems:
        return '<section><h2>Security Inventory</h2><p class="muted">No security-relevant memories.</p></section>'

    rows: list[str] = []
    for m in sec_mems:
        age = _age_days(m.get("Date", ""))
        stale = age > 180
        age_str = f"{age}d" if age >= 0 else "?"
        stale_badge = ' <span class="badge badge-yellow">STALE</span>' if stale else ""
        rows.append(
            f'<tr>'
            f'<td>#{m["id"]:03d}</td>'
            f'<td>{_esc(m.get("Decision", "N/A"))}</td>'
            f'<td>{_esc(m.get("Decided by", "N/A"))}</td>'
            f'<td>{_esc(m.get("Date", "N/A"))}</td>'
            f'<td>{age_str}{stale_badge}</td>'
            f'<td>{_esc(m.get("Status", "N/A"))}</td>'
            f'</tr>'
        )
    return (
        '<section><h2>Security Inventory</h2>'
        '<table><thead><tr><th>ID</th><th>Decision</th><th>Decided By</th>'
        '<th>Date</th><th>Age</th><th>Status</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table>'
        '</section>'
    )


def _section_pattern_rules(patterns: list[dict]) -> str:
    if not patterns:
        return '<section><h2>Code Pattern Rules</h2><p class="muted">No pattern rules defined.</p></section>'

    rows: list[str] = []
    for p in patterns:
        examples = p.get("Examples", "")
        bad_good = ""
        if examples:
            bad_good = f'<pre class="examples">{_esc(examples)}</pre>'
        rows.append(
            f'<tr>'
            f'<td>P#{p["id"]:03d}</td>'
            f'<td>{_esc(p.get("Rule", "N/A"))}</td>'
            f'<td><code>{_esc(p.get("Anti-pattern", "N/A"))}</code></td>'
            f'<td>{_esc(p.get("Language", "N/A"))}</td>'
            f'<td>{_esc(p.get("Established by", "N/A"))}</td>'
            f'</tr>'
            f'<tr><td colspan="5">{bad_good}</td></tr>'
        )
    return (
        '<section><h2>Code Pattern Rules</h2>'
        '<table><thead><tr><th>ID</th><th>Rule</th><th>Anti-pattern</th>'
        '<th>Language</th><th>Established By</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table>'
        '</section>'
    )


def _section_memory_details(memories: list[dict]) -> str:
    if not memories:
        return '<section><h2>Memory Details</h2><p class="muted">No memories.</p></section>'

    # sort: Active first, then Superseded, then everything else
    order = {"active": 0, "superseded": 1}
    sorted_mems = sorted(memories, key=lambda m: order.get(m.get("Status", "").lower(), 2))

    cards: list[str] = []
    for m in sorted_mems:
        mid = m["id"]
        status = m.get("Status", "Unknown")
        status_class = status.lower().replace(" ", "-")
        decision = _esc(m.get("Decision", "N/A"))

        fields_html = ""
        for key, val in m.items():
            if key == "id":
                continue
            fields_html += f'<div class="detail-field"><span class="field-key">{_esc(key)}:</span> {_esc(val)}</div>'

        cards.append(
            f'<details class="memory-card {status_class}">'
            f'<summary>#{mid:03d} &mdash; {decision} '
            f'<span class="badge badge-status-{status_class}">{_esc(status)}</span></summary>'
            f'<div class="memory-body">{fields_html}</div>'
            f'</details>'
        )

    return '<section><h2>Memory Details</h2>' + "".join(cards) + '</section>'


# ---------------------------------------------------------------------------
# Page wrapper
# ---------------------------------------------------------------------------

def _wrap_page(body: str, timestamp: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trace — Institutional Memory Dashboard</title>
<style>
:root {{
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --accent: #0f3460;
  --highlight: #e94560;
  --text: #e0e0e0;
  --text-muted: #8a8a9a;
  --green: #00b894;
  --yellow: #fdcb6e;
  --red: #e94560;
  --purple: #6c5ce7;
  --cyan: #00cec9;
}}
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }}
header {{
  text-align: center;
  padding: 3rem 1rem 2rem;
  background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 60%, #e94560 100%);
  border-bottom: 3px solid var(--highlight);
  margin-bottom: 2rem;
}}
header h1 {{
  margin: 0;
  font-size: 2.5rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  background: linear-gradient(90deg, #e94560, #00cec9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
header .subtitle {{ color: var(--text-muted); font-size: 1.1rem; margin-top: 0.25rem; }}
header .timestamp {{ color: var(--text-muted); font-size: 0.85rem; margin-top: 0.5rem; }}
section {{
  background: var(--card-bg);
  border-radius: 12px;
  padding: 1.5rem 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
section h2 {{
  margin-top: 0;
  font-size: 1.4rem;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 0.5rem;
  color: #fff;
}}
.card-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}}
.card {{
  flex: 1 1 140px;
  background: var(--bg);
  border-radius: 10px;
  padding: 1.2rem 1rem;
  text-align: center;
  min-width: 130px;
  transition: transform 0.15s;
}}
.card:hover {{ transform: translateY(-3px); }}
.card-value {{ font-size: 2rem; font-weight: 700; color: #fff; }}
.card-label {{ font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem; }}
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  font-size: 0.92rem;
}}
th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); }}
th {{ background: var(--accent); color: #fff; font-weight: 600; position: sticky; top: 0; }}
tr:hover {{ background: rgba(255,255,255,0.03); }}
.summary-row {{ background: var(--accent); font-weight: 600; }}
code {{ background: rgba(255,255,255,0.08); padding: 0.15em 0.4em; border-radius: 4px; font-size: 0.9em; }}
pre.examples {{
  background: rgba(0,0,0,0.3);
  padding: 0.8rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  overflow-x: auto;
  border-left: 3px solid var(--purple);
}}
.badge {{
  display: inline-block;
  padding: 0.15em 0.55em;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.badge-red {{ background: var(--red); color: #fff; }}
.badge-yellow {{ background: var(--yellow); color: #222; }}
.badge-status-active {{ background: var(--green); color: #fff; }}
.badge-status-superseded {{ background: var(--yellow); color: #222; }}
.badge-status-overridden {{ background: #e17055; color: #fff; }}
.muted {{ color: var(--text-muted); font-style: italic; }}
/* Memory detail cards */
.memory-card {{
  background: var(--bg);
  border-radius: 8px;
  margin-bottom: 0.75rem;
  border-left: 4px solid var(--accent);
  overflow: hidden;
}}
.memory-card.active {{ border-left-color: var(--green); }}
.memory-card.superseded {{ border-left-color: var(--yellow); }}
.memory-card.overridden {{ border-left-color: #e17055; }}
.memory-card summary {{
  cursor: pointer;
  padding: 0.8rem 1.2rem;
  font-weight: 600;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}
.memory-card summary::-webkit-details-marker {{ display: none; }}
.memory-card summary::before {{
  content: "\\25B6";
  font-size: 0.7rem;
  transition: transform 0.2s;
  color: var(--text-muted);
}}
.memory-card[open] summary::before {{ transform: rotate(90deg); }}
.memory-body {{ padding: 0.5rem 1.2rem 1rem; }}
.detail-field {{ padding: 0.2rem 0; }}
.field-key {{ color: var(--cyan); font-weight: 600; }}
/* Mermaid */
.mermaid {{
  background: rgba(0,0,0,0.2);
  border-radius: 8px;
  padding: 1.5rem;
  margin-top: 1rem;
  overflow-x: auto;
}}
.mermaid svg {{ max-width: 100%; }}
@media (max-width: 700px) {{
  header h1 {{ font-size: 1.6rem; }}
  .card {{ flex: 1 1 100%; }}
  section {{ padding: 1rem; }}
}}
</style>
</head>
<body>
<header>
  <h1>Trace</h1>
  <div class="subtitle">Institutional Memory Engine &mdash; Decision Dashboard</div>
  <div class="timestamp">Generated {_esc(timestamp)}</div>
</header>
<div class="container">
{body}
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: 'dark',
  themeVariables: {{
    primaryColor: '#0f3460',
    primaryTextColor: '#e0e0e0',
    primaryBorderColor: '#e94560',
    lineColor: '#00cec9',
    secondaryColor: '#16213e',
    tertiaryColor: '#1a1a2e'
  }}
}});
</script>
</body>
</html>"""
