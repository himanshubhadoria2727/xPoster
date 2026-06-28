from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config/tweet_config.json")


@dataclass(frozen=True)
class TopicConfig:
    name: str
    hashtags: list[str]
    angles: list[str]
    templates: list[str]
    thread_templates: list[list[str]]
    image_prompts: list[str]
    image_paths: list[str]


@dataclass(frozen=True)
class PosterConfig:
    daily_count: int
    max_post_length: int
    blocked_words: list[str]
    topics: list[TopicConfig]


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> PosterConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    topics = [
        TopicConfig(
            name=item["name"],
            hashtags=list(item["hashtags"]),
            angles=list(item["angles"]),
            templates=list(item["templates"]),
            thread_templates=[list(parts) for parts in item.get("thread_templates", [])],
            image_prompts=list(item.get("image_prompts", [])),
            image_paths=list(item.get("image_paths", [])),
        )
        for item in raw["topics"]
    ]
    return PosterConfig(
        daily_count=int(raw.get("daily_count", 5)),
        max_post_length=int(raw.get("max_post_length", 280)),
        blocked_words=[str(word).lower() for word in raw.get("blocked_words", [])],
        topics=topics,
    )
