from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Paper


class PaperStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pushed_papers (
                stable_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                doi TEXT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER,
                pushed_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def import_legacy_history(self, history_path: Path) -> int:
        if not history_path.exists():
            return 0
        imported = 0
        now = datetime.now(timezone.utc).isoformat()
        with history_path.open("r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if not url:
                    continue
                paper_id = url.rstrip("/").split("/")[-1]
                stable_key = f"arxiv:{paper_id}"
                cur = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO pushed_papers
                    (stable_key, source, paper_id, doi, title, url, score, pushed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (stable_key, "arxiv", paper_id, None, paper_id, url, None, now),
                )
                imported += cur.rowcount
        self.conn.commit()
        return imported

    def has_seen(self, paper: Paper) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM pushed_papers WHERE stable_key = ? LIMIT 1",
            (paper.stable_key,),
        )
        return cur.fetchone() is not None

    def mark_pushed(self, paper: Paper, score: int | None = None) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO pushed_papers
            (stable_key, source, paper_id, doi, title, url, score, pushed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper.stable_key,
                paper.source,
                paper.paper_id,
                paper.doi,
                paper.title,
                paper.url,
                score,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
