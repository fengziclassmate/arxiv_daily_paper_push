from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests

from ..models import Paper

ARXIV_API_URL = "https://export.arxiv.org/api/query"
PWC_BASE_URL = "https://arxiv.paperswithcode.com/api/v0/papers/"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _build_query(config: dict) -> str:
    topics = config.get("topics", {})
    primary = topics.get("primary", [])
    methods = topics.get("methods", [])
    primary_query = " OR ".join(f'abs:"{term}"' if " " in term else f"abs:{term}" for term in primary)
    method_query = " OR ".join(f'abs:"{term}"' if " " in term else f"abs:{term}" for term in methods)
    return f"({primary_query}) AND ({method_query})"


def _text(parent: ElementTree.Element, tag: str) -> str:
    node = parent.find(tag)
    return (node.text or "").strip() if node is not None else ""


def _published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_code_link(arxiv_url: str) -> str | None:
    arxiv_id = arxiv_url.rstrip("/").split("/")[-1].split("v")[0]
    try:
        response = requests.get(f"{PWC_BASE_URL}{arxiv_id}", timeout=8)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None
    official = data.get("official")
    if isinstance(official, dict):
        return official.get("url")
    return None


def fetch(config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("arxiv", {})
    if not source_config.get("enabled", True):
        return []

    max_results = int(source_config.get("max_results", 30))
    fetch_code_links = bool(source_config.get("fetch_code_links", False))
    params = {
        "search_query": _build_query(config),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": min(max_results, 20),
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "arxiv-daily-paper-push/1.0"})
        if response.status_code == 429:
            print("[WARN] ArXiv source skipped: HTTP 429 rate limited. Try again later or run on a daily schedule.")
            return []
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[WARN] ArXiv source skipped: {exc}")
        return []

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        print(f"[WARN] ArXiv source skipped: invalid feed XML: {exc}")
        return []

    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        entry_id = _text(entry, f"{ATOM_NS}id")
        title = " ".join(_text(entry, f"{ATOM_NS}title").split())
        summary = " ".join(_text(entry, f"{ATOM_NS}summary").split())
        authors = [_text(author, f"{ATOM_NS}name") for author in entry.findall(f"{ATOM_NS}author")]
        doi = _text(entry, f"{ARXIV_NS}doi") or None
        primary_category = entry.find(f"{ARXIV_NS}primary_category")
        category = primary_category.attrib.get("term") if primary_category is not None else None
        published = _published(_text(entry, f"{ATOM_NS}published"))
        if published and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        papers.append(
            Paper(
                source="arxiv",
                paper_id=entry_id.rstrip("/").split("/")[-1],
                title=title,
                summary=summary,
                url=entry_id,
                published_at=published,
                authors=[author for author in authors if author],
                doi=doi,
                venue="arXiv",
                code_url=_get_code_link(entry_id) if fetch_code_links else None,
                metadata={"primary_category": category},
            )
        )
    return papers
