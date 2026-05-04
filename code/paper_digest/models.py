from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Paper:
    source: str
    paper_id: str
    title: str
    summary: str
    url: str
    published_at: datetime | None = None
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    venue: str | None = None
    code_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stable_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"
        return f"{self.source}:{self.paper_id}"


@dataclass(slots=True)
class RankedPaper:
    paper: Paper
    score: int
    reason: str
    tags: list[str]
    llm_summary: str | None = None
