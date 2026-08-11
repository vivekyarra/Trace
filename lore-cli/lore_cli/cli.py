"""Main CLI entry point for LORE.

Usage:
    lore sync   --project-id 123
    lore validate --from-file memories.txt
    lore stats  --from-file memories.txt
"""

from __future__ import annotations

import argparse
import os
import sys

from lore_cli import __version__


def _env(name: str, default: str | None = None) -> str | None:
    """Read a value from the environment with an optional default."""
    return os.environ.get(name, default)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser and subcommands."""
    parser = argparse.ArgumentParser(
        prog="lore",
        description="LORE CLI — sync, validate, and report on architectural decision memories.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"lore-cli {__version__}",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help="GitLab project ID (env: LORE_PROJECT_ID)",
    )
    parser.add_argument(
        "--gitlab-url",
        default=None,
        help="GitLab instance URL (env: GITLAB_URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitLab private token (env: GITLAB_TOKEN)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── sync ────────────────────────────────────────────────────────────
    subparsers.add_parser(
        "sync",
        help="Read memories from the LORE Memory Bank issue and write wiki pages",
    )

    # ── validate ────────────────────────────────────────────────────────
    validate_parser = subparsers.add_parser(
        "validate",
        help="Check memory format and dependency integrity",
    )
    validate_parser.add_argument(
        "--from-file",
        metavar="PATH",
        default=None,
        help="Read memories from a local file instead of the GitLab API",
    )

    # ── stats ───────────────────────────────────────────────────────────
    stats_parser = subparsers.add_parser(
        "stats",
        help="Output JSON statistics about the memory bank",
    )
    stats_parser.add_argument(
        "--from-file",
        metavar="PATH",
        default=None,
        help="Read memories from a local file instead of the GitLab API",
    )

    # ── dashboard ────────────────────────────────────────────────────────
    dash_parser = subparsers.add_parser(
        "dashboard",
        help="Generate a self-contained HTML dashboard for GitLab Pages",
    )
    dash_parser.add_argument(
        "--from-file",
        metavar="PATH",
        default=None,
        help="Read memories from a local file instead of the GitLab API",
    )
    dash_parser.add_argument(
        "--output",
        metavar="DIR",
        default="public",
        help="Output directory (default: public/)",
    )

    return parser


def _resolve_gitlab_args(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in GitLab connection details from environment variables when not
    provided on the command line."""
    if args.project_id is None:
        env_val = _env("LORE_PROJECT_ID")
        if env_val is not None:
            args.project_id = int(env_val)
    if args.gitlab_url is None:
        args.gitlab_url = _env("GITLAB_URL", "https://gitlab.com")
    if args.token is None:
        args.token = _env("GITLAB_TOKEN")
    return args


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns an integer exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    args = _resolve_gitlab_args(args)

    # ── dispatch ────────────────────────────────────────────────────────
    if args.command == "sync":
        from lore_cli.sync import run_sync

        return run_sync(args)

    if args.command == "validate":
        from lore_cli.validate import run_validate

        return run_validate(args)

    if args.command == "stats":
        from lore_cli.stats import run_stats

        return run_stats(args)

    if args.command == "dashboard":
        from lore_cli.dashboard import generate_dashboard
        from lore_cli.sync import load_entries_from_file

        if args.from_file:
            memories, patterns = load_entries_from_file(args.from_file)
        elif args.project_id and args.token:
            from lore_cli.sync import (
                _collect_comments,
                _find_memory_bank_issue,
                _get_gitlab,
                parse_all_entries,
            )

            _gl, project = _get_gitlab(args)
            issue = _find_memory_bank_issue(project)
            if issue is None:
                print(
                    "ERROR: Could not find the LORE Memory Bank issue.",
                    file=sys.stderr,
                )
                return 1
            raw_text = _collect_comments(issue)
            memories, patterns = parse_all_entries(raw_text)
        else:
            print(
                "ERROR: Provide --from-file or --project-id and --token.",
                file=sys.stderr,
            )
            return 1

        import os

        output_path = os.path.join(args.output, "index.html")
        result = generate_dashboard(memories, patterns, output_path=output_path)
        print(f"Dashboard generated: {result}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
