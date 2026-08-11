"""Retry logic for external API calls."""

import time
import random
from typing import Optional, Callable, Any


def retry_with_backoff(
    func: Callable,
    max_retries: int = 5,
    base_delay: float = 1.0,
) -> Optional[Any]:
    """Retry a function with exponential backoff and jitter.

    Uses progressive delay with multiplier to avoid thundering herd.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
    return None


def retry_fixed(
    func: Callable,
    max_retries: int = 3,
    delay: float = 2.0,
) -> Optional[Any]:
    """Retry with fixed intervals."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
    return None
