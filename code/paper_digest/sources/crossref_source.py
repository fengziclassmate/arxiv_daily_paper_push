from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from html import unescape
from json import JSONDecodeError
from typing import Any

import requests

from ..models import Paper

CROSSREF_URL = "https://api.crossref.org/journals/{issn}/works"
CROSSREF_HEADERS = {
    "User-Agent": "arxiv-daily-paper-push/1.0 (mailto:2537118325@qq.com)",
}
ELSEVIER_ARTICLE_URL = "https://api.elsevier.com/content/article/doi/{doi}"
OPENALEX_WORK_URL = "https://api.openalex.org/works/https://doi.org/{doi}"
SEMANTIC_SCHOLAR_WORK_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
NON_RESEARCH_TITLE_PATTERNS = (
    "editorial board",
    "corrigendum",
    "erratum",
    "correction",
    "retraction",
)
ELSEVIER_JOURNAL_SHORT_NAMES = {
    "Applied Geography",
    "Applied Soft Computing",
    "Artificial Intelligence",
    "CEUS",
    "Cities",
    "Computer Science Review",
    "EIAR",
    "Information Fusion",
    "ISPRS JPRS",
    "JAG",
    "Landscape and Urban Planning",
    "Pattern Recognition",
    "RSE",
    "SCS",
    "Science Bulletin",
    "Urban Climate",
}


def _clean_abstract(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(unescape(text).split())


def _first(items: list[Any] | None) -> Any:
    return items[0] if items else None


def _is_non_research_item(title: str) -> bool:
    title_lower = title.lower().strip()
    return any(pattern in title_lower for pattern in NON_RESEARCH_TITLE_PATTERNS)


def _date_from_parts(parts: list[list[int]] | None) -> datetime | None:
    first = _first(parts)
    if not first:
        return None
    year = first[0]
    month = first[1] if len(first) > 1 else 1
    day = first[2] if len(first) > 2 else 1
    return datetime(year, month, day, tzinfo=timezone.utc)


def _date_text_from_parts(parts: list[list[int]] | None) -> str:
    first = _first(parts)
    if not first:
        return ""
    if len(first) >= 3:
        return f"{first[0]:04d}-{first[1]:02d}-{first[2]:02d}"
    if len(first) == 2:
        return f"{first[0]:04d}-{first[1]:02d}"
    return f"{first[0]:04d}"


def _date_text(item: dict, field: str) -> str:
    value = item.get(field)
    if not isinstance(value, dict):
        return ""
    return _date_text_from_parts(value.get("date-parts"))


def _find_abstract(value: Any) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = key.lower()
            if "abstract" in key_lower or key_lower in {"dc:description", "description"}:
                if isinstance(item, str):
                    cleaned = _clean_abstract(item)
                    if cleaned:
                        return cleaned
            found = _find_abstract(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_abstract(item)
            if found:
                return found
    return ""


def _abstract_from_openalex_index(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))
    return " ".join(word for _, word in sorted(words))


def _extract_taylor_abstract_from_html(html: str) -> str:
    patterns = (
        r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']dc\.Description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        r'"description"\s*:\s*"(.*?)"',
        r'<section[^>]+class=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</section>',
        r'<div[^>]+class=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</div>',
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            cleaned = _clean_abstract(match.group(1))
            if cleaned:
                return cleaned
    return ""


def _supplement_abstract_from_elsevier(doi: str | None) -> str:
    if not doi:
        return ""
    api_key = os.getenv("ELSEVIER_API_KEY")
    if not api_key:
        return ""
    try:
        response = requests.get(
            ELSEVIER_ARTICLE_URL.format(doi=doi),
            headers={"Accept": "application/json", "X-ELS-APIKey": api_key},
            params={"view": "META_ABS"},
            timeout=20,
        )
        response.raise_for_status()
        return _find_abstract(response.json())
    except requests.RequestException as exc:
        print(f"[WARN] Elsevier abstract supplement failed for {doi}: {exc}")
        return ""


def _supplement_abstract_from_openalex(doi: str | None) -> str:
    if not doi:
        return ""
    try:
        response = requests.get(OPENALEX_WORK_URL.format(doi=doi), timeout=20)
        response.raise_for_status()
        data = response.json()
        return _abstract_from_openalex_index(data.get("abstract_inverted_index"))
    except (requests.RequestException, JSONDecodeError) as exc:
        print(f"[WARN] OpenAlex abstract supplement failed for {doi}: {exc}")
        return ""


def _supplement_abstract_from_semantic_scholar(doi: str | None) -> str:
    if not doi:
        return ""
    try:
        response = requests.get(
            SEMANTIC_SCHOLAR_WORK_URL.format(doi=doi),
            params={"fields": "abstract"},
            timeout=20,
        )
        response.raise_for_status()
        return _clean_abstract(response.json().get("abstract"))
    except (requests.RequestException, JSONDecodeError) as exc:
        print(f"[WARN] Semantic Scholar abstract supplement failed for {doi}: {exc}")
        return ""


def _supplement_abstract_from_taylor_page(url: str | None) -> str:
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=25,
        )
        if response.status_code == 403:
            return ""
        response.raise_for_status()
        return _extract_taylor_abstract_from_html(response.text)
    except requests.RequestException as exc:
        print(f"[WARN] Taylor & Francis page abstract supplement failed for {url}: {exc}")
        return ""


def _supplement_abstract_for_journal(short_name: str | None, doi: str | None, url: str | None) -> str:
    if short_name in ELSEVIER_JOURNAL_SHORT_NAMES:
        return _supplement_abstract_from_elsevier(doi)
    if short_name == "IJGIS":
        for supplement in (
            _supplement_abstract_from_openalex(doi),
            _supplement_abstract_from_semantic_scholar(doi),
            _supplement_abstract_from_taylor_page(url),
        ):
            if supplement:
                return supplement
    return ""


def supplement_missing_abstracts(papers: list[Paper]) -> None:
    for paper in papers:
        if paper.summary.strip():
            continue
        paper.summary = _supplement_abstract_for_journal(paper.source, paper.doi, paper.url)


def _fetch_crossref_items(issn: str, params: dict[str, str | int], short_name: str) -> list[dict[str, Any]]:
    for attempt in range(3):
        try:
            response = requests.get(
                CROSSREF_URL.format(issn=issn),
                headers=CROSSREF_HEADERS,
                params=params,
                timeout=20,
            )
            if response.status_code == 429 and attempt < 2:
                wait_seconds = 5 * (attempt + 1)
                print(f"[WARN] Crossref source {short_name} rate limited; retrying in {wait_seconds}s.")
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return response.json().get("message", {}).get("items", [])
        except requests.RequestException as exc:
            if attempt < 2:
                wait_seconds = 3 * (attempt + 1)
                print(f"[WARN] Crossref source {short_name} request failed; retrying in {wait_seconds}s: {exc}")
                time.sleep(wait_seconds)
                continue
            print(f"[WARN] Crossref source {short_name} failed: {exc}")
            return []
        except JSONDecodeError as exc:
            print(f"[WARN] Crossref source {short_name} returned invalid JSON: {exc}")
            return []
    return []


def _fetch_one_journal(journal: dict, from_day: date, today: date, include_future: bool) -> list[Paper]:
    if not journal.get("enabled", True):
        return []
    issn = journal["issn"]
    short_name = journal.get("short_name", issn)
    params = {
        "filter": f"from-pub-date:{from_day.isoformat()},type:journal-article",
        "sort": "published",
        "order": "desc",
        "rows": 20,
        "select": "DOI,title,abstract,author,published-print,published-online,published,accepted,created,deposited,issued,container-title,URL",
    }
    items = _fetch_crossref_items(issn, params, short_name)

    papers: list[Paper] = []
    for item in items:
        title = _first(item.get("title")) or ""
        if not title:
            continue
        if _is_non_research_item(title):
            continue
        doi = item.get("DOI")
        published_at = (
            _date_from_parts(item.get("published-online", {}).get("date-parts"))
            or _date_from_parts(item.get("published-print", {}).get("date-parts"))
            or _date_from_parts(item.get("published", {}).get("date-parts"))
        )
        if published_at:
            published_day = published_at.date()
            if published_day < from_day:
                continue
            if not include_future and published_day > today:
                continue
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        summary = _clean_abstract(item.get("abstract"))
        authors = [
            " ".join(part for part in [author.get("given"), author.get("family")] if part)
            for author in item.get("author", [])
        ]
        papers.append(
            Paper(
                source=journal.get("short_name", issn),
                paper_id=doi or item.get("URL", title),
                title=title.strip(),
                summary=summary,
                url=url,
                published_at=published_at,
                authors=[author for author in authors if author],
                doi=doi,
                venue=journal.get("name"),
                metadata={
                    "published_online": _date_text(item, "published-online"),
                    "published_print": _date_text(item, "published-print"),
                    "published": _date_text(item, "published"),
                    "accepted": _date_text(item, "accepted"),
                    "created": _date_text(item, "created"),
                    "deposited": _date_text(item, "deposited"),
                    "issued": _date_text(item, "issued"),
                },
            )
        )
    return papers


def fetch(config: dict) -> list[Paper]:
    source_config = config.get("sources", {})
    journals = source_config.get("journals", [])
    lookback_days = int(config.get("lookback_days", 7))
    include_future = bool(config.get("include_future_published", True))
    today = date.today()
    from_day = today - timedelta(days=lookback_days)
    papers: list[Paper] = []

    workers = max(1, int(config.get("journal_fetch_workers", 6)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_one_journal, journal, from_day, today, include_future) for journal in journals]
        for future in as_completed(futures):
            papers.extend(future.result())

    return papers
