import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from trace_memory.runtime.github import GitHubClient, GitHubWebhookRuntime, verify_github_signature


class Store:
    def __init__(self):
        self.calls = []

    def admit(self, task, event):
        self.calls.append((task, event))
        return True


def signed(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_and_repository_bound_admission() -> None:
    secret = "s" * 32
    body = json.dumps({"action": "opened", "repository": {"full_name": "acme/widget"},
                       "pull_request": {"number": 7}, "sender": {"login": "dev"}}).encode()
    store = Store()
    runtime = GitHubWebhookRuntime(secret, uuid4(), uuid4(), "acme/widget", store)
    result = runtime.handle({"X-Hub-Signature-256": signed(secret, body),
                             "X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "d-1"}, body)
    assert result.status_code == 202 and result.admitted
    assert store.calls[0][0].task_type == "guardkeeper"
    assert store.calls[0][0].payload["pull_request_number"] == 7
    assert "title" not in store.calls[0][0].payload


def test_invalid_signature_fails_closed() -> None:
    runtime = GitHubWebhookRuntime("s" * 32, uuid4(), uuid4(), "acme/widget", Store())
    assert runtime.handle({"X-GitHub-Event": "ping"}, b"{}").status_code == 401
    assert not verify_github_signature(b"x", "sha256=no", "secret")


def test_github_client_rejects_untrusted_api_hosts_before_network() -> None:
    client = GitHubClient("token", "acme/widget", api_url="https://api.github.com.evil.example")
    with pytest.raises(ValueError, match="api.github.com"):
        client.pull_request(1)
