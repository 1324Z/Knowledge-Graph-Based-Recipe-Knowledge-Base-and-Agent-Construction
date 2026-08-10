# -*- coding: utf-8 -*-
"""演示问题测试脚本：验证三种查询路由的回答效果"""
import requests
import json
import time
import sys

API = "http://localhost:8001/api/chat"

QUESTIONS = [
    ("关系推理型", "需要鸡蛋的简单素菜有哪些"),
    ("详细做法型", "红烧肉怎么做"),
    ("列表推荐型", "推荐几个简单的家常菜"),
]

sys.stdout.reconfigure(encoding="utf-8")

for tag, q in QUESTIONS:
    print("=" * 60)
    print(f"【{tag}】{q}")
    print("=" * 60)
    t0 = time.time()
    try:
        resp = requests.post(API, json={"message": q}, timeout=180)
        elapsed = time.time() - t0
        data = resp.json()
        answer = data.get("response") or data.get("answer") or str(data)
        print(f"耗时: {elapsed:.1f}s | 状态码: {resp.status_code}")
        print("-" * 60)
        # 只打印前800字预览
        preview = answer[:800]
        print(preview + ("..." if len(answer) > 800 else ""))
    except Exception as e:
        print(f"请求失败: {e}")
    print()
