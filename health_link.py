# -*- coding: utf-8 -*-
"""读取桌前健康助手写来的状态 ~/.claude/pet_health.json。

纯本地文件，不联网。超过 STALE_SEC 无更新视为监控未运行 -> 返回 None。
"""
import os
import json
import time

HEALTH_FILE = os.path.join(os.path.expanduser("~"), ".claude", "pet_health.json")
STALE_SEC = 8.0


def read_health():
    try:
        with open(HEALTH_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    try:
        if time.time() - float(d.get("ts", 0)) > STALE_SEC:
            return None
    except (TypeError, ValueError):
        return None
    return d
