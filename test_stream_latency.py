# -*- coding: utf-8 -*-
"""测试 SSE 流式接口：首 token 延迟 + 总耗时"""
import requests
import time
import sys

sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8001/api/chat/stream"
q = "红烧肉怎么做"

t0 = time.time()
first_token_at = None
chunks = 0
total_text = 0

with requests.post(API, json={"message": q}, stream=True, timeout=180) as resp:
    print(f"状态码: {resp.status_code}")
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        chunks += 1
        if first_token_at is None:
            first_token_at = time.time() - t0
        total_text += len(line)

total = time.time() - t0
print(f"首数据块延迟: {first_token_at:.1f}s")
print(f"总耗时: {total:.1f}s")
print(f"数据块数: {chunks}, 累计字符: {total_text}")
