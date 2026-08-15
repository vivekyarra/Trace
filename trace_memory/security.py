"""Runtime security boundaries shared by transports and operators."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

_SECRET_KEYS = re.compile(r"(authorization|token|secret|password|signature|api[_-]?key)", re.I)


def redact(value: object, *, key: str = "") -> object:
    if _SECRET_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def validate_database_url(database_url: str, *, allow_insecure_local: bool = False) -> None:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"cockroachdb", "postgresql", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL must use a PostgreSQL-compatible scheme")
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not allow_insecure_local and not local and "sslmode=verify-full" not in parsed.query:
        raise ValueError("remote DATABASE_URL must enforce sslmode=verify-full")


@dataclass(frozen=True)
class RuntimeSettings:
    database_url: str
    github_webhook_secret: str
    github_token: str
    github_repository: str
    sqs_queue_url: str
    sqs_dead_letter_queue_url: str
    aws_region: str = "ap-south-1"

    @classmethod
    def from_env(cls) -> RuntimeSettings:
        required = {
            "database_url": "DATABASE_URL", "github_webhook_secret": "GITHUB_WEBHOOK_SECRET",
            "github_token": "GITHUB_TOKEN", "github_repository": "GITHUB_REPOSITORY",
            "sqs_queue_url": "TRACE_SQS_QUEUE_URL",
            "sqs_dead_letter_queue_url": "TRACE_SQS_DLQ_URL",
        }
        values: dict[str, str] = {}
        missing: list[str] = []
        for field, name in required.items():
            value = os.environ.get(name, "").strip()
            if not value:
                missing.append(name)
            values[field] = value
        if missing:
            raise ValueError(f"missing required settings: {', '.join(sorted(missing))}")
        validate_database_url(values["database_url"])
        if len(values["github_webhook_secret"]) < 32:
            raise ValueError("GITHUB_WEBHOOK_SECRET must be at least 32 characters")
        return cls(**values, aws_region=os.environ.get("AWS_REGION", "ap-south-1"))
