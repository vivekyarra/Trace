"""Trace production process entry points."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from trace_memory.console import DatabaseConsoleSource, serve_console
from trace_memory.migration import MigrationRunner
from trace_memory.observability import Metrics
from trace_memory.persistence import CockroachDatabase, MemoryRepository, RuntimeRepository
from trace_memory.runtime import OutboxWorker, SqsPublisher, SqsTaskWorker
from trace_memory.runtime.automation import GitHubAutomation
from trace_memory.runtime.github import (
    GitHubAppTokenProvider,
    GitHubClient,
    GitHubWebhookRuntime,
)
from trace_memory.security import RuntimeSettings, validate_database_url
from trace_memory.server import RuntimeServer


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="trace-runtime", description="Trace institutional-memory runtime")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply tracked CockroachDB migrations")
    for name in ("webhook", "console"):
        command = commands.add_parser(name)
        command.add_argument("--host", default="127.0.0.1")
        command.add_argument("--port", type=int, default=8000 if name == "webhook" else 8080)
    for name in ("outbox-worker", "task-worker"):
        command = commands.add_parser(name)
        command.add_argument("--once", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    validate_database_url(database_url)
    database = CockroachDatabase.from_url(database_url)
    organization_id = _uuid_env("TRACE_ORGANIZATION_ID")
    repository_id = _uuid_env("TRACE_REPOSITORY_ID")

    if args.command == "migrate":
        applied = MigrationRunner(database, _migrations_directory()).apply()
        print("applied: " + (", ".join(applied) if applied else "none"))
        return 0
    if args.command == "console":
        serve_console(DatabaseConsoleSource(database), host=args.host, port=args.port)
        return 0

    settings = RuntimeSettings.from_env()
    import boto3
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    store = RuntimeRepository(database)
    if args.command == "outbox-worker":
        worker = OutboxWorker(store, SqsPublisher(sqs, settings.sqs_queue_url))
        return _worker_loop(lambda: worker.run_once(), args.once)
    if args.command == "webhook":
        webhook = GitHubWebhookRuntime(
            settings.github_webhook_secret, organization_id, repository_id,
            settings.github_repository, store)
        RuntimeServer(webhook, Metrics()).serve(host=args.host, port=args.port)
        return 0
    if args.command == "task-worker":
        from trace_memory.agents import Guardkeeper
        from trace_memory.ai import BedrockEmbedder, BedrockReasoner
        memories = MemoryRepository(database)
        reasoner = BedrockReasoner()
        github_token = settings.github_token or GitHubAppTokenProvider(
            settings.github_app_id,
            settings.github_app_installation_id,
            settings.github_app_private_key,
        )
        automation = GitHubAutomation(
            github=GitHubClient(github_token, settings.github_repository),
            reasoner=reasoner, embedder=BedrockEmbedder(),
            guardkeeper=Guardkeeper(memories, reasoner=reasoner), memories=memories,
            organization_id=organization_id, repository_id=repository_id, effects=store,
        )
        worker = SqsTaskWorker(sqs, settings.sqs_queue_url, store, automation)
        return _worker_loop(lambda: worker.run_once(), args.once)
    raise AssertionError("unhandled command")


def _worker_loop(run_once: Callable[[], int], once: bool) -> int:
    while True:
        run_once()
        if once:
            return 0
        time.sleep(1)


def _uuid_env(name: str) -> UUID:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required")
    try:
        return UUID(value)
    except ValueError as error:
        raise SystemExit(f"{name} must be a UUID") from error


def _migrations_directory() -> Path:
    candidates = [
        Path(os.environ["TRACE_MIGRATIONS_DIR"]) if os.environ.get("TRACE_MIGRATIONS_DIR") else None,
        Path("migrations"),
        Path(sys.prefix) / "share" / "trace" / "migrations",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "001_canonical_memory.sql").is_file():
            return candidate
    raise SystemExit("Trace migrations were not found; set TRACE_MIGRATIONS_DIR")


if __name__ == "__main__":
    raise SystemExit(main())
