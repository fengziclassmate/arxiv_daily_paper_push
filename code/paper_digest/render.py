from __future__ import annotations

import re
from datetime import datetime
from html import escape

import markdown

from .models import RankedPaper


def _paper_date(paper_date: datetime | None) -> str:
    if paper_date is None:
        return "Unknown"
    return paper_date.strftime("%Y-%m-%d")


def _authors(authors: list[str]) -> str:
    if not authors:
        return "Unknown"
    text = "、".join(authors[:4])
    if len(authors) > 4:
        text += " 等"
    return text


def _directions(papers: list[RankedPaper]) -> list[str]:
    seen: list[str] = []
    for ranked in papers:
        for tag in ranked.tags:
            if tag and tag not in seen:
                seen.append(tag)
    return seen[:10]


def _overview_reason(ranked: RankedPaper) -> str:
    if ranked.tags:
        return f"主要涉及{'、'.join(ranked.tags[:3])}研究。"
    return ranked.reason.rstrip("。") + "。"


def _render_issue_overview(papers: list[RankedPaper], report_date: datetime) -> list[str]:
    directions = _directions(papers)
    direction_text = " | ".join(directions) if directions else "城市遥感 | GIS | 时空智能"
    lines = [
        f"📅 发布日期：{report_date:%Y-%m-%d}",
        f"📊 论文数量：{len(papers)}篇",
        f"🔬 涵盖方向：{direction_text}",
        "",
        "本期论文概览：",
    ]
    for idx, ranked in enumerate(papers, start=1):
        lines.append(f"【{idx}】{ranked.paper.title}：{_overview_reason(ranked)}")
    lines.extend(
        [
            "",
            "本期速递为您精选最新发布的城市遥感、GIS 与地理空间智能相关论文，覆盖从基础算法研究到前沿应用方向的多个领域。",
            "",
            "---",
            "",
        ]
    )
    return lines


def _wechat_summary(llm_summary: str | None) -> str:
    if not llm_summary:
        return "摘要暂缺。"

    text = llm_summary.strip()
    text = re.sub(r"^\s*\*\*中文学术翻译\*\*\s*[：:]\s*", "", text)
    text = re.split(r"\n\s*\*\*专业解读\*\*\s*[：:]?", text, maxsplit=1)[0]
    text = re.split(r"\n\s*-?\s*专业解读\s*[：:]?", text, maxsplit=1)[0]
    text = text.strip()
    return text or "摘要暂缺。"


def _is_bibliographic_alert(ranked: RankedPaper) -> bool:
    return ranked.paper.source == "IJGIS" and not ranked.paper.summary.strip()


def render_markdown(papers: list[RankedPaper], report_date: datetime) -> str:
    lines = [
        f"# 城市遥感与 GIS 论文速递 | {report_date:%Y-%m-%d}",
        "",
        *_render_issue_overview(papers, report_date),
    ]

    for idx, ranked in enumerate(papers, start=1):
        paper = ranked.paper
        lines.extend(
            [
                f"## 【{idx}】{paper.title}",
                "",
                f"- 发布时间：{_paper_date(paper.published_at)}",
                f"- 来源：{paper.venue or paper.source}",
                f"- 作者：{_authors(paper.authors)}",
                f"- 链接：[原文]({paper.url})" + (f" | [代码]({paper.code_url})" if paper.code_url else ""),
                f"- 相关性：{ranked.score}/100；{ranked.reason}",
                "",
            ]
        )
        if not _is_bibliographic_alert(ranked):
            lines.extend(
                [
                    "**英文摘要**：",
                    "",
                    paper.summary or "开放元数据暂未提供英文摘要。",
                    "",
                    ranked.llm_summary or "",
                    "",
                ]
            )
        lines.extend(["---", ""])
    return "\n".join(lines)


def render_wechat_markdown(papers: list[RankedPaper], report_date: datetime) -> str:
    lines = [
        f"# 城市遥感与 GIS 论文速递 | {report_date:%Y-%m-%d}",
        "",
        *_render_issue_overview(papers, report_date),
    ]

    for idx, ranked in enumerate(papers, start=1):
        paper = ranked.paper
        lines.extend(
            [
                f"## 【{idx}】{paper.title}",
                "",
                f"- 发布时间：{_paper_date(paper.published_at)}",
                f"- 来源：{paper.venue or paper.source}",
                f"- 作者：{_authors(paper.authors)}",
                f"- 链接：[原文]({paper.url})" + (f" | [代码]({paper.code_url})" if paper.code_url else ""),
                "",
            ]
        )
        if not _is_bibliographic_alert(ranked):
            lines.extend(
                [
                    "**摘要**：",
                    "",
                    _wechat_summary(ranked.llm_summary),
                    "",
                ]
            )
        lines.extend(["---", ""])
    return "\n".join(lines)


def render_email_html(markdown_content: str, report_date: datetime) -> str:
    body = markdown.markdown(markdown_content, extensions=["extra"])
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; line-height: 1.75; color: #222; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 18px; margin-top: 28px; }}
    a {{ color: #1769aa; text-decoration: none; }}
    hr {{ border: 0; border-top: 1px solid #e5e5e5; margin: 24px 0; }}
    strong {{ color: #111; }}
  </style>
</head>
<body>
  {body}
  <hr>
  <p style="font-size:12px;color:#777;">基于 DeepSeek 自动生成 | {report_date:%Y-%m-%d}</p>
</body>
</html>
"""


def render_wechat_html(markdown_content: str) -> str:
    html = markdown.markdown(markdown_content, extensions=["extra"])
    return f'<section style="font-size:15px;line-height:1.8;color:#222;">{html}</section>'


def plain_text_title(report_date: datetime) -> str:
    return escape(f"城市遥感与 GIS 论文速递 | {report_date:%Y-%m-%d}")
