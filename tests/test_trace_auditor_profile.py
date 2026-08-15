import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_managed_mcp_configuration_is_oauth_and_contains_no_secret() -> None:
    config = json.loads((ROOT / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    server = config["servers"]["cockroachdb-cloud"]
    assert server["url"] == "https://cockroachlabs.cloud/mcp"
    assert set(server["headers"]) == {"mcp-cluster-id"}


def test_trace_auditor_exposes_only_read_only_managed_mcp_tools() -> None:
    profile = (ROOT / ".github" / "agents" / "trace-auditor.agent.md").read_text(encoding="utf-8")
    assert "cockroachdb-cloud/select_query" in profile
    assert "cockroachdb-cloud/explain_query" in profile
    for write_tool in ("create_database", "create_table", "insert_rows"):
        assert f"cockroachdb-cloud/{write_tool}" not in profile
    assert "Retrieval or selection alone is insufficient" in profile
