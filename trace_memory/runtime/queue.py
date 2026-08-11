"""AWS SQS transport and transactional-outbox workers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
from uuid import UUID, uuid4

from trace_memory.runtime.tasks import retry_delay_seconds


class QueueClient(Protocol):
    def send_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def receive_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def delete_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def change_message_visibility(self, **kwargs: Any) -> dict[str, Any]: ...


class DurableRuntimeStore(Protocol):
    def claim_outbox(self, *, worker_id: UUID, lease_seconds: int = 60,
                     limit: int = 50) -> list[dict[str, object]]: ...
    def mark_published(self, event_id: UUID, *, worker_id: UUID) -> bool: ...
    def release_outbox(self, event_id: UUID, *, worker_id: UUID, error: str) -> None: ...
    def start_task(self, task_id: UUID, *, lease_seconds: int = 180) -> int | None: ...
    def task_status(self, task_id: UUID) -> str | None: ...
    def finish_task(self, task_id: UUID) -> None: ...
    def fail_task(self, task_id: UUID, *, error: str, retry_at: datetime | None) -> None: ...


@dataclass(frozen=True)
class SqsPublisher:
    client: QueueClient
    queue_url: str

    def publish(self, event: dict[str, object]) -> str:
        body = json.dumps(event, default=str, separators=(",", ":"), sort_keys=True)
        args: dict[str, Any] = {"QueueUrl": self.queue_url, "MessageBody": body}
        if self.queue_url.endswith(".fifo"):
            args.update(MessageGroupId=str(event["repository_id"]),
                        MessageDeduplicationId=str(event["deduplication_key"]))
        response = self.client.send_message(**args)
        return str(response["MessageId"])


@dataclass
class OutboxWorker:
    store: DurableRuntimeStore
    publisher: SqsPublisher
    worker_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.worker_id is None:
            self.worker_id = uuid4()

    def run_once(self, *, limit: int = 50) -> int:
        published = 0
        for event in self.store.claim_outbox(worker_id=self.worker_id, limit=limit):
            event_id = UUID(str(event["id"]))
            try:
                self.publisher.publish(event)
                if self.store.mark_published(event_id, worker_id=self.worker_id):
                    published += 1
            except Exception as error:
                self.store.release_outbox(event_id, worker_id=self.worker_id,
                                          error=f"{type(error).__name__}: {error}")
        return published


@dataclass
class SqsTaskWorker:
    """Consume admitted tasks; database state is the source of retry truth."""

    client: QueueClient
    queue_url: str
    store: DurableRuntimeStore
    handler: Callable[[dict[str, object]], None]
    visibility_timeout: int = 60

    def run_once(self, *, max_messages: int = 10, wait_seconds: int = 10) -> int:
        response = self.client.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=max(1, min(10, max_messages)),
            WaitTimeSeconds=max(0, min(20, wait_seconds)), VisibilityTimeout=self.visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        completed = 0
        for message in response.get("Messages", []):
            receipt = message["ReceiptHandle"]
            task_id: UUID | None = None
            attempt: int | None = None
            event: dict[str, object] = {}
            try:
                decoded = json.loads(message["Body"])
                if not isinstance(decoded, dict):
                    raise ValueError("SQS event must be a JSON object")
                event = decoded
                task_id = UUID(str(event["aggregate_id"]))
                attempt = self.store.start_task(task_id, lease_seconds=self.visibility_timeout)
                if attempt is None:
                    if self.store.task_status(task_id) == "SUCCEEDED":
                        self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
                    continue
                self.handler(event)
                self.store.finish_task(task_id)
                self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
                completed += 1
            except Exception as error:
                # Database attempt_count is authoritative; SQS receive count is transport telemetry only.
                attempt = attempt or 1
                delay = retry_delay_seconds(attempt)
                permanent = isinstance(error, (ValueError, KeyError, json.JSONDecodeError))
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)
                            if not permanent and attempt < 3 else None)
                if task_id is not None:
                    self.store.fail_task(task_id, error=f"{type(error).__name__}: {error}", retry_at=retry_at)
                if retry_at:
                    self.client.change_message_visibility(
                        QueueUrl=self.queue_url, ReceiptHandle=receipt, VisibilityTimeout=delay)
                # Final/permanent failures are deliberately not deleted. SQS RedrivePolicy is
                # the single DLQ mechanism and preserves the original immutable message.
        return completed
