import json

from infra import judge_console_lambda
from infra.judge_console_lambda import PRESET_DIFF, handler, run_trace


class FakeEmbedder:
    model_id = "fake-titan"

    def embed(self, text: str) -> list[float]:
        assert "permission_cache" in text
        return [0.1] * 1024


class FakeRetriever:
    def retrieve(self, embedding: list[float], *, limit: int = 5) -> list[dict[str, object]]:
        assert len(embedding) == 1024
        assert limit == 5
        return [
            {
                "id": "memory-uuid",
                "display_id": "TRACE-MEMORY-00401",
                "decision": "Invalidate authorization decisions immediately after revocation.",
                "vector_distance": 0.08,
                "source_url": "https://github.com/vivekyarra/Trace/pull/4",
            }
        ]


class FakeClassifier:
    model_id = "fake-claude"

    def classify(self, diff: str, candidates: list[dict[str, object]]) -> dict[str, object]:
        assert diff == PRESET_DIFF
        assert candidates[0]["display_id"] == "TRACE-MEMORY-00401"
        return {
            "classification": "CONFLICT",
            "severity": "HIGH",
            "summary": "The ten-minute cache reintroduces stale authorization decisions.",
            "selected_memory_ids": ["TRACE-MEMORY-00401"],
            "final_action": "Reject the cache until revocation invalidation is implemented.",
        }


class ClearClassifier(FakeClassifier):
    def classify(self, diff: str, candidates: list[dict[str, object]]) -> dict[str, object]:
        result = super().classify(diff, candidates)
        result["classification"] = "CLEAR"
        result["severity"] = "LOW"
        return result


def test_live_run_traverses_embedding_retrieval_classification_and_receipt() -> None:
    result = run_trace(
        PRESET_DIFF,
        embedder=FakeEmbedder(),
        retriever=FakeRetriever(),
        classifier=FakeClassifier(),
    )

    assert result["mode"] == "LIVE"
    assert [stage["service"] for stage in result["stages"]] == [
        "Amazon Bedrock",
        "CockroachDB Cloud",
        "Amazon Bedrock",
    ]
    assert result["judgment"]["classification"] == "CONFLICT"
    receipt = result["memory_consequence_receipt"]
    assert receipt["memory_changed_review"] is True
    assert receipt["governing_memory_ids"] == ["TRACE-MEMORY-00401"]
    assert receipt["write_routes"] == 0


def test_retrieved_memory_does_not_change_review_without_a_conflict() -> None:
    result = run_trace(
        PRESET_DIFF,
        embedder=FakeEmbedder(),
        retriever=FakeRetriever(),
        classifier=ClearClassifier(),
    )

    receipt = result["memory_consequence_receipt"]
    assert result["judgment"]["selected_memory_ids"] == ["TRACE-MEMORY-00401"]
    assert receipt["memory_changed_review"] is False
    assert receipt["governing_memory_ids"] == []
    assert receipt["memory_conflict_findings"] == 0


def test_public_console_primary_action_is_live_without_replay() -> None:
    page = handler({"rawPath": "/", "requestContext": {"http": {"method": "GET"}}}, None)
    assert page["statusCode"] == 200
    assert ">Run Trace<" in page["body"]
    assert "<p>" not in page["body"]
    assert "<p " not in page["body"]
    assert "REPLAY" not in page["body"]
    assert "NO RESULT FABRICATED" in page["body"]
    assert "html,body{height:100%;overflow:hidden}" in page["body"]
    assert "white-space:nowrap" in page["body"]

    status = handler({"rawPath": "/api/status"}, None)
    payload = json.loads(status["body"])
    assert payload["primary_mode"] == "live-read-only"
    assert payload["write_routes"] == 0
    assert payload["replay_mode"] is False
    assert payload["rate_limit_per_warm_instance_per_minute"] == 12


def test_run_endpoint_returns_fresh_result(monkeypatch) -> None:
    monkeypatch.setattr(judge_console_lambda, "_live_run", lambda diff: {"mode": "LIVE", "diff": diff})
    response = handler(
        {
            "rawPath": "/api/run",
            "body": json.dumps({"diff": "diff --git a/x b/x"}),
            "requestContext": {"http": {"method": "POST"}},
        },
        None,
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["mode"] == "LIVE"


def test_public_console_rejects_unknown_and_write_routes() -> None:
    assert handler({"rawPath": "/write"}, None)["statusCode"] == 404
    empty = handler(
        {
            "rawPath": "/api/run",
            "body": json.dumps({"diff": ""}),
            "requestContext": {"http": {"method": "POST"}},
        },
        None,
    )
    assert empty["statusCode"] in {400, 503}


def test_dependency_failure_does_not_expose_cloud_identity(monkeypatch) -> None:
    error = RuntimeError("denied")
    error.response = {
        "Error": {
            "Code": "AccessDeniedException",
            "Message": "arn:aws:sts::123456789012:assumed-role/private-role is denied",
        }
    }

    def fail(_diff: str) -> dict[str, object]:
        raise error

    monkeypatch.setattr(judge_console_lambda, "_live_run", fail)
    response = handler(
        {
            "rawPath": "/api/run",
            "body": json.dumps({"diff": "diff --git a/x b/x"}),
            "requestContext": {"http": {"method": "POST"}},
        },
        None,
    )
    payload = response["body"]
    assert response["statusCode"] == 503
    assert "AccessDeniedException" in payload
    assert "123456789012" not in payload
    assert "private-role" not in payload
