from __future__ import annotations

import json
import os

import openai
from openai import OpenAI

from .models import RankedPaper


def _client() -> OpenAI | None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))


def _clean_markdown_output(text: str) -> str:
    banned_starts = (
        "好的",
        "以下",
        "请看",
        "为您生成",
        "标题：",
        "来源：",
        "作者：",
        "题目：",
    )
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if any(line.startswith(prefix) for prefix in banned_starts):
            continue
        if "微信公众号论文速递内容" in line or "为您生成的" in line:
            continue
        cleaned_lines.append(raw_line)

    cleaned = "\n".join(cleaned_lines).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned


def _extract_between(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    after_start = text.split(start, 1)[1]
    if end in after_start:
        after_start = after_start.split(end, 1)[0]
    return _clean_markdown_output(after_start.strip())


def refine_relevance(ranked: RankedPaper) -> RankedPaper:
    client = _client()
    if client is None:
        return ranked

    paper = ranked.paper
    prompt = f"""
请判断这篇论文是否适合推送给关注“城市遥感、GIS、城市更新、时空智能、多源地理空间数据融合”的读者。
只输出 JSON，不要输出解释性正文。

标题：{paper.title}
来源：{paper.source}
期刊/会议：{paper.venue or ""}
摘要：{paper.summary[:3500]}

JSON 格式：
{{
  "relevance_score": 0到100的整数,
  "topic_tags": ["标签1", "标签2"],
  "reason": "一句话说明为什么相关或不相关"
}}
"""
    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "你是严谨的地理信息科学与城市遥感论文筛选助手。"},
                {"role": "user", "content": prompt},
            ],
            timeout=45,
        )
        text = response.choices[0].message.content or "{}"
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        ranked.score = int(data.get("relevance_score", ranked.score))
        ranked.tags = list(data.get("topic_tags", ranked.tags))[:8]
        ranked.reason = str(data.get("reason", ranked.reason))
    except (json.JSONDecodeError, openai.OpenAIError, ValueError) as exc:
        print(f"[WARN] LLM relevance check failed for {paper.title}: {exc}")
    return ranked


def summarize(ranked: RankedPaper) -> RankedPaper:
    client = _client()
    paper = ranked.paper
    if paper.source == "IJGIS" and not paper.summary.strip():
        ranked.llm_summary = ""
        ranked.email_summary = ""
        ranked.wechat_summary = ""
        return ranked

    if not paper.summary.strip():
        ranked.email_summary = (
            "**中文学术翻译**：\n\n"
            "开放元数据暂未提供英文摘要，因此无法生成忠实的中文学术摘要翻译。\n\n"
            "**专业解读**：\n\n"
            f"- 一句话价值：{ranked.reason}\n"
            "- 方法亮点：摘要暂缺，暂不对具体方法细节作扩展判断。\n"
            "- 数据与场景：摘要暂缺，建议打开原文核对研究区域、数据来源与实验设置。\n"
            "- 对城市更新/GIS/遥感研究的启发：可先根据题名和来源作为候选文献保留，待获取摘要或全文后再精读。\n"
            "- 继续跟进指数：中，原因是题名和来源相关，但摘要暂缺，需进一步核对。"
        )
        ranked.wechat_summary = "开放元数据暂未提供英文摘要，建议点击原文查看详情。"
        ranked.llm_summary = ranked.email_summary
        return ranked

    if client is None:
        ranked.email_summary = (
            "**中文学术翻译**：\n\n"
            "未配置 DeepSeek API Key，暂未生成中文学术翻译。\n\n"
            "**专业解读**：\n\n"
            f"- 一句话价值：{ranked.reason}\n"
            "- 方法亮点：请结合英文摘要进一步确认。\n"
            "- 数据与场景：请打开原文核对数据来源、空间分辨率和实验区域。\n"
            "- 研究启发：可作为城市遥感、GIS 或时空建模方向的候选阅读。"
        )
        ranked.wechat_summary = paper.summary[:700]
        ranked.llm_summary = ranked.email_summary
        return ranked

    prompt = f"""
你是一名城市遥感、GIS 与地理空间智能方向的中文学术编辑。
请基于论文标题和英文摘要，同时生成两套内容：邮件深度版和微信公众号短摘要版。
要求：
1. 邮件深度版：先给出“中文学术翻译”，忠实翻译英文摘要；再给出“专业解读”，包括一句话价值、方法亮点、数据与场景、对城市更新/GIS/遥感研究的启发、继续跟进指数。
2. 微信公众号短摘要版：只输出 150-250 字中文摘要，不要标题，不要“专业解读”，不要项目符号，不要英文摘要，不要出现“中文学术翻译”字样。
3. 不要编造摘要中没有的信息；如果摘要没有数据集或区域信息，请在邮件深度版中写“摘要未说明”，公众号短摘要中直接略过。
4. 输出 Markdown。
5. 禁止输出“好的”“以下为您生成”“请看”等寒暄语。
6. 禁止重复输出标题、来源、作者字段；这些信息正文外部已经展示。

标题：{paper.title}
来源：{paper.source}
期刊/会议：{paper.venue or ""}
作者：{", ".join(paper.authors[:6])}
英文摘要：{paper.summary[:5000]}

请严格按以下结构输出：
<EMAIL>
**中文学术翻译**：

（这里给出完整、专业的中文摘要翻译）

**专业解读**：

- 一句话价值：
- 方法亮点：
- 数据与场景：
- 对城市更新/GIS/遥感研究的启发：
- 继续跟进指数：高/中/低，并给出一句理由。
</EMAIL>
<WECHAT>
（这里仅给出 150-250 字中文短摘要）
</WECHAT>
"""
    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "你擅长将英文学术摘要翻译为准确、克制、专业的中文，并给出面向 GIS 与遥感研究者的解读。"},
                {"role": "user", "content": prompt},
            ],
            timeout=90,
        )
        text = response.choices[0].message.content or ""
        email_summary = _extract_between(text, "<EMAIL>", "</EMAIL>")
        wechat_summary = _extract_between(text, "<WECHAT>", "</WECHAT>")
        ranked.email_summary = email_summary or _clean_markdown_output(text)
        ranked.wechat_summary = wechat_summary or _clean_markdown_output(text)
        ranked.llm_summary = ranked.email_summary
    except openai.OpenAIError as exc:
        ranked.email_summary = f"**中文学术翻译**：生成失败：{exc}\n\n**专业解读**：请打开原文核对。"
        ranked.wechat_summary = "摘要生成失败，请点击原文查看。"
        ranked.llm_summary = ranked.email_summary
    return ranked
