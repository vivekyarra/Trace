import io
import json

import pytest

from trace_memory.ai.bedrock import BedrockEmbedder, BedrockReasoner, ReasoningEnvelope


class FakeBedrock:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"body": io.BytesIO(json.dumps(self.payload).encode())}

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"output": {"message": {"content": self.payload["content"]}}}


class AccessDeniedThenFallback:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            error = RuntimeError("denied")
            error.response = {"Error": {"Code": "AccessDeniedException"}}
            raise error
        return {
            "output": {
                "message": {
                    "content": [
                        {"text": '{"summary":"fallback","risk_level":"LOW","findings":[]}'}
                    ]
                }
            }
        }


def test_titan_embedding_records_expected_dimension_and_normalization() -> None:
    client = FakeBedrock({"embedding": [0.1] * 1024})
    result = BedrockEmbedder(client).embed("retry storms are expensive")
    assert result.dimension == 1024
    assert json.loads(client.calls[0]["body"])["normalize"] is True


def test_embedding_dimension_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="expected 1024"):
        BedrockEmbedder(FakeBedrock({"embedding": [0.1]})).embed("x")


def test_reasoner_validates_structured_output_before_returning_it() -> None:
    client = FakeBedrock({"content": [{"text": '{"summary":"risk found","risk_level":"HIGH","findings":["secret"]}'}]})
    result = BedrockReasoner(client).reason_json(system="system", user_content="untrusted", output_type=ReasoningEnvelope)
    assert result.risk_level == "HIGH"
    request = client.calls[0]
    assert request["modelId"] == "apac.amazon.nova-pro-v1:0"
    assert "<OUTPUT_SCHEMA>" in request["system"][0]["text"]
    assert '"risk_level"' in request["system"][0]["text"]


def test_reasoner_accepts_fenced_json_from_primary_model() -> None:
    client = FakeBedrock(
        {"content": [{"text": '```json\n{"summary":"risk found","risk_level":"HIGH","findings":[]}\n```'}]}
    )
    result = BedrockReasoner(client).reason_json(
        system="system", user_content="untrusted", output_type=ReasoningEnvelope
    )
    assert result.risk_level == "HIGH"


def test_reasoner_rejects_unvalidated_model_output() -> None:
    client = FakeBedrock({"content": [{"text": '{"summary":"bad","risk_level":"MAYBE"}'}]})
    with pytest.raises(ValueError, match="structured-output"):
        BedrockReasoner(client).reason_json(system="system", user_content="untrusted", output_type=ReasoningEnvelope)


def test_reasoner_truthfully_records_strong_fallback_when_primary_is_unavailable() -> None:
    client = AccessDeniedThenFallback()
    reasoner = BedrockReasoner(client)
    result = reasoner.reason_json(system="system", user_content="untrusted", output_type=ReasoningEnvelope)
    assert result.summary == "fallback"
    assert reasoner.model_id == "mistral.mistral-large-2402-v1:0"
    assert client.calls[1]["modelId"] == "mistral.mistral-large-2402-v1:0"
