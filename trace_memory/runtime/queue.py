"""AWS SQS transport and transactional-outbox workers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
from uuid import UUID

from trace_memory.runtime.tasks import retry_delay_seconds


class QueueClient(Protocol):
    def send_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def receive_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def delete_message(self, **kwargs: Any) -> dict[str, Any]: ...
    def change_message_visibility(self, **kwargs: Any) -> dict[str, Any]: ...


class DurableRuntimeStore(Protocol):
    def pending_outbox(self, *, limit: int = 50) -> list[dict[str, object]]: ...
    def mark_published(self, event_id: UUID) -> None: ...
    def start_task(self, task_id: UUID) -> bool: ...
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

    def run_once(self, *, limit: int = 50) -> int:
        published = 0
        for event in self.store.pending_outbox(limit=limit):
            self.publisher.publish(event)
            self.store.mark_published(UUID(str(event["id"])))
            published += 1
        return published


@dataclass
class SqsTaskWorker:
    """Consume admitted tasks; database state is the source of retry truth."""

    client: QueueClient
    queue_url: str
    store: DurableRuntimeStore
    handler: Callable[[dict[str, object]], None]
    visibility_timeout: int = 60
    dead_letter_queue_url: str | None = None

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
            event: dict[str, object] = {}
            try:
                decoded = json.loads(message["Body"])
                if not isinstance(decoded, dict):
                    raise ValueError("SQS event must be a JSON object")
                event = decoded
                task_id = UUID(str(event["aggregate_id"]))
                if not self.store.start_task(task_id):
                    self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
                    continue
                self.handler(event)
                self.store.finish_task(task_id)
                self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
                completed += 1
            except Exception as error:
                attempt = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
                delay = retry_delay_seconds(attempt)
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay) if attempt < 3 else None
                if task_id is not None:
                    self.store.fail_task(task_id, error=f"{type(error).__name__}: {error}", retry_at=retry_at)
                if retry_at:
                    self.client.change_message_visibility(
                        QueueUrl=self.queue_url, ReceiptHandle=receipt, VisibilityTimeout=delay)
                else:
                    if self.dead_letter_queue_url:
                        dead = {"failed_event": event, "error_type": type(error).__name__, "attempt": attempt}
                        args: dict[str, Any] = {
                            "QueueUrl": self.dead_letter_queue_url,
                            "MessageBody": json.dumps(dead, default=str, separators=(",", ":")),
                        }
                        if self.dead_letter_queue_url.endswith(".fifo"):
                            args.update(MessageGroupId=str(event.get("repository_id", "unknown")),
                                        MessageDeduplicationId=f"{task_id}:failed")
                        self.client.send_message(**args)
                    # A configured DLQ preserves the forensic event. Without one, deletion
                    # still prevents an unbounded poison-message cost loop.
                    self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
        return completed
