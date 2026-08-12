import json

from infra.judge_console_lambda import handler


def test_public_judge_console_is_read_only_and_truth_labelled() -> None:
    page = handler({"rawPath": "/"}, None)
    assert page["statusCode"] == 200
    assert "AWS DEPLOYED · PUBLIC · READ ONLY" in page["body"]
    assert "does not claim a fresh Bedrock run" in page["body"]
    assert "TRACE-MEMORY-00401" in page["body"]

    status = handler({"rawPath": "/api/status"}, None)
    payload = json.loads(status["body"])
    assert payload["write_routes"] == 0
    assert payload["retrieval"]["id"] == "8033c0ed-9596-4aeb-ba95-e31d5825ac34"
    assert payload["status"] == "verified-live-proof-snapshot"


def test_public_judge_console_rejects_unknown_routes() -> None:
    assert handler({"rawPath": "/write"}, None)["statusCode"] == 404
