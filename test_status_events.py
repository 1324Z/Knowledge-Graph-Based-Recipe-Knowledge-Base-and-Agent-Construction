# -*- coding: utf-8 -*-
"""验证流式状态事件时序"""
import requests, time, json, sys
sys.stdout.reconfigure(encoding="utf-8")

query = sys.argv[1] if len(sys.argv) > 1 else "红烧肉怎么做"
session = sys.argv[2] if len(sys.argv) > 2 else "test_status"
print(f"问题: {query}\n")
t0 = time.time()
resp = requests.post(
    "http://localhost:8002/api/chat/stream",
    json={"message": query, "session_id": session, "stream": True},
    stream=True,
    timeout=120,
)
print(f"HTTP {resp.status_code}")

chunk_count = 0
for line in resp.iter_lines():
    if not line:
        continue
    elapsed = time.time() - t0
    text = line.decode("utf-8")
    if not text.startswith("data: "):
        continue
    data = text[6:]
    if data == "[DONE]":
        print(f"  [{elapsed:6.1f}s] DONE")
        break
    parsed = json.loads(data)
    if "status" in parsed:
        print(f"  [{elapsed:6.1f}s] STATUS → {parsed['status']}")
    elif "chunk" in parsed:
        chunk_count += 1
        if chunk_count <= 3:
            preview = parsed["chunk"][:30].replace("\n", " ")
            print(f'  [{elapsed:6.1f}s] CHUNK #{chunk_count}: "{preview}..."')

print(f"\n总耗时: {time.time()-t0:.1f}s | 内容块数: {chunk_count}")
