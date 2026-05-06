from __future__ import annotations

import re
from datetime import datetime
from html import escape
from urllib.parse import quote

import markdown

from .models import RankedPaper


def _paper_date(paper_date: datetime | None) -> str:
    if paper_date is None:
        return ""
    return paper_date.strftime("%Y-%m-%d")


def _paper_date_items(ranked: RankedPaper) -> list[tuple[str, str]]:
    paper = ranked.paper
    metadata = paper.metadata or {}
    date_keys = {"published_online", "published_print", "published", "accepted", "issued"}
    if any(metadata.get(key) for key in date_keys):
        items: list[tuple[str, str]] = []
        published_online = metadata.get("published_online")
        published_print = metadata.get("published_print") or metadata.get("issued")
        accepted = metadata.get("accepted")
        if published_online:
            items.append(("在线发布时间", published_online))
        elif metadata.get("published") and not published_print:
            items.append(("发布时间", metadata["published"]))
        if published_print:
            items.append(("期刊卷期时间", published_print))
        if accepted:
            items.append(("接收时间", accepted))
        return items
    published_at = _paper_date(paper.published_at)
    return [("发布时间", published_at)] if published_at else []


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


def _email_summary(ranked: RankedPaper) -> str:
    return ranked.email_summary or ranked.llm_summary or ""


def _is_bibliographic_alert(ranked: RankedPaper) -> bool:
    return ranked.paper.source == "IJGIS" and not ranked.paper.summary.strip()


def _paper_url(ranked: RankedPaper) -> str:
    paper = ranked.paper
    if paper.doi:
        return f"https://doi.org/{quote(paper.doi, safe='/.-()')}"
    return paper.url


def _paragraphs(text: str) -> str:
    parts = [part.strip() for part in re.split(r"\n{2,}", text.strip()) if part.strip()]
    if not parts:
        return "<p>摘要暂缺。</p>"
    return "".join(
        f'<p style="margin:0 0 12px;color:#333;font-size:15px;line-height:1.85;text-align:justify;">{escape(part)}</p>'
        for part in parts
    )


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
                *[f"- {label}：{value}" for label, value in _paper_date_items(ranked)],
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
                    _email_summary(ranked),
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
                *[f"- {label}：{value}" for label, value in _paper_date_items(ranked)],
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
                    _wechat_summary(ranked.wechat_summary or ranked.llm_summary),
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


def render_wechat_html(papers: list[RankedPaper], report_date: datetime) -> str:
    directions = _directions(papers)
    direction_text = " | ".join(directions) if directions else "城市遥感 | GIS | 时空智能"

    html_parts = [
        '<section style="font-family:\'Times New Roman\', serif;color:#1A1A1A;line-height:1.75;background:#ffffff;">',
        '<section style="padding:22px 0 18px;border-bottom:3px solid #0044FF;">',
        '<p style="margin:0 0 8px;color:#0044FF;font-size:13px;letter-spacing:1px;font-weight:bold;">PAPER DIGEST</p>',
        f'<h1 style="margin:0 0 14px;font-size:28px;line-height:1.25;font-weight:bold;color:#1A1A1A;">城市遥感与 GIS<br>论文速递</h1>',
        f'<p style="margin:0;color:#666666;font-size:14px;">发布日期：{report_date:%Y-%m-%d}　论文数量：{len(papers)}篇</p>',
        f'<p style="margin:8px 0 0;color:#666666;font-size:14px;">涵盖方向：{escape(direction_text)}</p>',
        '</section>',
        '<section style="margin:22px 0 24px;padding:16px 16px;background:#F7F9FF;border-left:4px solid #0044FF;">',
        '<p style="margin:0 0 12px;font-size:17px;font-weight:bold;color:#0044FF;">本期论文概览</p>',
    ]

    for idx, ranked in enumerate(papers, start=1):
        html_parts.append(
            '<p style="margin:0 0 8px;color:#333;font-size:14px;line-height:1.7;">'
            f'<strong style="color:#0044FF;">【{idx}】</strong>{escape(ranked.paper.title)}：{escape(_overview_reason(ranked))}'
            '</p>'
        )

    html_parts.extend(
        [
            '<p style="margin:14px 0 0;color:#666666;font-size:14px;line-height:1.7;">本期速递为您精选最新发布的城市遥感、GIS 与地理空间智能相关论文，覆盖从基础算法研究到前沿应用方向的多个领域。</p>',
            '</section>',
        ]
    )

    for idx, ranked in enumerate(papers, start=1):
        paper = ranked.paper
        url = _paper_url(ranked)
        html_parts.extend(
            [
                '<section style="margin:0 0 28px;padding:0 0 24px;border-bottom:2px solid #0044FF;">',
                '<section style="margin:0 0 14px;display:block;">',
                f'<p style="margin:0 0 6px;color:#0044FF;font-size:13px;font-weight:bold;">NO. {idx:02d}</p>',
                f'<h2 style="margin:0;font-size:20px;line-height:1.45;font-weight:bold;color:#1A1A1A;">{escape(paper.title)}</h2>',
                '</section>',
                '<section style="margin:0 0 14px;padding:10px 12px;background:#F8F8F8;color:#666666;font-size:13px;line-height:1.7;">',
                "".join(
                    f'<p style="margin:0;">{escape(label)}：{escape(value)}</p>'
                    for label, value in _paper_date_items(ranked)
                ),
                f'<p style="margin:0;">来源：{escape(paper.venue or paper.source)}</p>',
                f'<p style="margin:0;">作者：{escape(_authors(paper.authors))}</p>',
                '</section>',
            ]
        )

        if not _is_bibliographic_alert(ranked):
            html_parts.extend(
                [
                    '<p style="margin:0 0 8px;font-size:16px;font-weight:bold;color:#0044FF;">摘要</p>',
                    _paragraphs(_wechat_summary(ranked.wechat_summary or ranked.llm_summary)),
                ]
            )
        else:
            html_parts.append(
                '<p style="margin:0 0 12px;color:#607086;font-size:14px;line-height:1.75;">该条目作为题录提醒收录，开放元数据暂未提供摘要。</p>'
            )

        if url:
            safe_url = escape(url, quote=True)
            html_parts.extend(
                [
                    f'<p style="margin:8px 0 0;color:#999999;font-size:12px;line-height:1.5;word-break:break-all;">原文链接：{safe_url}</p>',
                ]
            )
        html_parts.append('</section>')

    html_parts.append('<p style="margin:24px 0 0;text-align:center;color:#999999;font-size:12px;">END</p></section>')
    return "".join(html_parts)


def plain_text_title(report_date: datetime) -> str:
    return escape(f"城市遥感与 GIS 论文速递 | {report_date:%Y-%m-%d}")
