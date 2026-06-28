from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .approval import post_selected
from .config import DEFAULT_CONFIG_PATH, load_config
from .drafts import generate_drafts
from .issue import make_state, parse_issue_body, render_issue_body
from .x_api import DryRunPublisher, publisher_from_env


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="xposter")
    subparsers = parser.add_subparsers(dest="action", required=True)

    generate = subparsers.add_parser("generate-drafts", help="Generate a daily GitHub Issue body.")
    generate.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    generate.add_argument("--date", help="Date in YYYY-MM-DD format. Defaults to today.")
    generate.add_argument("--count", type=int, help="Number of drafts to generate.")
    generate.add_argument(
        "--mode",
        choices=["posts", "threads", "mixed"],
        default="mixed",
        help="Generate single posts, threads, or a mix.",
    )
    generate.add_argument("--output", help="Write issue body to this file instead of stdout.")

    post = subparsers.add_parser("post-approved", help="Post approved drafts from an issue body.")
    post.add_argument("--issue-body-file", required=True)
    post.add_argument("--command", required=True)
    post.add_argument("--updated-body-file", help="Write the updated issue body to this file.")
    post.add_argument("--result-file", help="Write a GitHub comment result message to this file.")
    post.add_argument("--dry-run", action="store_true", help="Do not call the X API.")

    args = parser.parse_args(argv)
    if args.action == "generate-drafts":
        _generate(args)
    elif args.action == "post-approved":
        _post(args)


def _generate(args: argparse.Namespace) -> None:
    day = _parse_date(args.date) if args.date else dt.date.today()
    config = load_config(args.config)
    drafts = generate_drafts(config, day, count=args.count, mode=args.mode)
    body = render_issue_body(make_state(day, drafts))
    _write_or_print(body, args.output)


def _post(args: argparse.Namespace) -> None:
    state = None

    try:
        issue_body = Path(args.issue_body_file).read_text(encoding="utf-8")
        state = parse_issue_body(issue_body)
        publisher = DryRunPublisher() if args.dry_run else publisher_from_env()
        result = post_selected(state, args.command, publisher)
        exit_code = 0
        message = result.message
    except Exception as exc:
        exit_code = 1
        message = f"X poster failed: {exc}"

    if state is not None and args.updated_body_file:
        updated_body = render_issue_body(state)
        Path(args.updated_body_file).write_text(updated_body, encoding="utf-8")
    if args.result_file:
        Path(args.result_file).write_text(message + "\n", encoding="utf-8")
    else:
        print(message)

    if exit_code:
        raise SystemExit(exit_code)


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def _write_or_print(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
