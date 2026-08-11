"""Idempotent admission rules shared by webhook and SQS handlers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


def retry_delay_seconds(attempt: int) -> int:
    """Bounded retry schedule for transient delivery failures."""
    if attempt < 1:
        raise ValueError("attempt must start at one")
    return min(300, 2 ** (attempt - 1))


@dataclass(frozen=True)
class EventAdmission:
    provider: str
    delivery_id: str
    repository_external_id: str

    @property
    def idempotency_key(self) -> str:
        raw = f"{self.provider}:{self.repository_external_id}:{self.delivery_id}".encode()
        return sha256(raw).hexdigest()

    def outbox_deduplication_key(self, event_type: str) -> str:
        return f"{self.idempotency_key}:{event_type}"
