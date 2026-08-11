"""Minimal production HTTP ingress for GitHub, health, and metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lore.observability import Metrics
from lore.runtime.github import MAX_WEBHOOK_BYTES, GitHubWebhookRuntime


@dataclass
class RuntimeServer:
    webhook: GitHubWebhookRuntime
    metrics: Metrics

    def serve(self, *, host: str = "127.0.0.1", port: int = 8000) -> None:
        application = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/healthz":
                    self._reply(200, b'{"status":"ok"}', "application/json")
                elif self.path == "/metrics":
                    self._reply(200, application.metrics.render().encode(), "text/plain; version=0.0.4")
                else:
                    self.send_error(404)

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/webhooks/github":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(400)
                    return
                if length < 0 or length > MAX_WEBHOOK_BYTES:
                    self.send_error(413)
                    return
                result = application.webhook.handle(dict(self.headers), self.rfile.read(length))
                application.metrics.increment("lore_webhooks_total", labels={"status": str(result.status_code)})
                self._reply(result.status_code, json.dumps({"message": result.message,
                            "task_id": str(result.task_id) if result.task_id else None}).encode(), "application/json")

            def _reply(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        ThreadingHTTPServer((host, port), Handler).serve_forever()
