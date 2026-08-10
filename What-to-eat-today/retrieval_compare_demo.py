# -*- coding: utf-8 -*-
"""三路检索对比演示：BM25(休眠) / 图双层检索(实际) / 向量增强检索(实际) / Round-Robin融合"""
import os
import sys

# 必须在 import huggingface 前设置
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(override=True)

from main import AdvancedGraphRAGSystem

QUERY = "需要鸡蛋的菜"
TOP_K = 5


def show_header(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def main():
    print("正在初始化系统（约20秒，加载模型+图谱）...")
    rag = AdvancedGraphRAGSystem()
    rag.initialize_system()
    rag.build_knowledge_base()

    tr = rag.traditional_retrieval  # HybridRetrievalModule

    # ① 休眠的 BM25（简历声称有，实际未接入 hybrid_search）
    show_header(f"① BM25 关键词检索（休眠状态，手动唤醒演示）: 「{QUERY}」")
    try:
        bm25_docs = tr.bm25_retriever.invoke(QUERY)
        for i, d in enumerate(bm25_docs[:TOP_K], 1):
            name = d.metadata.get("recipe_name", "?")
            snippet = d.page_content.replace("\n", " ")[:70]
            print(f"  Top{i} | 《{name}》\n         {snippet}...")
    except Exception as e:
        print(f"  BM25 调用失败: {e}")

    # ② 图双层检索（实际路径1：实体级+主题级+1跳邻居）
    show_header(f"② 图双层检索 dual_level（实际路径1）: 「{QUERY}」")
    try:
        dual_docs = tr.dual_level_retrieval(QUERY, TOP_K)
        for i, d in enumerate(dual_docs, 1):
            name = d.metadata.get("recipe_name", "?")
            lvl = d.metadata.get("retrieval_level", "?")
            score = d.metadata.get("relevance_score", 0)
            snippet = d.page_content.replace("\n", " ")[:70]
            print(f"  Top{i} | [{lvl}] score={score:.2f} | 《{name}》\n         {snippet}...")
    except Exception as e:
        print(f"  图双层检索失败: {e}")

    # ③ 向量增强检索（实际路径2：Milvus+1跳邻居）
    show_header(f"③ 向量增强检索 vector_enhanced（实际路径2）: 「{QUERY}」")
    try:
        vec_docs = tr.vector_search_enhanced(QUERY, TOP_K)
        for i, d in enumerate(vec_docs, 1):
            name = d.metadata.get("recipe_name", "?")
            score = d.metadata.get("score", 0)
            snippet = d.page_content.replace("\n", " ")[:70]
            print(f"  Top{i} | score={score:.4f} | 《{name}》\n         {snippet}...")
    except Exception as e:
        print(f"  向量检索失败: {e}")

    # ④ Round-Robin 融合最终结果
    show_header(f"④ Round-Robin 融合最终结果 hybrid_search: 「{QUERY}」")
    try:
        merged = tr.hybrid_search(QUERY, TOP_K)
        for i, d in enumerate(merged, 1):
            name = d.metadata.get("recipe_name", "?")
            method = d.metadata.get("search_method", "?")
            final = d.metadata.get("final_score", 0)
            snippet = d.page_content.replace("\n", " ")[:70]
            print(f"  Top{i} | [{method}] final={final:.3f} | 《{name}》\n         {snippet}...")
    except Exception as e:
        print(f"  融合检索失败: {e}")

    rag.traditional_retrieval.close()
    print("\n✅ 演示完成")


if __name__ == "__main__":
    main()
