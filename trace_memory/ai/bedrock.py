"""Typed Amazon Bedrock adapters; callers cannot persist unvalidated model text."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

T = TypeVar("T", bound=BaseModel)


class BedrockRuntime(Protocol):
    def invoke_model(self, **kwargs: Any) -> dict[str, Any]: ...

    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


def _runtime(region: str) -> BedrockRuntime:
    import boto3

    return boto3.client("bedrock-runtime", region_name=region)


@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    model_id: str
    version: str
    dimension: int
    embedded_at: datetime


class BedrockEmbedder:
    """Titan Text Embeddings V2 adapter fixed to the schema's 1024 dimensions."""

    def __init__(self, client: BedrockRuntime | None = None, *, model_id: str | None = None,
                 region: str | None = None, dimension: int = 1024) -> None:
        self._region = region or os.environ.get("AWS_REGION", "ap-south-1")
        self._client = client or _runtime(self._region)
        self.model_id = model_id or os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
        self.dimension = dimension

    def embed(self, text: str) -> EmbeddingResult:
        if not text.strip():
            raise ValueError("cannot embed empty text")
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": self.dimension, "normalize": True}),
        )
        payload = json.loads(response["body"].read())
        values = payload["embedding"]
        if len(values) != self.dimension:
            raise ValueError(f"Bedrock returned {len(values)} dimensions; expected {self.dimension}")
        return EmbeddingResult(values=values, model_id=self.model_id, version="v2", dimension=self.dimension,
                               embedded_at=datetime.now(timezone.utc))


class ReasoningEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1)
    risk_level: str = Field(pattern=r"^(LOW|MEDIUM|HIGH)$")
    findings: list[str] = Field(default_factory=list)


class BedrockReasoner:
    """Configurable Bedrock Converse reasoning with strict JSON validation."""

    def __init__(self, client: BedrockRuntime | None = None, *, model_id: str | None = None,
                 fallback_model_id: str | None = None, region: str | None = None) -> None:
        self._region = region or os.environ.get("AWS_REGION", "ap-south-1")
        self._client = client or _runtime(self._region)
        self.primary_model_id = model_id or os.environ.get(
            "BEDROCK_REASONING_MODEL_ID", "apac.amazon.nova-pro-v1:0"
        )
        self.fallback_model_id = fallback_model_id or os.environ.get(
            "BEDROCK_FALLBACK_MODEL_ID", "mistral.mistral-large-2402-v1:0"
        )
        self.model_id = self.primary_model_id

    def reason_json(self, *, system: str, user_content: str, output_type: type[T], max_tokens: int = 800) -> T:
        schema = json.dumps(output_type.model_json_schema(), separators=(",", ":"), sort_keys=True)
        constrained_system = (
            f"{system}\nReturn exactly one JSON object with no markdown or commentary. "
            f"It must conform to this JSON Schema: <OUTPUT_SCHEMA>{schema}</OUTPUT_SCHEMA>"
        )
        try:
            response = self._client.converse(
                modelId=self.primary_model_id,
                system=[{"text": constrained_system}],
                messages=[{"role": "user", "content": [{"text": user_content}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
            )
            text = response["output"]["message"]["content"][0]["text"].strip()
            self.model_id = self.primary_model_id
        except Exception as error:
            response_data = getattr(error, "response", {})
            code = response_data.get("Error", {}).get("Code") if isinstance(response_data, dict) else None
            if code not in {"AccessDeniedException", "ResourceNotFoundException", "ValidationException"}:
                raise
            response = self._client.converse(
                modelId=self.fallback_model_id,
                system=[{"text": constrained_system}],
                messages=[{"role": "user", "content": [{"text": user_content}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
            )
            text = response["output"]["message"]["content"][0]["text"].strip()
            self.model_id = self.fallback_model_id
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return output_type.model_validate_json(text)
        except (KeyError, IndexError, ValidationError, ValueError) as error:
            raise ValueError("Bedrock response failed Trace structured-output validation") from error
