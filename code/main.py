from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from paper_digest.config import load_config, load_env_file, project_dir
from paper_digest.deduplicate import deduplicate
from paper_digest.llm import refine_relevance, summarize
from paper_digest.publishers import feishu, qq_mail, wechat_official
from paper_digest.render import plain_text_title, render_email_html, render_markdown, render_wechat_html, render_wechat_markdown
from paper_digest.scoring import keyword_score
from paper_digest.sources import arxiv_source, crossref_source, semantic_scholar_source
from paper_digest.storage import PaperStore


def collect_papers(config: dict):
    papers = []
    for fetcher in (arxiv_source.fetch, crossref_source.fetch, semantic_scholar_source.fetch):
        fetched = fetcher(config)
        print(f"[INFO] fetched {len(fetched)} papers from {fetcher.__module__.split('.')[-1]}")
        papers.extend(fetched)
    return deduplicate(papers)


def try_publish(name: str, publish_func, *args) -> bool:
    try:
        return bool(publish_func(*args))
    except Exception as exc:
        print(f"[WARN] {name} publish failed: {exc}")
        return False


def unique_report_path(output_dir: Path, report_date: datetime) -> Path:
    base_name = f"paper_digest_{report_date:%Y%m%d_%H%M%S}"
    candidate = output_dir / f"{base_name}.md"
    index = 1
    while candidate.exists():
        candidate = output_dir / f"{base_name}_{index}.md"
        index += 1
    return candidate


def wechat_title(report_date: datetime) -> str:
    return f"Paper Digest {report_date:%m-%d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish a daily paper digest.")
    parser.add_argument("--dry-run", action="store_true", help="write the report without publishing or marking papers as pushed")
    parser.add_argument("--skip-llm", action="store_true", help="skip DeepSeek relevance checks and summaries")
    parser.add_argument("--lookback-days", type=int, help="override config lookback_days for this run")
    parser.add_argument("--exclude-future-published", action="store_true", help="exclude journal papers whose published date is after today")
    args = parser.parse_args()

    base_dir = project_dir()
    load_env_file(base_dir / ".env")
    if args.skip_llm:
        import os

        os.environ["DEEPSEEK_API_KEY"] = ""
    config = load_config(base_dir / "config.json")
    if args.lookback_days is not None:
        config["lookback_days"] = args.lookback_days
    if args.exclude_future_published:
        config["include_future_published"] = False
    store = PaperStore(base_dir / "storage" / "papers.sqlite")
    imported = store.import_legacy_history(base_dir / "pushed_history.txt")
    if imported:
        print(f"[INFO] imported {imported} legacy pushed records.")

    try:
        papers = [paper for paper in collect_papers(config) if not store.has_seen(paper)]
        print(f"[INFO] {len(papers)} unseen papers after deduplication and history filter.")

        ranked = [keyword_score(paper, config) for paper in papers]
        ranked = [refine_relevance(item) for item in ranked]
        ranked.sort(key=lambda item: (item.score, item.paper.published_at.timestamp() if item.paper.published_at else 0), reverse=True)
        min_score = int(config.get("min_relevance_score", 55))
        selected = [item for item in ranked if item.score >= min_score]
        selected = selected[: int(config.get("max_papers_per_day", 5))]

        if not selected:
            print("[INFO] No relevant new papers today. Nothing to publish.")
            return 0

        selected = [summarize(item) for item in selected]
        report_date = datetime.now()
        md_content = render_markdown(selected, report_date)
        html_content = render_email_html(md_content, report_date)
        wechat_md_content = render_wechat_markdown(selected, report_date)
        wechat_html = render_wechat_html(wechat_md_content)
        title = plain_text_title(report_date)
        wx_title = wechat_title(report_date)

        output_dir = base_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = unique_report_path(output_dir, report_date)
        report_path.write_text(md_content, encoding="utf-8-sig")
        print(f"[OK] report written: {report_path}")

        if args.dry_run:
            print("[INFO] dry run enabled: skipped publishing and history update.")
            return 0

        publish_results = [
            try_publish("QQ mail", qq_mail.publish, config, title, html_content),
            try_publish("Feishu", feishu.publish, config, title, md_content),
            try_publish("WeChat", wechat_official.publish, config, wx_title, wechat_html, f"Daily digest: {len(selected)} selected papers."),
        ]
        if any(publish_results):
            for item in selected:
                store.mark_pushed(item.paper, item.score)
        else:
            print("[WARN] no publisher succeeded; skipped history update.")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
