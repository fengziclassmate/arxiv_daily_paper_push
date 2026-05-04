from __future__ import annotations

import os

import requests


def publish(config: dict, title: str, markdown_content: str) -> bool:
    feishu_config = config.get("publishers", {}).get("feishu", {})
    if not feishu_config.get("enabled", False):
        return False
    webhook = os.getenv("FEISHU_WEBHOOK") or feishu_config.get("webhook")
    if not webhook:
        print("[WARN] Feishu skipped: webhook is missing.")
        return False
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "orange"},
            "elements": [{"tag": "markdown", "content": markdown_content}],
        },
    }
    response = requests.post(webhook, json=payload, timeout=20)
    response.raise_for_status()
    print("[OK] Feishu message sent.")
    return True
