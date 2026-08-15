"""Read-only judge console with health, provenance, and runtime evidence."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol


class ConsoleSource(Protocol):
    def snapshot(self) -> dict[str, object]: ...


@dataclass
class DatabaseConsoleSource:
    database: object

    def snapshot(self) -> dict[str, object]:
        engine = getattr(self.database, "engine")
        query = """
            SELECT
              (SELECT count(*) FROM memories) AS memories,
              (SELECT count(*) FROM memories WHERE status = 'ACTIVE') AS active_memories,
              (SELECT count(*) FROM memories WHERE security_relevant) AS security_memories,
              (SELECT count(*) FROM agent_tasks) AS tasks,
              (SELECT count(*) FROM agent_tasks WHERE status = 'SUCCEEDED') AS succeeded_tasks,
              (SELECT count(*) FROM agent_tasks WHERE status = 'DEAD_LETTERED') AS dead_lettered_tasks,
              (SELECT count(*) FROM outbox_events WHERE published_at IS NULL) AS pending_outbox,
              (SELECT count(*) FROM retrieval_events) AS retrievals
        """
        from sqlalchemy import text
        with engine.connect() as connection:
            counts = dict(connection.execute(text(query)).mappings().one())
            recent = [dict(row) for row in connection.execute(text("""
                SELECT task_type, status, attempt_count, created_at, completed_at
                FROM agent_tasks ORDER BY created_at DESC LIMIT 10
            """)).mappings()]
        return {"status": "ok", "generated_at": datetime.now(timezone.utc).isoformat(),
                "counts": counts, "recent_tasks": recent}


def render_console(snapshot: dict[str, object]) -> str:
    payload = html.escape(json.dumps(snapshot, default=str, indent=2))
    counts = snapshot.get("counts", {})
    cards = "".join(
        f'<article><strong>{html.escape(str(value))}</strong><span>{html.escape(str(key).replace("_", " "))}</span></article>'
        for key, value in dict(counts).items()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Trace Judge Console</title>
<style>body{{margin:0;background:#09111f;color:#e6edf7;font:16px system-ui}}main{{max-width:1100px;margin:auto;padding:3rem 1.5rem}}
h1{{font-size:2.7rem;margin:.2rem 0}}p{{color:#9fb0c7}}section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin:2rem 0}}
article,pre{{background:#111d30;border:1px solid #263a57;border-radius:12px;padding:1.2rem}}strong{{display:block;color:#66e3c4;font-size:2rem}}span{{text-transform:capitalize;color:#9fb0c7}}pre{{overflow:auto;white-space:pre-wrap}}.live{{color:#66e3c4}}</style></head>
<body><main><p class="live">● LIVE READ-ONLY RUNTIME</p><h1>Institutional memory you can prove.</h1>
<p>CockroachDB is canonical. Every task is idempotent, every retrieval is attributable, and every change leaves an audit trail.</p>
<section>{cards}</section><h2>Judge evidence</h2><pre>{payload}</pre></main></body></html>"""


def serve_console(source: ConsoleSource, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/", "/api/status"}:
                self.send_error(404)
                return
            snapshot = source.snapshot()
            body = (json.dumps(snapshot, default=str) if self.path == "/api/status"
                    else render_console(snapshot)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if self.path.startswith("/api/") else "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()
