from __future__ import annotations

import difflib

from .models import Paper


def deduplicate(papers: list[Paper]) -> list[Paper]:
    seen_keys: set[str] = set()
    seen_titles: list[str] = []
    unique: list[Paper] = []

    for paper in papers:
        if paper.stable_key in seen_keys:
            continue
        title_key = " ".join(paper.title.lower().split())
        if any(difflib.SequenceMatcher(None, title_key, old).ratio() > 0.94 for old in seen_titles):
            continue
        seen_keys.add(paper.stable_key)
        seen_titles.append(title_key)
        unique.append(paper)

    return unique
