from __future__ import annotations

import re

from .models import Paper, RankedPaper


def keyword_score(paper: Paper, config: dict) -> RankedPaper:
    topics = config.get("topics", {})
    primary_terms = topics.get("primary", [])
    method_terms = topics.get("methods", [])
    haystack = f"{paper.title}\n{paper.summary}\n{paper.venue or ''}".lower()

    tags: list[str] = []
    score = 0
    primary_hits = 0
    method_hits = 0
    for term in primary_terms:
        if re.search(re.escape(term.lower()), haystack):
            score += 18
            primary_hits += 1
            tags.append(term)
    for term in method_terms:
        if re.search(re.escape(term.lower()), haystack):
            score += 12
            method_hits += 1
            tags.append(term)

    if primary_hits and method_hits:
        score += 20
    if paper.source == "arxiv":
        score += 5
    if paper.source in {"IJGIS", "CEUS"}:
        score += 8
    if paper.doi:
        score += 3

    score = min(score, 100)
    reason = "关键词命中：" + "、".join(tags[:6]) if tags else "未命中核心关键词"
    return RankedPaper(paper=paper, score=score, reason=reason, tags=tags[:8])
