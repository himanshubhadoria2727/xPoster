from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from .config import PosterConfig, TopicConfig


@dataclass(frozen=True)
class Draft:
    id: int
    topic: str
    parts: list[str] | str
    image_prompt: str | None = None
    image_path: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.parts, str):
            object.__setattr__(self, "parts", [self.parts])

    @property
    def text(self) -> str:
        return self.parts[0]


def generate_drafts(
    config: PosterConfig,
    date: dt.date | None = None,
    count: int | None = None,
    mode: str = "mixed",
) -> list[Draft]:
    if not config.topics:
        raise ValueError("At least one topic is required.")

    if mode not in {"posts", "threads", "mixed"}:
        raise ValueError("mode must be one of: posts, threads, mixed.")

    day = date or dt.date.today()
    rng = random.Random(day.isoformat())
    draft_count = count or config.daily_count
    topics = _select_topics(config.topics, draft_count, rng)
    drafts: list[Draft] = []
    seen_texts: set[str] = set()

    for topic in topics:
        draft = _build_valid_draft(topic, config, rng, len(drafts) + 1, seen_texts, mode)
        drafts.append(draft)
        seen_texts.add(_normalize(" ".join(draft.parts)))

    return drafts


def _select_topics(topics: list[TopicConfig], count: int, rng: random.Random) -> list[TopicConfig]:
    if count < 1:
        raise ValueError("daily_count must be at least 1.")

    shuffled = list(topics)
    rng.shuffle(shuffled)
    selected: list[TopicConfig] = []
    while len(selected) < count:
        selected.extend(shuffled)
    return selected[:count]


def _build_valid_draft(
    topic: TopicConfig,
    config: PosterConfig,
    rng: random.Random,
    draft_id: int,
    seen_texts: set[str],
    mode: str,
) -> Draft:
    candidates = _candidate_parts(topic, rng, mode)

    rng.shuffle(candidates)
    errors: list[str] = []
    for parts in candidates:
        try:
            for text in parts:
                validate_text(text, config.max_post_length, config.blocked_words)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        normalized = _normalize(" ".join(parts))
        if normalized not in seen_texts:
            image_prompt = _pick_optional(topic.image_prompts, rng)
            image_path = _pick_optional(topic.image_paths, rng)
            return Draft(
                id=draft_id,
                topic=topic.name,
                parts=parts,
                image_prompt=image_prompt,
                image_path=image_path,
            )

    detail = f" Last validation error: {errors[-1]}" if errors else ""
    raise ValueError(f"No valid unique draft could be generated for topic '{topic.name}'.{detail}")


def _candidate_parts(topic: TopicConfig, rng: random.Random, mode: str) -> list[list[str]]:
    candidates: list[list[str]] = []
    include_posts = mode in {"posts", "mixed"}
    include_threads = mode in {"threads", "mixed"}

    if include_posts:
        for template in topic.templates:
            for angle in topic.angles:
                for hashtag in topic.hashtags:
                    candidates.append([
                        template.format(topic=topic.name, angle=angle, hashtag=hashtag).strip()
                    ])

    if include_threads:
        for thread_template in topic.thread_templates:
            for angle in topic.angles:
                for hashtag in topic.hashtags:
                    parts = [
                        part.format(topic=topic.name, angle=angle, hashtag=hashtag).strip()
                        for part in thread_template
                    ]
                    candidates.append(parts)

    if mode == "threads" and not candidates:
        raise ValueError(f"Topic '{topic.name}' does not define thread_templates.")
    rng.shuffle(candidates)
    return candidates


def validate_text(text: str, max_length: int, blocked_words: list[str]) -> None:
    if not text:
        raise ValueError("Draft text cannot be empty.")
    if len(text) > max_length:
        raise ValueError(f"Draft is {len(text)} characters; limit is {max_length}.")

    lowered = text.lower()
    blocked = [word for word in blocked_words if word and word in lowered]
    if blocked:
        raise ValueError(f"Draft contains blocked word(s): {', '.join(blocked)}")


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _pick_optional(values: list[str], rng: random.Random) -> str | None:
    cleaned = [value for value in values if value]
    if not cleaned:
        return None
    return rng.choice(cleaned)
