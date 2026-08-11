"""GitHub webhook admission and least-privilege REST operations."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from trace_memory.domain import AgentTask, OutboxEvent
from trace_memory.runtime.tasks import EventAdmission

MAX_WEBHOOK_BYTES = 2 * 1024 * 1024
SUPPORTED_EVENTS = {"issues", "issue_comment", "pull_request", "pull_request_review", "push", "ping"}


class AdmissionStore(Protocol):
    def admit(self, task: AgentTask, event: OutboxEvent) -> bool: ...


def verify_github_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not signature.startswith("sha256=") or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:], expected)


@dataclass(frozen=True)
class WebhookResult:
    status_code: int
    message: str
    admitted: bool = False
    task_id: UUID | None = None


@dataclass
class GitHubWebhookRuntime:
    secret: str
    organization_id: UUID
    repository_id: UUID
    repository_external_id: str
    store: AdmissionStore

    def handle(self, headers: Mapping[str, str], body: bytes) -> WebhookResult:
        normalized = {key.lower(): value for key, value in headers.items()}
        if len(body) > MAX_WEBHOOK_BYTES:
            return WebhookResult(413, "payload too large")
        if not verify_github_signature(body, normalized.get("x-hub-signature-256"), self.secret):
            return WebhookResult(401, "invalid signature")
        event_name = normalized.get("x-github-event", "")
        delivery_id = normalized.get("x-github-delivery", "")
        if event_name not in SUPPORTED_EVENTS or not delivery_id:
            return WebhookResult(400, "unsupported or incomplete delivery")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return WebhookResult(400, "invalid JSON")
        full_name = str(payload.get("repository", {}).get("full_name", ""))
        if str(payload.get("sender", {}).get("type", "")).casefold() == "bot":
            return WebhookResult(200, "bot event ignored")
        if event_name != "ping" and full_name.casefold() != self.repository_external_id.casefold():
            return WebhookResult(403, "repository does not match configured tenant")

        admission = EventAdmission("github", delivery_id, self.repository_external_id)
        task_type = self._task_type(event_name, str(payload.get("action", "")))
        safe_payload = {
            "provider": "github", "event": event_name, "action": payload.get("action"),
            "delivery_id": delivery_id, "repository": full_name,
            "sender": payload.get("sender", {}).get("login"),
            "issue_number": payload.get("issue", {}).get("number"),
            "pull_request_number": payload.get("pull_request", {}).get("number"),
            "ref": payload.get("ref"), "after": payload.get("after"),
        }
        task = AgentTask(
            organization_id=self.organization_id, repository_id=self.repository_id,
            task_type=task_type, idempotency_key=admission.idempotency_key,
            payload=safe_payload,
        )
        event = OutboxEvent(
            organization_id=self.organization_id, repository_id=self.repository_id,
            aggregate_type="agent_task", aggregate_id=task.id, event_type="task.admitted",
            payload={"task_type": task_type, **safe_payload},
            deduplication_key=admission.outbox_deduplication_key("task.admitted"),
        )
        admitted = self.store.admit(task, event)
        return WebhookResult(202 if admitted else 200, "admitted" if admitted else "duplicate", admitted, task.id)

    @staticmethod
    def _task_type(event: str, action: str) -> str:
        if event == "pull_request" and action == "closed":
            return "tracekeeper"
        if event.startswith("pull_request"):
            return "guardkeeper"
        if event in {"issues", "issue_comment"}:
            return "specforge"
        if event == "ping":
            return "healthcheck"
        return "triage"


@dataclass(frozen=True)
class GitHubClient:
    token: str
    repository: str
    api_url: str = "https://api.github.com"
    timeout_seconds: int = 15

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None,
                 *, accept: str = "application/vnd.github+json", raw: bool = False) -> object:
        endpoint = urlsplit(self.api_url)
        if endpoint.scheme != "https" or endpoint.hostname != "api.github.com" or endpoint.username:
            raise ValueError("GitHub API URL must be https://api.github.com")
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.api_url}/repos/{self.repository}/{path.lstrip('/')}", data=data, method=method,
            headers={"Accept": accept, "Authorization": f"Bearer {self.token}",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "trace-memory-runtime"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read()
                if raw:
                    return response_body.decode("utf-8", errors="replace")
                return json.loads(response_body) if response_body else {}
        except HTTPError as error:
            # Never include the token or an unbounded remote response in errors.
            raise RuntimeError(f"GitHub API {method} {path} failed with HTTP {error.code}") from error

    def pull_request(self, number: int) -> dict[str, object]:
        return dict(self._request("GET", f"pulls/{number}"))

    def pull_request_files(self, number: int) -> list[dict[str, object]]:
        return list(self._request("GET", f"pulls/{number}/files?per_page=100"))

    def complete_pull_request_diff(self, number: int, files: list[dict[str, object]]) -> tuple[str, bool]:
        """Use file patches when complete; otherwise fetch GitHub's full diff representation."""
        incomplete = len(files) >= 100 or any(
            not file.get("patch") or bool(file.get("previous_filename"))
            for file in files if str(file.get("status", "")) != "removed"
        )
        patch = "\n".join(str(file.get("patch", "")) for file in files)
        if incomplete:
            full = str(self._request("GET", f"pulls/{number}", accept="application/vnd.github.diff", raw=True))
            return full[:500_000], len(full) <= 500_000
        return patch[:500_000], len(patch) <= 500_000

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        return list(self._request("GET", f"issues/{number}/comments?per_page=100"))

    def issue(self, number: int) -> dict[str, object]:
        return dict(self._request("GET", f"issues/{number}"))

    def post_comment(self, number: int, body: str) -> dict[str, object]:
        if not body.strip() or len(body) > 65_536:
            raise ValueError("comment must contain 1..65536 characters")
        return dict(self._request("POST", f"issues/{number}/comments", {"body": body}))

    def post_comment_once(self, number: int, task_id: UUID, body: str) -> dict[str, object]:
        """Close the accepted-comment/crashed-before-commit duplication window."""
        marker = f"<!-- trace-task:{task_id} -->"
        for comment in self.issue_comments(number):
            if marker in str(comment.get("body", "")):
                return comment
        return self.post_comment(number, f"{marker}\n{body}")
