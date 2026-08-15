"""Tracked SQL migrations for the Trace production runtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from trace_memory.persistence import CockroachDatabase


@dataclass(frozen=True)
class MigrationRunner:
    database: CockroachDatabase
    directory: Path

    def apply(self) -> list[str]:
        files = sorted(self.directory.glob("[0-9][0-9][0-9]_*.sql"))
        if not files:
            raise ValueError(f"no migrations found in {self.directory}")

        def migrate(connection: Connection) -> list[str]:
            connection.execute(text("""CREATE TABLE IF NOT EXISTS schema_migrations (
                version STRING PRIMARY KEY, checksum STRING NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )"""))
            applied = {row.version: row.checksum for row in connection.execute(
                text("SELECT version, checksum FROM schema_migrations")
            )}
            completed: list[str] = []
            for path in files:
                version = path.name.split("_", 1)[0]
                sql = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise RuntimeError(f"applied migration {version} checksum changed")
                    continue
                for statement in _sql_statements(sql):
                    connection.exec_driver_sql(statement)
                connection.execute(text(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (:version, :checksum)"
                ), {"version": version, "checksum": checksum})
                completed.append(version)
            return completed
        return self.database.transaction(migrate)


def _sql_statements(sql: str) -> list[str]:
    """Split repository DDL files; quoted semicolons are intentionally unsupported."""
    stripped = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in stripped.split(";") if statement.strip()]
