"""Tracked SQL migrations and idempotent legacy Trace memory import."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from trace_memory.domain import ActorType, Memory, MemoryStatus, MemoryType
from trace_memory.persistence import CockroachDatabase


class MemorySink(Protocol):
    def create(self, memory: Memory) -> bool | None: ...


class ImportRecorder(Protocol):
    def record(self, *, source_name: str, source_checksum: str, imported: int, skipped: int) -> None: ...


class MemoryEmbedder(Protocol):
    def embed(self, text: str) -> object: ...


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


_FIELD = re.compile(r"^([A-Za-z][A-Za-z ]+):\s*(.*)$")
_ID = re.compile(r"(?:Trace Memory|TRACE-MEMORY-)\s*#?([0-9]+)", re.I)


@dataclass(frozen=True)
class ImportReport:
    imported: int
    skipped: int
    errors: tuple[str, ...]


@dataclass
class LegacyMemoryImporter:
    sink: MemorySink
    organization_id: UUID
    repository_id: UUID
    recorder: ImportRecorder | None = None
    embedder: MemoryEmbedder | None = None

    def import_text(self, content: str, *, strict: bool = True,
                    source_name: str = "legacy-memory") -> ImportReport:
        blocks = re.split(r"(?=^Trace Memory\s+#?[0-9]+)", content, flags=re.M | re.I)
        parsed: list[Memory] = []
        errors: list[str] = []
        for block in blocks:
            if not _ID.search(block):
                continue
            try:
                parsed.append(self._parse(block))
            except Exception as error:
                errors.append(str(error))
        if strict and errors:
            raise ValueError(f"legacy import failed before writes: {errors[0]}")
        imported = 0
        skipped = len(errors)
        for memory in parsed:
            if memory.status is MemoryStatus.ACTIVE and self.embedder is not None:
                result = self.embedder.embed(
                    f"{memory.decision}\n{memory.rationale}\n{memory.future_implication}"
                )
                memory = memory.model_copy(update={
                    "embedding": getattr(result, "values"),
                    "embedding_model": getattr(result, "model_id"),
                    "embedding_version": getattr(result, "version"),
                    "embedded_at": getattr(result, "embedded_at"),
                })
            created = self.sink.create(memory)
            if created is False:
                skipped += 1
            else:
                imported += 1
        checksum = hashlib.sha256(content.encode()).hexdigest()
        if self.recorder:
            self.recorder.record(source_name=source_name, source_checksum=checksum,
                                 imported=imported, skipped=skipped)
        return ImportReport(imported, skipped, tuple(errors))

    def _parse(self, block: str) -> Memory:
        match = _ID.search(block)
        assert match is not None
        fields: dict[str, str] = {}
        for line in block.splitlines():
            field = _FIELD.match(line.strip())
            if field:
                fields[field.group(1).casefold()] = field.group(2).strip()
        required = ["decision", "reason", "future implication", "confidence"]
        missing = [field for field in required if not fields.get(field)]
        if missing:
            raise ValueError(f"memory {match.group(1)} missing fields: {', '.join(missing)}")
        decision = fields["decision"]
        source = fields.get("source mr", "Legacy Trace import")
        raw_status = fields.get("status", "Active").upper()
        status = {"ACTIVE": MemoryStatus.ACTIVE, "DRAFT": MemoryStatus.DRAFT}.get(raw_status, MemoryStatus.DEPRECATED)
        confidence = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.4}.get(fields["confidence"].upper())
        if confidence is None:
            confidence = float(fields["confidence"])
        content_hash = hashlib.sha256(block.strip().encode()).hexdigest()
        semantic_key = hashlib.sha256(decision.casefold().encode()).hexdigest()
        return Memory(
            organization_id=self.organization_id, repository_id=self.repository_id,
            display_id=f"TRACE-MEMORY-{int(match.group(1)):03d}",
            memory_type=_memory_type(fields), title=source[:300], decision=decision,
            rationale=fields["reason"], rejected_alternative=_nullable(fields.get("rejected")),
            future_implication=fields["future implication"], status=status, confidence=confidence,
            confidence_basis=f"Imported legacy confidence: {fields['confidence']}",
            security_relevant=fields.get("security relevant", "no").casefold() in {"yes", "true"},
            content_hash=content_hash, semantic_key=semantic_key,
            created_by_actor_type=ActorType.SYSTEM, created_by_actor_id="trace-importer",
        )


def _nullable(value: str | None) -> str | None:
    return None if not value or value.casefold() in {"n/a", "none"} else value


def _memory_type(fields: dict[str, str]) -> MemoryType:
    if fields.get("security relevant", "no").casefold() in {"yes", "true"}:
        return MemoryType.SECURITY_CONSTRAINT
    if fields.get("incident type", "none").casefold() != "none":
        return MemoryType.INCIDENT_LESSON
    return MemoryType.ARCHITECTURAL_DECISION
