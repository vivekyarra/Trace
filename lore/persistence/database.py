"""Small, explicit CockroachDB transaction layer with retry-safe semantics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import sleep
from typing import ParamSpec, TypeVar

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, OperationalError

P = ParamSpec("P")
T = TypeVar("T")


def is_retryable_serialization_error(error: BaseException) -> bool:
    """Recognise CockroachDB SQLSTATE 40001 without retrying arbitrary failures."""
    cursor: BaseException | None = error
    while cursor is not None:
        if getattr(cursor, "sqlstate", None) == "40001" or getattr(cursor, "pgcode", None) == "40001":
            return True
        if "restart transaction" in str(cursor).lower() or "sqlstate 40001" in str(cursor).lower():
            return True
        cursor = getattr(cursor, "__cause__", None) or getattr(cursor, "orig", None)
    return False


@dataclass(frozen=True)
class CockroachDatabase:
    engine: Engine
    max_transaction_attempts: int = 3

    @classmethod
    def from_url(cls, database_url: str, *, max_transaction_attempts: int = 3) -> CockroachDatabase:
        return cls(create_engine(database_url, pool_pre_ping=True), max_transaction_attempts)

    def transaction(self, work: Callable[[Connection], T]) -> T:
        """Run work in a serializable transaction, retrying only contention failures."""
        for attempt in range(1, self.max_transaction_attempts + 1):
            try:
                with self.engine.begin() as connection:
                    return work(connection)
            except (DBAPIError, OperationalError) as error:
                if not is_retryable_serialization_error(error) or attempt == self.max_transaction_attempts:
                    raise
                sleep(0.05 * attempt)
        raise RuntimeError("unreachable transaction retry state")
