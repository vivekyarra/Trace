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


def test_public_console_primary_action_is_live_and_fallback_is_truth_labelled() -> None:
    page = handler({"rawPath": "/", "requestContext": {"http": {"method": "GET"}}}, None)
    assert page["statusCode"] == 200
    assert "Run Trace live" in page["body"]
    assert "Fallback: verified 2026-08-11 replay evidence" in page["body"]
    assert "LIVE only after all three cloud stages return" in page["body"]

    status = handler({"rawPath": "/api/status"}, None)
    payload = json.loads(status["body"])
    assert payload["primary_mode"] == "live-read-only"
    assert payload["write_routes"] == 0
    assert payload["fallback"]["mode"] == "REPLAY"


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
