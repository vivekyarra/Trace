import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from trace_memory.runtime.github import (
    GitHubAppTokenProvider,
    GitHubClient,
    GitHubWebhookRuntime,
    verify_github_signature,
)


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


def test_issue_comments_paginates_until_the_last_page(monkeypatch) -> None:
    paths: list[str] = []

    def fake_request(self, method, path, payload=None, **kwargs):
        paths.append(path)
        if path.endswith("page=1"):
            return [{"id": number} for number in range(100)]
        return [{"id": 100}]

    monkeypatch.setattr(GitHubClient, "_request", fake_request)
    comments = GitHubClient("token", "acme/widget").issue_comments(7)

    assert len(comments) == 101
    assert paths == [
        "issues/7/comments?per_page=100&page=1",
        "issues/7/comments?per_page=100&page=2",
    ]


def test_github_app_provider_mints_and_caches_installation_token(monkeypatch) -> None:
    import jwt

    import trace_memory.runtime.github as github_runtime

    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"token":"installation-token"}'

    monkeypatch.setattr(jwt, "encode", lambda *_args, **_kwargs: "app-jwt")
    monkeypatch.setattr(
        github_runtime,
        "urlopen",
        lambda request, **_kwargs: requests.append(request) or Response(),
    )
    provider = GitHubAppTokenProvider("4604859", "153959613", "private-key")

    assert provider.access_token() == "installation-token"
    assert provider.access_token() == "installation-token"
    assert len(requests) == 1
    assert requests[0].full_url.endswith("/app/installations/153959613/access_tokens")
    assert requests[0].headers["Authorization"] == "Bearer app-jwt"
