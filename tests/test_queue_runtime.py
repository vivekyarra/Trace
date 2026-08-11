from uuid import uuid4

from lore.runtime.queue import OutboxWorker, SqsPublisher, SqsTaskWorker


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
    def __init__(self, event=None):
        self.event = event
        self.states = []

    def pending_outbox(self, *, limit=50):
        return [self.event] if self.event else []

    def mark_published(self, event_id):
        self.states.append(("published", event_id))

    def start_task(self, task_id):
        self.states.append(("running", task_id))
        return True

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
    store = Store()
    worker = SqsTaskWorker(queue, "queue", store, lambda event: (_ for _ in ()).throw(RuntimeError("no")),
                           dead_letter_queue_url="dead.fifo")
    assert worker.run_once(wait_seconds=0) == 0
    assert store.states[-1][0] == "failed" and store.states[-1][2] is None
    assert [call[0] for call in queue.calls[-2:]] == ["send", "delete"]
