修改了一下提示词内容和arxiv检索关键词，添加了qq邮箱推送的功能，源代码来源于https://github.com/NN0202/arxiv_daily_paper_push。

# 🚀 ArXiv Daily Paper Push | 学术前沿每日速递

![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek_V3-blueviolet)
![License](https://img.shields.io/badge/License-MIT-green)

这是一个自动化的学术论文追踪与精读工具。它每天自动从 ArXiv 抓取你所在领域的最新论文，调用 DeepSeek 大模型进行深度总结，并最终以排版精美的 Markdown HTML 邮件发送到你的邮箱中。

本项目最初为**城市遥感与 GIS** 领域的科研人员打造，但你可以通过修改搜索词和提示词，轻松将其适配到任何研究领域（如 CV、NLP、医疗 AI 等）。

## ✨ 核心特性

* 🔍 **精准检索**：基于 `arxiv` API 的高级布尔查询，精准捕获最新提交的顶会/顶刊预印本。
* 🧠 **深度总结**：接入强大的 DeepSeek 大模型，不仅翻译摘要，更深度拆解论文的**核心逻辑、破局路径与技术细节**。
* 💻 **代码溯源**：自动通过 PapersWithCode 接口查询论文是否带有官方开源代码，并附带链接。
* 📧 **优雅触达**：原生 Python SMTP 发送，支持 Markdown 渲染转 HTML，每天早上在 QQ 邮箱/微信接收精美日报。
* 🔒 **安全配置**：采用 `.env` 环境变量管理 API Key 和邮箱授权码，告别隐私泄露。

## 🛠️ 快速开始

### 1. 环境准备
确保你的电脑或服务器上已安装 Python 3.8+。
克隆本仓库并安装依赖库：

```bash
git clone [https://github.com/你的用户名/arxiv-daily-paper-push.git](https://github.com/你的用户名/arxiv-daily-paper-push.git)
cd arxiv-daily-paper-push
配置一下缺失的库
