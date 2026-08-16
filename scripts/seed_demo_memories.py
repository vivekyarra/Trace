"""Idempotently seed the two secondary live-demo memories with Titan vectors."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import UUID, uuid5

import boto3
from sqlalchemy import create_engine, text

NAMESPACE = UUID("8f379319-c17c-4ae0-b989-995079052204")
SOURCE_URL = (
    "https://github.com/vivekyarra/Trace/blob/main/"
    "docs/evidence/demo-memory-examples.md"
)
EXAMPLES = (
    {
        "display_id": "TRACE-MEMORY-00402",
        "memory_type": "ARCHITECTURAL_DECISION",
        "title": "Cross-service commands use the durable queue and outbox",
        "decision": (
            "Route cross-service commands through the durable queue and outbox; "
            "do not send synchronous HTTP commands directly between services."
        ),
        "rationale": (
            "A downstream timeout must not lose an accepted command or leave the "
            "caller guessing whether it was applied."
        ),
        "rejected": "Direct requests.post calls between API and billing services.",
        "future": (
            "New cross-service command paths must enqueue durably and publish from "
            "the transactional outbox."
        ),
        "security": False,
        "severity": "HIGH",
        "scope": "services/commands",
        "anchor": "#architecture-decision",
    },
    {
        "display_id": "TRACE-MEMORY-00403",
        "memory_type": "INCIDENT_LESSON",
        "title": "Authentication secrets never enter request logs",
        "decision": (
            "Redact Authorization, Cookie, and session-token values before request "
            "metadata reaches any log sink."
        ),
        "rationale": (
            "An incident exposed reusable bearer tokens in centralized logs and "
            "required emergency credential rotation."
        ),
        "rejected": "Logging complete request headers during authentication failures.",
        "future": (
            "Every new request logger must apply the shared secret-field redactor "
            "before serialization."
        ),
        "security": True,
        "severity": "CRITICAL",
        "scope": "security/request-logging",
        "anchor": "#incident-and-security-lesson",
    },
)


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def embedding(text_value: str) -> list[float]:
    response = boto3.client("bedrock-runtime", region_name="ap-south-1").invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(
            {"inputText": text_value, "dimensions": 1024, "normalize": True}
        ),
        contentType="application/json",
        accept="application/json",
    )
    return list(json.loads(response["body"].read())["embedding"])


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(value, ".9g") for value in values) + "]"


def main() -> int:
    database_url = required("DATABASE_URL")
    for scheme in ("postgresql://", "postgres://"):
        if database_url.startswith(scheme):
            database_url = database_url.replace(scheme, "cockroachdb://", 1)
            break
    organization_id = UUID(required("TRACE_ORGANIZATION_ID"))
    repository_id = UUID(required("TRACE_REPOSITORY_ID"))
    engine = create_engine(database_url, pool_pre_ping=True)
    now = datetime.now(timezone.utc)
    inserted: list[str] = []
    for example in EXAMPLES:
        memory_id = uuid5(NAMESPACE, str(example["display_id"]))
        semantic_text = "\n".join(
            str(example[key]) for key in ("title", "decision", "rationale", "future")
        )
        params = {
            **example,
            "id": memory_id,
            "organization_id": organization_id,
            "repository_id": repository_id,
            "content_hash": hashlib.sha256(semantic_text.encode()).hexdigest(),
            "semantic_key": f"demo/{str(example['display_id']).lower()}",
            "embedding": vector_literal(embedding(semantic_text)),
            "now": now,
            "source_id": uuid5(NAMESPACE, f"source-{example['display_id']}"),
            "source_url": SOURCE_URL + str(example["anchor"]),
            "source_hash": hashlib.sha256(
                (SOURCE_URL + str(example["anchor"])).encode()
            ).hexdigest(),
            "scope_id": uuid5(NAMESPACE, f"scope-{example['display_id']}"),
        }
        with engine.begin() as connection:
            created = connection.execute(
                text(
                    """
                    INSERT INTO memories (
                        id, organization_id, repository_id, display_id, memory_type,
                        title, decision, rationale, rejected_alternative,
                        future_implication, status, confidence, confidence_basis,
                        security_relevant, severity, content_hash, semantic_key,
                        embedding, embedding_model, embedding_version, embedded_at,
                        valid_from, version, created_by_actor_type,
                        created_by_actor_id, created_at, updated_at
                    ) VALUES (
                        :id, :organization_id, :repository_id, :display_id, :memory_type,
                        :title, :decision, :rationale, :rejected, :future, 'ACTIVE',
                        0.95, 'documented production demo precedent', :security,
                        :severity, :content_hash, :semantic_key,
                        CAST(:embedding AS VECTOR), 'amazon.titan-embed-text-v2:0',
                        'v2-1024', :now, :now, 1, 'SYSTEM', 'trace-seed', :now, :now
                    ) ON CONFLICT (repository_id, content_hash) DO NOTHING
                    RETURNING id
                    """
                ),
                params,
            ).scalar_one_or_none()
            if created is None:
                continue
            connection.execute(
                text(
                    """
                    INSERT INTO memory_sources (
                        id, memory_id, source_type, source_external_id, source_url,
                        source_excerpt, source_hash, captured_at
                    ) VALUES (
                        :source_id, :id,
                        CASE WHEN :security THEN 'INCIDENT' ELSE 'ADR' END,
                        :display_id, :source_url, :rationale, :source_hash, :now
                    )
                    """
                ),
                params,
            )
            connection.execute(
                text(
                    """
                    INSERT INTO memory_scopes (id, memory_id, scope_type, scope_value)
                    VALUES (:scope_id, :id, 'DOMAIN', :scope)
                    """
                ),
                params,
            )
            inserted.append(str(example["display_id"]))
    print(json.dumps({"inserted": inserted, "status": "live"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
