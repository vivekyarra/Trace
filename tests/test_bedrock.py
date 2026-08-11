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


def test_reasoner_rejects_unvalidated_model_output() -> None:
    client = FakeBedrock({"content": [{"text": '{"summary":"bad","risk_level":"MAYBE"}'}]})
    with pytest.raises(ValueError, match="structured-output"):
        BedrockReasoner(client).reason_json(system="system", user_content="untrusted", output_type=ReasoningEnvelope)
