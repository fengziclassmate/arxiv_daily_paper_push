from __future__ import annotations

import json
import os

import requests

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
FREEPUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
MAX_TITLE_BYTES = 64


def _access_token() -> str | None:
    app_id = os.getenv("WECHAT_APP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")
    if not app_id or not app_secret:
        return None
    response = requests.get(
        TOKEN_URL,
        params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if "access_token" not in data:
        raise RuntimeError(f"WeChat token error: {data}")
    return data["access_token"]


def _fit_wechat_title(title: str) -> str:
    cleaned = " ".join(title.split())
    encoded = cleaned.encode("utf-8")
    if len(encoded) <= MAX_TITLE_BYTES:
        return cleaned

    result = ""
    for char in cleaned:
        if len((result + char).encode("utf-8")) > MAX_TITLE_BYTES:
            break
        result += char
    return result.rstrip() or "Paper Digest"


def publish(config: dict, title: str, html_content: str, digest: str, source_url: str = "") -> bool:
    wechat_config = config.get("publishers", {}).get("wechat", {})
    if not wechat_config.get("enabled", False):
        return False

    missing = [
        name
        for name in ("WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_THUMB_MEDIA_ID")
        if not (os.getenv(name) or (name == "WECHAT_THUMB_MEDIA_ID" and wechat_config.get("thumb_media_id")))
    ]
    if missing:
        print(f"[WARN] WeChat skipped: missing {', '.join(missing)}. Put them in code/.env or disable publishers.wechat.enabled.")
        return False

    token = _access_token()
    thumb_media_id = os.getenv("WECHAT_THUMB_MEDIA_ID") or wechat_config.get("thumb_media_id")
    if not token:
        print("[WARN] WeChat skipped: failed to get access token.")
        return False

    configured_source_url = wechat_config.get("content_source_url", "") or source_url
    article = {
        "title": _fit_wechat_title(title),
        "author": wechat_config.get("author", ""),
        "digest": digest[:120],
        "content": html_content,
        "content_source_url": configured_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    payload = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
    response = requests.post(
        DRAFT_ADD_URL,
        params={"access_token": token},
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"WeChat add draft error: {data}")

    media_id = data["media_id"]
    print(f"[OK] WeChat draft created: {media_id}")

    if wechat_config.get("draft_only", True):
        return True

    publish_payload = json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8")
    response = requests.post(
        FREEPUBLISH_URL,
        params={"access_token": token},
        data=publish_payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    response.raise_for_status()
    publish_data = response.json()
    if publish_data.get("errcode", 0) != 0:
        raise RuntimeError(f"WeChat publish error: {publish_data}")
    print(f"[OK] WeChat publish submitted: {publish_data}")
    return True
