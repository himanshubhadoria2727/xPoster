from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .issue import update_posted_id


COMMAND_RE = re.compile(r"^\s*/post(?:\s+(all|[0-9][0-9\s,]*))\s*$", re.IGNORECASE)


class Publisher(Protocol):
    def post_draft(self, draft: dict) -> list[str]:
        ...


@dataclass(frozen=True)
class ApprovalResult:
    posted: list[tuple[int, list[str]]]
    skipped: list[int]
    requested: list[int]
    message: str


def parse_post_command(command: str, available_ids: list[int]) -> list[int]:
    match = COMMAND_RE.match(command)
    if not match:
        raise ValueError("Command must be `/post all` or `/post 1 3 5`.")

    selection = match.group(1).lower()
    if selection == "all":
        return list(available_ids)

    requested = [int(item) for item in re.findall(r"\d+", selection)]
    if not requested:
        raise ValueError("No draft IDs were provided.")

    invalid = sorted(set(requested) - set(available_ids))
    if invalid:
        raise ValueError(f"Unknown draft ID(s): {', '.join(str(item) for item in invalid)}")

    deduped: list[int] = []
    for item in requested:
        if item not in deduped:
            deduped.append(item)
    return deduped


def post_selected(state: dict, command: str, publisher: Publisher) -> ApprovalResult:
    drafts = state.get("drafts", [])
    available_ids = [int(draft["id"]) for draft in drafts]
    requested = parse_post_command(command, available_ids)

    posted: list[tuple[int, list[str]]] = []
    skipped: list[int] = []
    by_id = {int(draft["id"]): draft for draft in drafts}

    for draft_id in requested:
        draft = by_id[draft_id]
        if draft.get("posted_id"):
            skipped.append(draft_id)
            continue

        posted_ids = publisher.post_draft(draft)
        update_posted_id(state, draft_id, posted_ids)
        posted.append((draft_id, posted_ids))

    return ApprovalResult(
        posted=posted,
        skipped=skipped,
        requested=requested,
        message=format_result_message(posted, skipped),
    )


def format_result_message(posted: list[tuple[int, list[str]]], skipped: list[int]) -> str:
    lines = ["X poster result:"]
    if posted:
        for draft_id, posted_ids in posted:
            urls = ", ".join(f"https://x.com/i/web/status/{posted_id}" for posted_id in posted_ids)
            lines.append(f"- Posted draft {draft_id}: {urls}")
    if skipped:
        lines.append(f"- Skipped already posted draft(s): {', '.join(str(item) for item in skipped)}")
    if not posted and not skipped:
        lines.append("- No drafts were posted.")
    return "\n".join(lines)
