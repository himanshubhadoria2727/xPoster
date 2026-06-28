from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from .drafts import Draft


STATE_START = "<!-- xposter-state"
STATE_END = "-->"
STATE_RE = re.compile(r"<!-- xposter-state\s*(\{.*?\})\s*-->", re.DOTALL)


def make_issue_title(date: dt.date) -> str:
    return f"Daily X drafts {date.isoformat()}"


def make_state(date: dt.date, drafts: list[Draft]) -> dict[str, Any]:
    return {
        "date": date.isoformat(),
        "drafts": [
            {
                "id": draft.id,
                "topic": draft.topic,
                "text": draft.text,
                "parts": draft.parts,
                "image_prompt": draft.image_prompt,
                "image_path": draft.image_path,
                "posted_id": None,
                "posted_ids": [],
            }
            for draft in drafts
        ],
    }


def render_issue_body(state: dict[str, Any]) -> str:
    date = state["date"]
    state_json = json.dumps(state, indent=2, sort_keys=True)
    lines = [
        f"{STATE_START}",
        state_json,
        f"{STATE_END}",
        "",
        f"# Daily X Drafts - {date}",
        "",
        "Approve posts by commenting `/post all` or `/post 1 3 5`.",
        "",
        "Only unchecked drafts will be posted. Already posted drafts are skipped.",
        "",
        "## Drafts",
        "",
    ]

    for draft in state["drafts"]:
        checked = "x" if draft.get("posted_id") else " "
        parts = draft.get("parts") or [draft.get("text", "")]
        draft_type = "Thread" if len(parts) > 1 else "Post"
        lines.append(f"- [{checked}] {draft['id']}. {draft_type}")
        lines.append(f"  Topic: `{draft['topic']}`")
        if draft.get("image_path"):
            lines.append(f"  Image file: `{draft['image_path']}`")
        if draft.get("image_prompt"):
            lines.append(f"  Image prompt: {draft['image_prompt']}")
        for index, part in enumerate(parts, start=1):
            prefix = f"  {index}/{len(parts)}" if len(parts) > 1 else "  Text"
            lines.append(f"{prefix}: {part}")
        if draft.get("posted_id"):
            lines.append(f"  Posted: https://x.com/i/web/status/{draft['posted_id']}")
        elif draft.get("posted_ids"):
            lines.append(f"  Posted: https://x.com/i/web/status/{draft['posted_ids'][-1]}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_issue_body(body: str) -> dict[str, Any]:
    match = STATE_RE.search(body)
    if not match:
        raise ValueError("Issue body does not contain xposter state.")
    return json.loads(match.group(1))


def update_posted_id(state: dict[str, Any], draft_id: int, posted_id: str | list[str]) -> None:
    for draft in state["drafts"]:
        if int(draft["id"]) == int(draft_id):
            posted_ids = posted_id if isinstance(posted_id, list) else [posted_id]
            draft["posted_ids"] = posted_ids
            draft["posted_id"] = posted_ids[-1]
            return
    raise ValueError(f"Draft {draft_id} was not found.")
