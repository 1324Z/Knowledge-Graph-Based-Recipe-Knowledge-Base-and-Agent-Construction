# -*- coding: utf-8 -*-
"""验证菜谱推荐与详情接口"""
import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 1. 推荐接口
r = requests.post("http://localhost:8002/api/recipes/recommendations", json={}, timeout=30)
data = r.json()
recipes = data.get("data", [])
print(f"[推荐接口] 状态码: {r.status_code}, 返回 {len(recipes)} 个菜谱")
for rec in recipes:
    print(f"  - id={rec['id']} | {rec['name']} | {rec['category']} | 图片: {rec['imageUrl'][:80]}")

# 2. 详情接口（用推荐返回的第一个 id 测试）
if recipes:
    rid = recipes[0]["id"]
    r2 = requests.get(f"http://localhost:8002/api/recipes/{rid}", timeout=30)
    d = r2.json()
    if r2.status_code == 200 and d.get("success"):
        detail = d["data"]
        print(f"\n[详情接口] 状态码: {r2.status_code} | {detail['name']}")
        print(f"  食材数: {len(detail.get('ingredients', []))}, 步骤数: {len(detail.get('steps', []))}")
        print(f"  图片: {detail['imageUrl'][:100]}")
    else:
        print(f"\n[详情接口] 失败: {r2.status_code} {r2.text[:200]}")

# 3. 健康检查
r3 = requests.get("http://localhost:8002/health", timeout=10)
print(f"\n[健康检查] {r3.json()}")
