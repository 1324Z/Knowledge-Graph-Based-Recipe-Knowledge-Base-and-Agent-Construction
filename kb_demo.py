# -*- coding: utf-8 -*-
"""向量知识库现场演示脚本
用法: python kb_demo.py "你的问题"
不传入问题则默认演示 "需要鸡蛋的菜"
"""
import sys
from pymilvus import connections, Collection
from langchain_huggingface import HuggingFaceEmbeddings

sys.stdout.reconfigure(encoding="utf-8")

query = sys.argv[1] if len(sys.argv) > 1 else "需要鸡蛋的菜"

print("=" * 60)
print("① 连接 Milvus 知识库")
print("=" * 60)
connections.connect(host="localhost", port="19530")
col = Collection("cooking_knowledge")
col.load()
print(f"集合名称: cooking_knowledge")
print(f"知识块总数: {col.num_entities}")
print(f"字段数: {len(col.schema.fields)}")
for f in col.schema.fields:
    extra = f" dim={f.params.get('dim')}" if 'dim' in f.params else ""
    dtype = getattr(f.dtype, 'name', str(f.dtype))
    print(f"  - {f.name:<15} {dtype:<15}{extra}")

print()
print("=" * 60)
print("② HNSW 索引参数")
print("=" * 60)
for idx in col.indexes:
    print(f"字段: {idx.field_name} | 参数: {idx.params}")

print()
print("=" * 60)
print(f"③ 现场向量检索: 「{query}」")
print("=" * 60)
embeddings = HuggingFaceEmbeddings(
    model_name="E:/rag/all-in-rag/models/bge-small-zh-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
import time
t0 = time.time()
qv = embeddings.embed_query(query)
res = col.search(
    data=[qv],
    anns_field="vector",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=5,
    output_fields=["text", "recipe_name", "category"],
)
elapsed = (time.time() - t0) * 1000
print(f"检索耗时: {elapsed:.0f}ms (含模型推理)\n")

for rank, hit in enumerate(res[0], 1):
    recipe = hit.entity.get("recipe_name") or "未知"
    category = hit.entity.get("category") or ""
    text = hit.entity.get("text", "").replace("\n", " ")[:80]
    print(f"Top {rank} | 相似度: {hit.distance:.4f} | 《{recipe}》({category})")
    print(f"        {text}...")
    print()
