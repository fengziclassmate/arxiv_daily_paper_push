# 城市遥感与 GIS 每日论文速递

这个版本把原来的单文件脚本拆成了可扩展 pipeline：

1. `sources/` 采集 ArXiv、IJGIS、CEUS 和可选会议数据源。
2. `storage.py` 用 SQLite 记录已推送论文，首次运行会导入 `pushed_history.txt`。
3. `scoring.py` 和 `llm.py` 负责规则初筛、DeepSeek 二次相关性判断和中文摘要。
4. `render.py` 生成 Markdown、邮件 HTML 和公众号 HTML。
5. `publishers/` 负责 QQ 邮件、飞书和微信公众号草稿箱。

## 运行

```powershell
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py
```

只生成报告、不推送、不写入已推送历史：

```powershell
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py --dry-run
```

快速检查采集和文件保存，不调用 DeepSeek：

```powershell
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py --dry-run --skip-llm
```

每次运行都会在 `output/` 下生成一个带时分秒的独立 Markdown 文件，例如 `paper_digest_20260427_095727.md`，同一天多次运行不会互相覆盖。

临时改成近 3 天或近 7 天：

```powershell
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py --lookback-days 3
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py --lookback-days 7
```

默认会保留期刊的未来 published 日期，因为这通常是出版社提前上线的卷期信息。若要严格排除未来日期：

```powershell
D:\Anaconda\envs\crawl\python.exe C:\Users\25371\Desktop\arxiv_daily_paper_push\code\main.py --exclude-future-published
```

## 配置

主要配置在 `config.json`：

- `topics.primary`：你的研究主题词。
- `topics.methods`：方法关键词。
- `sources.journals`：IJGIS、CEUS 等期刊源。
- `sources.semantic_scholar.enabled`：会议数据源开关，默认关闭。
- `publishers.wechat.enabled`：公众号草稿箱开关，默认关闭。

## 公众号

公众号默认只进草稿箱，不自动发布。需要配置：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_THUMB_MEDIA_ID`

然后把 `config.json` 中 `publishers.wechat.enabled` 改为 `true`。

程序会自动读取 `code/.env`。可以从 `.env.example` 复制一份改名为 `.env`，再填入自己的密钥。

CEUS 等 Elsevier 期刊有时不会在 Crossref 开放元数据中提供摘要。若需要尽量补齐这些摘要，可以在 `code/.env` 中配置 `ELSEVIER_API_KEY`。如果开放接口仍没有返回摘要，程序会明确标注摘要缺失，不会让模型编造摘要翻译。
