#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project ：arxiv_daily_paper_push
@File    ：get_cover_id.py
@IDE     ：PyCharm
@Author  ：疯子同学.
@Email   ：2537118325@qq.com
@Date    ：2026/4/26 11:52
@Brief   ：
"""
import os
import requests

app_id = "wx55893b957350df68"
app_secret = "7a47acc31273dc1745d34d6f00198a8e"
image_path = r"C:\Users\25371\Pictures\phone\Cache_bc70ffddff02c70.jpg"

resp = requests.post(
    "https://api.weixin.qq.com/cgi-bin/stable_token",
    json={
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
        "force_refresh": False,
    },
    timeout=20,
)

data = resp.json()
print(data)

if "access_token" not in data:
    raise RuntimeError(f"获取 stable access_token 失败: {data}")

access_token = data["access_token"]

with open(image_path, "rb") as f:
    resp = requests.post(
        "https://api.weixin.qq.com/cgi-bin/material/add_material",
        params={
            "access_token": access_token,
            "type": "thumb",
        },
        files={
            "media": f,
        },
        timeout=30,
    )

print(resp.json())
