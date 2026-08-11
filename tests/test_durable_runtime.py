import pytest

from lore.runtime import EventAdmission, retry_delay_seconds


def test_delivery_idempotency_is_stable_and_repository_scoped() -> None:
    one = EventAdmission("github", "delivery-1", "repo-a")
    assert one.idempotency_key == EventAdmission("github", "delivery-1", "repo-a").idempotency_key
    assert one.idempotency_key != EventAdmission("github", "delivery-1", "repo-b").idempotency_key
    assert one.outbox_deduplication_key("review.ready").endswith(":review.ready")


def test_retry_backoff_is_bounded() -> None:
    assert retry_delay_seconds(1) == 1
    assert retry_delay_seconds(20) == 300
    with pytest.raises(ValueError):
        retry_delay_seconds(0)
