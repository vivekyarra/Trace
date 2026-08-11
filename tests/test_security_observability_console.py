import pytest

from lore.console import render_console
from lore.observability import Metrics
from lore.security import redact, validate_database_url


def test_remote_database_requires_verified_tls() -> None:
    with pytest.raises(ValueError, match="verify-full"):
        validate_database_url("postgresql://user@db.example/lore")
    validate_database_url("postgresql://user@db.example/lore?sslmode=verify-full")
    validate_database_url("postgresql://localhost/lore")


def test_redaction_is_recursive() -> None:
    assert redact({"token": "bad", "nested": {"Authorization": "bad", "ok": 1}}) == {
        "token": "[REDACTED]", "nested": {"Authorization": "[REDACTED]", "ok": 1}}


def test_metrics_are_prometheus_compatible() -> None:
    metrics = Metrics()
    metrics.increment("lore_tasks_total", labels={"status": "ok"})
    assert metrics.render() == 'lore_tasks_total{status="ok"} 1\n'
    metrics.increment("lore_tasks_total", labels={"error": 'bad"\nline'})
    assert 'error="bad\\"\\nline"' in metrics.render()


def test_console_escapes_runtime_content() -> None:
    page = render_console({"counts": {"tasks": 1}, "note": "<script>alert(1)</script>"})
    assert "<script>alert" not in page
    assert "LORE Judge Console" in page
