from trace_memory.cli import _migrations_directory, parser
from trace_memory.runtime.automation import _promises


def test_all_production_processes_are_exposed() -> None:
    for command in ("migrate", "import", "webhook", "console", "outbox-worker", "task-worker"):
        arguments = [command]
        if command == "import":
            arguments.append("memory.txt")
        assert parser().parse_args(arguments).command == command


def test_promise_extraction_is_bounded_and_specific() -> None:
    promises = _promises("We will validate tokens\nNothing\n- Must use TLS")
    assert promises == ["We will validate tokens", "Must use TLS"]


def test_repository_migrations_are_discoverable() -> None:
    assert (_migrations_directory() / "002_runtime_operations.sql").is_file()
