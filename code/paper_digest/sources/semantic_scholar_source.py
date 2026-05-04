from __future__ import annotations

from datetime import datetime, timezone

import requests

from ..models import Paper

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def fetch(config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("semantic_scholar", {})
    if not source_config.get("enabled", False):
        return []

    topics = config.get("topics", {})
    query = " ".join(topics.get("primary", [])[:3] + topics.get("methods", [])[:3])
    fields = "title,abstract,url,authors,venue,year,publicationDate,externalIds"
    params = {
        "query": query,
        "limit": int(source_config.get("max_results", 20)),
        "fields": fields,
    }
    try:
        response = requests.get(SEARCH_URL, params=params, timeout=20)
        response.raise_for_status()
        items = response.json().get("data", [])
    except requests.RequestException as exc:
        print(f"[WARN] Semantic Scholar source failed: {exc}")
        return []

    venues = {v.lower() for v in source_config.get("venues", [])}
    papers: list[Paper] = []
    for item in items:
        venue = item.get("venue") or ""
        if venues and not any(v in venue.lower() for v in venues):
            continue
        external_ids = item.get("externalIds") or {}
        publication_date = item.get("publicationDate")
        published_at = None
        if publication_date:
            try:
                published_at = datetime.fromisoformat(publication_date).replace(tzinfo=timezone.utc)
            except ValueError:
                published_at = None
        papers.append(
            Paper(
                source="semantic_scholar",
                paper_id=item.get("paperId"),
                title=item.get("title", "").strip(),
                summary=item.get("abstract") or "",
                url=item.get("url") or "",
                published_at=published_at,
                authors=[author.get("name") for author in item.get("authors", []) if author.get("name")],
                doi=external_ids.get("DOI"),
                venue=venue,
                metadata={"external_ids": external_ids},
            )
        )
    return papers
