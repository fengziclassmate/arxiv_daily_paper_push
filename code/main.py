from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from paper_digest.config import load_config, load_env_file, project_dir
from paper_digest.deduplicate import deduplicate
from paper_digest.llm import refine_relevance, summarize
from paper_digest.publishers import feishu, qq_mail, wechat_official
from paper_digest.render import plain_text_title, render_email_html, render_markdown, render_wechat_html
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
    return f"城市遥感与GIS论文速递 | {report_date:%m-%d}"


def wechat_digest(selected) -> str:
    directions: list[str] = []
    for item in selected:
        for tag in item.tags:
            if tag and tag not in directions:
                directions.append(tag)
    direction_text = "、".join(directions[:4]) if directions else "城市遥感、GIS、时空智能"
    return f"本期精选{len(selected)}篇城市遥感、GIS与地理空间智能相关论文，涵盖{direction_text}等方向。"


def first_source_url(selected) -> str:
    for item in selected:
        if item.paper.doi:
            return f"https://doi.org/{item.paper.doi}"
        if item.paper.url:
            return item.paper.url
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish a daily paper digest.")
    parser.add_argument("--dry-run", action="store_true", help="write the report without publishing or marking papers as pushed")
    parser.add_argument("--skip-llm", action="store_true", help="skip DeepSeek relevance checks and summaries")
    parser.add_argument("--lookback-days", type=int, help="override config lookback_days for this run")
    parser.add_argument("--max-papers", type=int, help="override config max_papers_per_day for this run")
    parser.add_argument("--exclude-future-published", action="store_true", help="exclude journal papers whose published date is after today")
    parser.add_argument("--ignore-history", action="store_true", help="include already pushed papers and skip updating push history; useful for draft previews")
    args = parser.parse_args()

    base_dir = project_dir()
    load_env_file(base_dir / ".env")
    if args.skip_llm:
        import os

        os.environ["DEEPSEEK_API_KEY"] = ""
    config = load_config(base_dir / "config.json")
    if args.lookback_days is not None:
        config["lookback_days"] = args.lookback_days
    if args.max_papers is not None:
        config["max_papers_per_day"] = args.max_papers
    if args.exclude_future_published:
        config["include_future_published"] = False
    store = PaperStore(base_dir / "storage" / "papers.sqlite")
    imported = store.import_legacy_history(base_dir / "pushed_history.txt")
    if imported:
        print(f"[INFO] imported {imported} legacy pushed records.")

    try:
        collected = collect_papers(config)
        if args.ignore_history:
            papers = collected
            print(f"[INFO] {len(papers)} papers after deduplication; history filter disabled.")
        else:
            papers = [paper for paper in collected if not store.has_seen(paper)]
            print(f"[INFO] {len(papers)} unseen papers after deduplication and history filter.")

        ranked = [keyword_score(paper, config) for paper in papers]
        ranked.sort(key=lambda item: (item.score, item.paper.published_at.timestamp() if item.paper.published_at else 0), reverse=True)
        max_papers = int(config.get("max_papers_per_day", 5))
        candidate_limit = int(config.get("llm_candidate_limit", 90))
        candidate_min = int(config.get("llm_candidate_min", 30))
        candidate_multiplier = int(config.get("llm_candidate_multiplier", 3))
        candidate_limit = min(candidate_limit, max(candidate_min, max_papers * candidate_multiplier))
        candidate_limit = min(candidate_limit, len(ranked))
        llm_candidates = ranked[:candidate_limit]
        skipped_candidates = ranked[candidate_limit:]
        llm_candidates = [refine_relevance(item) for item in llm_candidates]
        ranked = llm_candidates + skipped_candidates
        ranked.sort(key=lambda item: (item.score, item.paper.published_at.timestamp() if item.paper.published_at else 0), reverse=True)
        min_score = int(config.get("min_relevance_score", 55))
        selected = [item for item in ranked if item.score >= min_score]
        selected = selected[:max_papers]

        if not selected and args.max_papers is not None and ranked:
            print("[WARN] No papers passed the relevance threshold; using top-ranked candidates for this limited preview run.")
            selected = ranked[:max_papers]

        if not selected:
            print("[INFO] No relevant new papers today. Nothing to publish.")
            return 0

        crossref_source.supplement_missing_abstracts([item.paper for item in selected])
        selected = [summarize(item) for item in selected]
        report_date = datetime.now()
        md_content = render_markdown(selected, report_date)
        html_content = render_email_html(md_content, report_date)
        wechat_html = render_wechat_html(selected, report_date)
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
            try_publish("WeChat", wechat_official.publish, config, wx_title, wechat_html, wechat_digest(selected), first_source_url(selected)),
        ]
        if any(publish_results) and not args.ignore_history:
            for item in selected:
                store.mark_pushed(item.paper, item.score)
        elif any(publish_results):
            print("[INFO] history update skipped because --ignore-history is enabled.")
        else:
            print("[WARN] no publisher succeeded; skipped history update.")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
