from uuid import uuid4

from trace_memory.runtime.queue import OutboxWorker, SqsPublisher, SqsTaskWorker


class Queue:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(("send", kwargs))
        return {"MessageId": "m-1"}

    def receive_message(self, **kwargs):
        return {"Messages": self.messages}

    def delete_message(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return {}

    def change_message_visibility(self, **kwargs):
        self.calls.append(("visibility", kwargs))
        return {}


class Store:
    def __init__(self, event=None, attempt=1):
        self.event = event
        self.attempt = attempt
        self.states = []

    def claim_outbox(self, *, worker_id, lease_seconds=60, limit=50):
        return [self.event] if self.event else []

    def mark_published(self, event_id, *, worker_id):
        self.states.append(("published", event_id))
        return True

    def release_outbox(self, event_id, *, worker_id, error):
        self.states.append(("released", event_id, error))

    def start_task(self, task_id, *, lease_seconds=180):
        self.states.append(("running", task_id))
        return self.attempt

    def task_status(self, task_id):
        return "RUNNING"

    def finish_task(self, task_id):
        self.states.append(("succeeded", task_id))

    def fail_task(self, task_id, *, error, retry_at):
        self.states.append(("failed", task_id, retry_at))


def test_fifo_outbox_publishes_then_marks() -> None:
    event = {"id": uuid4(), "repository_id": uuid4(), "deduplication_key": "d", "payload": {}}
    queue, store = Queue(), Store(event)
    assert OutboxWorker(store, SqsPublisher(queue, "https://sqs/x.fifo")).run_once() == 1
    assert queue.calls[0][1]["MessageDeduplicationId"] == "d"
    assert store.states[0][0] == "published"


def test_task_worker_completes_and_deletes() -> None:
    task_id = uuid4()
    queue = Queue([{"Body": '{"aggregate_id":"%s"}' % task_id, "ReceiptHandle": "r", "Attributes": {"ApproximateReceiveCount": "1"}}])
    store = Store()
    assert SqsTaskWorker(queue, "queue", store, lambda event: None).run_once(wait_seconds=0) == 1
    assert [state[0] for state in store.states] == ["running", "succeeded"]
    assert queue.calls[-1][0] == "delete"


def test_poison_task_is_dead_lettered_after_final_attempt() -> None:
    task_id = uuid4()
    queue = Queue([{"Body": '{"aggregate_id":"%s"}' % task_id, "ReceiptHandle": "r", "Attributes": {"ApproximateReceiveCount": "3"}}])
    store = Store(attempt=3)
    worker = SqsTaskWorker(queue, "queue", store, lambda event: (_ for _ in ()).throw(RuntimeError("no")))
    assert worker.run_once(wait_seconds=0) == 0
    assert store.states[-1][0] == "failed" and store.states[-1][2] is None
    assert not any(call[0] in {"send", "delete"} for call in queue.calls)
