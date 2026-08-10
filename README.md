# 基于知识图谱的菜谱智能问答系统（Graph RAG）

基于 Neo4j 知识图谱 + Milvus 向量检索的混合 RAG 系统，实现菜谱推荐、智能问答、知识图谱可视化。

## 技术栈

- **知识图谱**：Neo4j 5.18 + APOC（323 菜谱 / 2906 食材 / 2514 烹饪步骤）
- **向量数据库**：Milvus v2.5.11（1138 个知识块，512 维 BGE 嵌入，HNSW 索引）
- **后端**：Flask（端口 8001），SSE 流式输出，语义缓存，多轮上下文
- **前端**：Next.js 14 + React 18 + TypeScript + Tailwind CSS + Zustand
- **嵌入模型**：BAAI/bge-small-zh-v1.5（本地部署）
- **LLM**：OpenAI 兼容 API（gpt-5.4）

## 项目结构

```
├── What-to-eat-today/          # 主应用
│   ├── main.py                 # 后端入口
│   ├── rag_modules/            # RAG 核心模块
│   │   ├── graph_data_preparation.py     # 图谱数据准备 + 文档分块
│   │   ├── milvus_index_construction.py  # Milvus 向量索引构建
│   │   ├── hybrid_retrieval.py           # 混合检索（图双层 + 向量增强）
│   │   ├── intelligent_query_router.py   # LLM 查询路由
│   │   ├── generation_integration.py     # 流式答案生成
│   │   ├── web_service_handler.py        # Flask Web 服务
│   │   ├── graph_rag_retrieval.py        # 图 RAG 检索
│   │   └── recipe_recommendation.py      # 菜谱推荐
│   ├── data/                   # 菜谱数据
│   │   ├── recipes_with_images.json
│   │   └── dishes/             # HowToCook 菜谱 Markdown
│   ├── frontend/               # Next.js 前端
│   └── kb_demo.py              # 知识库演示脚本
├── all-in-rag/data/C9/         # Docker 配置
│   ├── milvus-docker-compose.yml
│   ├── docker-compose.yml      # Neo4j
│   └── cypher/                 # Neo4j 导入数据和脚本
│       ├── nodes.csv
│       ├── relationships.csv
│       └── neo4j_import.cypher
└── test_*.py                   # 测试脚本
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.12 + conda 环境
conda create -n cook-rag python=3.12
conda activate cook-rag
pip install -r requirements.txt
```

### 2. 配置

```bash
# 后端配置
cp What-to-eat-today/.env.example What-to-eat-today/.env
# 编辑 .env 填入 API Key、Neo4j 密码等

# 前端配置
cp What-to-eat-today/frontend/.env.local.example What-to-eat-today/frontend/.env.local
```

### 3. 启动 Docker 服务

```bash
# Neo4j
cd all-in-rag/data/C9
docker compose -f docker-compose.yml up -d
docker compose -f milvus-docker-compose.yml up -d
```

### 4. 启动后端

```bash
cd What-to-eat-today
python main.py
```

### 5. 启动前端

```bash
cd What-to-eat-today/frontend
npm install
npm run dev
```

### 6. 访问

- 前端：http://localhost:3000
- 后端 API：http://localhost:8001
- Neo4j 浏览器：http://localhost:7474
- MinIO 控制台：http://localhost:9003

## 核心功能

- **三路混合检索**：图双层检索（实体级+主题级）+ Milvus 向量增强检索 + Neo4j 1 跳邻居扩展
- **Round-Robin 轮询融合**：多路检索结果交替合并去重
- **LLM 查询路由**：根据问题类型动态选择检索策略
- **SSE 流式输出**：分阶段状态反馈（缓存检查→问题分析→混合检索→答案生成）
- **语义缓存**：相似问题秒级响应
- **知识图谱可视化**：Neo4j Browser 演示 REQUIRES/SIMILAR 关系
