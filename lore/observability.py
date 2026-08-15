"""Structured, secret-safe logs and dependency-free operational metrics."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock

from lore.security import redact


def log_event(logger: logging.Logger, event: str, **details: object) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **details}
    logger.info(json.dumps(redact(record), default=str, separators=(",", ":"), sort_keys=True))


@dataclass
class Metrics:
    """Thread-safe counters renderable in Prometheus text format."""

    _values: Counter[tuple[str, tuple[tuple[str, str], ...]]] = field(default_factory=Counter)
    _lock: Lock = field(default_factory=Lock)

    def increment(self, name: str, *, labels: dict[str, str] | None = None, amount: int = 1) -> None:
        if not name.startswith("lore_") or not name.replace("_", "").isalnum():
            raise ValueError("metric names must be lore_ prefixed identifiers")
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._values[key] += amount

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            items = sorted(self._values.items())
        for (name, labels), value in items:
            suffix = ""
            if labels:
                encoded = ",".join(f'{key}="{_escape_label(val)}"' for key, val in labels)
                suffix = "{" + encoded + "}"
            lines.append(f"{name}{suffix} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
