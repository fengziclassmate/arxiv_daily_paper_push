#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project ：arxiv_daily_paper_push 
@File    ：daily_Papers.py
@IDE     ：PyCharm 
@Author  ：疯子同学.
@Email   ：2537118325@qq.com
@Date    ：2026/4/17 14:15 
@Brief   ：
"""
import arxiv
import openai
import requests
import json
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import markdown
import os
from openai import OpenAI

# --- 配置区 ---
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook"
PWC_BASE_URL = "https://arxiv.paperswithcode.com/api/v0/papers/"

# # --- 邮箱推送配置 ---
QQ_MAIL_SENDER = "2537118325@qq.com"       # 发件人邮箱
QQ_MAIL_AUTH_CODE = os.getenv("QQ_MAIL_AUTH_CODE")
QQ_MAIL_RECEIVER = "2537118325@qq.com"  # 收件人邮箱（可以是同一个QQ邮箱，即自己发给自己）


def get_code_link(arxiv_url):
    """从 PapersWithCode 获取代码链接"""
    arxiv_id = arxiv_url.split('/')[-1].split('v')[0]
    try:
        r = requests.get(f"{PWC_BASE_URL}{arxiv_id}", timeout=10).json()
        if "official" in r and r["official"]:
            return r["official"]["url"]
    except:
        pass
    return None


def summarize_with_deepseek(paper):
    """使用 DeepSeek 进行论文摘要深度总结"""
    # 构造 Prompt
    prompt_text = f"""你是一名资深的城市遥感与GIS专家，擅长将最先进的人工智能技术应用于城市更新和地理空间分析。
        请根据以下论文的标题和摘要进行深度专业中文分析。

        论文标题: {paper['title']}
        论文摘要: {paper['summary']}

        请严格按此格式输出：
        【城市更新/遥感应用价值】: （说明该研究在城市更新场景、遥感制图或GIS空间分析中的具体落地场景是什么？）
        【方法论拆解】：
        - **核心逻辑**：作者是如何针对地理空间数据/城市问题的特殊性（如多尺度、时空相关性、多模态）进行设计的？
        - **破局路径**：作者的核心直觉是什么？他解决了之前模型在处理空间数据时的什么痛点？
        - **实现流程**：1, 2, 3 步精炼描述。
        【数据与技术细节】: （重点关注：使用了什么遥感源数据（如Sentinel/高分/街景）、空间分辨率、是否有特殊的损失函数设计或坐标嵌入技术？）
        【对你的启发】: （作为博士研究，这篇论文在实验设计、新数据集构建或多源数据融合方面有什么值得模仿的地方？）
        【专业术语解读】: （解释文中涉及的GIS/AI交叉概念，如 GNN、Self-Attention、NDVI、时空卷积等）
        """

    try:
        # 【关键点 1】初始化 Client
        # 注意：使用 openai 库时，base_url 只需要填到域名即可，千万不要加上 /chat/completions
        client = OpenAI(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url="https://api.deepseek.com"
        )

        # 发起调用
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个学术分析专家，擅长将复杂的人工智能领域的论文总结得清晰易懂。"},
                {"role": "user", "content": prompt_text}
            ],
            stream=False,
            timeout=60  # 设置超时时间，防止死等
        )

        # 【关键点 2】直接提取内容返回，不需要再手动解析 JSON 了
        return response.choices[0].message.content

        # 【关键点 3】使用 openai 库自带的精准错误捕获
    except openai.AuthenticationError:
        return "❌ API Key 错误或无效，请检查 DEEPSEEK_API_KEY。"
    except openai.APIConnectionError:
        return "❌ 网络连接失败或 base_url 填写错误（请确保能正常访问 DeepSeek）。"
    except openai.RateLimitError:
        return "❌ API 请求太频繁，或者账户余额不足，请去 DeepSeek 官网检查额度。"
    except openai.APIError as e:
        return f"❌ DeepSeek 服务器端报错: {str(e)}"
    except Exception as e:
        return f"❌ 发生未知异常: {str(e)}"


def push_to_feishu(report_content):
    """发送飞书富文本卡片"""
    header = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚀 ArXiv {datetime.now().strftime('%m-%d')}"},
                "template": "orange"
            },
            "elements": [
                {"tag": "markdown", "content": report_content},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "基于 DeepSeek-V3 自动生成"}]}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, headers=header, json=payload)


def push_to_qq_mail(report_content):
    """发送邮件到指定邮箱"""
    print("正在生成邮件并发送...")

    # 1. 将 Markdown 转换为 HTML 以保证邮件排版美观
    # extensions=['extra'] 支持了表格、代码块等高级 Markdown 语法
    html_content = markdown.markdown(report_content, extensions=['extra'])

    # 为了让邮件稍微好看一点，给 HTML 加一点基础的 CSS 样式
    email_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        h3 {{ color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        a {{ color: #3498db; text-decoration: none; }}
        hr {{ border: 0; border-top: 1px solid #ddd; margin: 20px 0; }}
        strong {{ color: #e74c3c; }}
    </style>
    </head>
    <body>
        <h2>🚀 城市遥感与 GIS 前沿速递 ({datetime.now().strftime('%m-%d')})</h2>
        {html_content}
        <br><hr>
        <p style="font-size: 12px; color: #7f8c8d;">基于 DeepSeek 自动分析生成 | By 疯子同学</p>
    </body>
    </html>
    """

    # 2. 构造邮件对象
    msg = MIMEMultipart()
    msg['From'] = QQ_MAIL_SENDER
    msg['To'] = QQ_MAIL_RECEIVER
    msg['Subject'] = f"🚀 ArXiv 每日科研速递 {datetime.now().strftime('%Y-%m-%d')}"

    # 将 HTML 内容附加到邮件中
    msg.attach(MIMEText(email_html, 'html', 'utf-8'))

    # 3. 连接 QQ 邮箱服务器并发送
    try:
        # QQ 邮箱使用 SSL 加密，端口为 465
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(QQ_MAIL_SENDER, QQ_MAIL_AUTH_CODE)
        server.sendmail(QQ_MAIL_SENDER, [QQ_MAIL_RECEIVER], msg.as_string())
        server.quit()
        print("📧 QQ邮件发送成功！请查收。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")


if __name__ == "__main__":
    print("正在搜集最新论文...")
    client = arxiv.Client()
    search_query = (
        '(abs:"Urban Remote Sensing" OR abs:GIS OR abs:"Urban Renewal" OR abs:"Urban Planning" OR abs:"Spatio-temporal") '
        'AND (abs:"Deep Learning" OR abs:Transformer OR abs:Segmentation OR abs:"Computer Vision" OR abs:"Foundation Model")'
    )

    search = arxiv.Search(
        query=search_query,
        max_results=1,  # 领域论文通常比纯AI少，可以适当增加获取量
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    full_report = ""
    results = list(client.results(search))

    if not results:
        print("今日暂无新论文。")
    else:
        for i, res in enumerate(results):
            print(f"正在分析第 {i + 1}/{len(results)} 篇: {res.title}")

            code_url = get_code_link(res.entry_id)
            code_md = f" | [💻 代码]({code_url})" if code_url else ""

            paper_info = {
                "title": res.title,
                "summary": res.summary.replace('\n', ' '),
                "url": res.entry_id
            }

            summary = summarize_with_deepseek(paper_info)
            full_report += f"### {i + 1}. {res.title}\n🔗 [原文]({res.entry_id}){code_md}\n{summary}\n\n---\n"

        # push_to_feishu(full_report)
        push_to_qq_mail(full_report)
