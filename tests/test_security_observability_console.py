import pytest

from trace_memory.console import render_console
from trace_memory.observability import Metrics
from trace_memory.security import redact, validate_database_url


def test_remote_database_requires_verified_tls() -> None:
    with pytest.raises(ValueError, match="verify-full"):
        validate_database_url("cockroachdb://user@db.example/trace")
    validate_database_url("cockroachdb://user@db.example/trace?sslmode=verify-full")
    validate_database_url("cockroachdb://localhost/trace")
    with pytest.raises(ValueError, match="CockroachDB SQLAlchemy dialect"):
        validate_database_url("postgresql://user@db.example/trace?sslmode=verify-full")


def test_redaction_is_recursive() -> None:
    assert redact({"token": "bad", "nested": {"Authorization": "bad", "ok": 1}}) == {
        "token": "[REDACTED]", "nested": {"Authorization": "[REDACTED]", "ok": 1}}


def test_metrics_are_prometheus_compatible() -> None:
    metrics = Metrics()
    metrics.increment("trace_tasks_total", labels={"status": "ok"})
    assert metrics.render() == 'trace_tasks_total{status="ok"} 1\n'
    metrics.increment("trace_tasks_total", labels={"error": 'bad"\nline'})
    assert 'error="bad\\"\\nline"' in metrics.render()


def test_console_escapes_runtime_content() -> None:
    page = render_console({"counts": {"tasks": 1}, "note": "<script>alert(1)</script>"})
    assert "<script>alert" not in page
    assert "Trace Judge Console" in page
