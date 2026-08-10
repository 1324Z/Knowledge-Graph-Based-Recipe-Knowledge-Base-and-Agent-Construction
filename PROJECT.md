# 基于知识图谱的菜谱智能问答系统 — 项目流程文档

## 一、项目背景

日常烹饪场景中，用户的问题往往不只是简单的关键词匹配。比如"鸡蛋有哪些做法"既需要列出具体菜谱，又需要理解食材与菜品之间的关联关系；"红烧肉怎么做"则需要完整的步骤信息。传统 RAG 仅依赖向量检索，缺乏对实体间关系的结构化理解，容易遗漏关联菜谱或无法推理食材替代。

本项目构建了一套**知识图谱 + 向量检索**的混合 RAG 系统，以 Neo4j 存储菜谱、食材、步骤之间的图结构关系，以 Milvus 存储 1138 个语义知识块的向量表示，通过多路并行检索 + LLM 路由 + 流式生成，实现菜谱推荐与智能问答。

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层 (Next.js 3000)                        │
│                   SSE 流式接收 + 分阶段状态展示                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                      服务层 (Flask 8001)                      │
│    语义缓存 → 查询路由 → 混合检索 → 流式生成 → SSE 推送            │
└──┬───────────┬───────────────────┬──────────────────┬────────┘
   │           │                   │                  │
   ▼           ▼                   ▼                  ▼
┌──────┐ ┌─────────┐    ┌──────────────┐    ┌─────────────┐
│语义  │ │LLM 查询 │    │  混合检索层   │    │  生成层     │
│缓存  │ │路由     │    │              │    │ (LLM 流式)  │
└──────┘ └─────────┘    └──────┬───────┘    └─────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌──────────┐   ┌──────────┐   ┌──────────┐
         │图双层检索 │   │向量增强  │   │Neo4j 1跳 │
         │(实体+主题)│   │(Milvus)  │   │邻居扩展  │
         └─────┬────┘   └─────┬────┘   └──────────┘
               │              │
               ▼              ▼
         ┌──────────┐   ┌──────────────┐
         │ Neo4j    │   │ Milvus      │
         │ 知识图谱 │   │ 向量知识库  │
         │ 7687    │   │ 19530       │
         └─────────┘   └─────────────┘
```

## 三、数据层：知识图谱与向量知识库构建

### 3.1 知识图谱构建（Neo4j）

**数据来源**：323 道中式菜谱的 Markdown 文件（HowToCook 开源项目），每道菜谱包含食材清单、烹饪步骤、分类标签等结构化信息。

**图谱 Schema**：

```
节点类型：
  Recipe（菜谱）       — nodeId, name, difficulty, cook_time, category
  Ingredient（食材）   — nodeId, name, type
  CookingStep（步骤）  — nodeId, step_number, description
  Category（分类）     — name（水产/早餐/荤菜/素菜/...）

关系类型：
  REQUIRES         — Recipe → Ingredient（菜谱需要食材）
  CONTAINS_STEP    — Recipe → CookingStep（菜谱包含步骤）
  BELONGS_TO_CATEGORY — Recipe → Category（菜谱属于分类）
  SIMILAR          — Recipe → Recipe（相似菜品，基于食材重叠度）
```

**构建流程**：

1. 解析 323 个 Markdown 菜谱文件，提取食材列表和步骤文本
2. 生成 `nodes.csv`（323 菜谱 + 2906 食材 + 2514 烹饪步骤）和 `relationships.csv`（REQUIRES + CONTAINS_STEP + BELONGS_TO_CATEGORY）
3. 通过 Neo4j 的 `neo4j_import.cypher` 脚本执行 `LOAD CSV` 批量导入，建立索引和约束
4. 基于 Jaccard 相似度计算食材重叠，生成 SIMILAR 关系

**最终规模**：323 菜谱 / 2906 食材 / 2514 烹饪步骤 / 多种关系类型。

### 3.2 知识块生成

知识图谱中的结构化数据无法直接用于向量检索，需要将其转换为文本知识块。核心流程分为两步：**文档拼装**和**语义切割**。

#### 第一步：实时联动 Neo4j 拼装菜谱文本

系统不使用预先生成的静态文档，而是在启动时通过 Cypher 查询实时从 Neo4j 拼装每道菜谱的完整 Markdown 文本：

```cypher
-- 查询菜谱基本信息
MATCH (r:Recipe {nodeId: $recipe_id})
RETURN r.name, r.difficulty, r.cook_time

-- 查询所需食材
MATCH (r:Recipe)-[:REQUIRES]->(i:Ingredient)
RETURN i.name, i.type

-- 查询烹饪步骤
MATCH (r:Recipe)-[:CONTAINS_STEP]->(s:CookingStep)
RETURN s.step_number, s.description ORDER BY s.step_number
```

拼装后的 Markdown 文档示例：

```markdown
# 红烧肉

**难度**：中等 | **烹饪时间**：60分钟

## 食材
- 五花肉 500g
- 冰糖 30g
- 生抽 2勺
- 老抽 1勺

## 步骤
1. 五花肉切块，冷水下锅焯水
2. 锅中放冰糖，小火炒至焦糖色
3. ...
```

每篇文档同时携带 12 维元数据：`node_id`、`recipe_name`、`node_type`、`category`、`cuisine_type`、`difficulty`、`cook_time`、`doc_type`、`source`、`keywords`、`embedding_text`、`chunk_count`。

#### 第二步：按章节语义切割 + 重叠补全

对拼装好的菜谱文档执行三种切割策略：

| 策略 | 条件 | 方法 |
|------|------|------|
| 单块策略 | 文档 ≤500 字符 | 不切割，整篇作为一个知识块 |
| 滑窗策略 | 文档 >500 字符且无章节标记 | 以 500 字符为窗口滑动，窗口间重叠 50 字符 |
| 章节策略 | 文档 >500 字符且含 `\n## ` 章节标记 | 按 `\n## ` 切分为子段，每个子块开头补回章节标题 |

**重叠补全**：滑窗策略中 50 字符的重叠窗口确保上下文不丢失；章节策略中每个子块开头补回 `## ` 标题，保证子块可独立理解。

**子块元数据继承**：每个知识块在父文档 12 维元数据基础上，追加 5 维子块元数据：`chunk_id`、`parent_id`、`chunk_index`、`total_chunks`、`chunk_size`。

**最终规模**：323 篇菜谱文档 → 1138 个知识块。

### 3.3 向量索引构建（Milvus）

**嵌入模型**：BAAI/bge-small-zh-v1.5，512 维，本地部署，通过 HuggingFaceEmbeddings 加载。

**集合 Schema**（12 字段）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(150) | 主键，格式 `{node_id}_{chunk_index}` |
| vector | FLOAT_VECTOR(512) | BGE 嵌入向量 |
| text | VARCHAR(15000) | 知识块原文 |
| node_id | VARCHAR(100) | Neo4j 节点 ID（用于回查图谱） |
| recipe_name | VARCHAR(300) | 菜谱名称 |
| node_type | VARCHAR(100) | 节点类型 |
| category | VARCHAR(100) | 分类 |
| cuisine_type | VARCHAR(200) | 菜系 |
| difficulty | INT64 | 难度等级 |
| doc_type | VARCHAR(50) | 文档类型 |
| chunk_id | VARCHAR(150) | 知识块 ID |
| parent_id | VARCHAR(100) | 父文档 ID |

**索引参数**：

```
索引类型：HNSW
距离度量：COSINE
M：16（图连接数）
efConstruction：200（构建时搜索宽度）
ef：64（查询时搜索宽度）
一致性级别：Strong
```

**存算分离架构**：Milvus standalone 模式下，计算层（milvus-standalone）无状态，元数据层（milvus-etcd）管理集合/分段/索引配置，存储层（milvus-minio）持久化向量数据和 HNSW 索引文件。三者通过 Docker Compose 编排。

## 四、检索层：多路混合检索

### 4.1 检索策略总览

系统采用**线程池并行**执行两路检索，再通过 **Round-Robin 轮询**融合结果：

```
                    用户查询
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
    ┌──────────────┐      ┌──────────────┐
    │ 图双层检索    │      │ 向量增强检索  │     ← ThreadPoolExecutor 并行
    │ (线程 A)     │      │ (线程 B)     │
    └──────┬───────┘      └──────┬───────┘
           │                     │
           └──────────┬──────────┘
                      ▼
              Round-Robin 轮询融合
                      │
                      ▼
                 去重 + Top-K
```

### 4.2 图双层检索（dual_level_retrieval）

图双层检索利用 Neo4j 的图结构，从实体和主题两个维度检索：

**第一层 — 实体级检索**：

1. LLM 提取查询中的实体关键词（如"鸡蛋"→实体关键词 `["鸡蛋"]`，主题关键词 `["做法"]`）
2. 在 Neo4j 图索引中匹配实体节点（`Ingredient.name` 匹配）
3. 沿 `REQUIRES` 反向关系找到关联菜谱
4. 按 `relevance_score` 排序

**第二层 — 主题级检索**：

1. 使用主题关键词匹配 `Category` 节点和 `Recipe.keywords` 字段
2. 返回主题相关的菜谱集合
3. 按 `relevance_score` 排序

**双层融合**：合并实体级 + 主题级结果，按 `relevance_score` 降序去重，取 Top-K。

### 4.3 向量增强检索（vector_search_enhanced）

**第一步 — Milvus 语义检索**：

1. 用户查询经 BGE 嵌入为 512 维向量
2. Milvus HNSW 索引执行 COSINE 相似度检索，取 `top_k * 2` 条候选
3. 返回结果包含 `text`、`node_id`、`score` 等字段

**第二步 — Neo4j 1 跳邻居扩展**：

```cypher
MATCH (n {nodeId: $node_id})-[r]-(neighbor)
RETURN neighbor.name as name
LIMIT 3
```

对每个向量检索结果，通过 `node_id` 回查 Neo4j，获取该节点的 1 跳邻居信息（最多 3 个），追加到知识块文本中，增强上下文完整性。

### 4.4 Round-Robin 轮询融合

两路检索结果通过 Round-Robin 策略交替合并：

```python
for i in range(max(len(dual_docs), len(vector_docs))):
    # 先取图检索第 i 个
    if i < len(dual_docs):
        merged_docs.append(dual_docs[i])
    # 再取向量检索第 i 个
    if i < len(vector_docs):
        merged_docs.append(vector_docs[i])
```

**去重**：以 `node_id` 为唯一标识，已出现的节点跳过。

**分数统一**：图检索的 `relevance_score` 直接使用；向量检索的 COSINE 距离转换为相似度 `1.0 - distance`。

**最终输出**：取前 `top_k` 个作为检索结果送入生成层。

## 五、路由层：LLM 查询路由

### 5.1 查询分析

系统使用 LLM 对用户查询进行结构化分析，输出 JSON 格式的分析结果：

```json
{
    "query_complexity": 0.6,          // 查询复杂度 0-1
    "relationship_intensity": 0.8,    // 关系推理强度 0-1
    "reasoning_required": true,       // 是否需要推理
    "entity_count": 3,                // 实体数量
    "recommended_strategy": "graph_rag",  // 推荐策略
    "confidence": 0.85,               // 置信度
    "reasoning": "该查询涉及多个实体间的复杂关系，需要图结构推理"
}
```

**分析维度**：

- 查询复杂度：简单信息查找 vs 复杂关系推理
- 关系强度：是否涉及实体间关联（搭配、替代、对比）
- 推理需求：是否需要因果分析或多步推理
- 实体识别：查询中包含的明确实体数量和类型

### 5.2 策略路由

根据分析结果选择检索策略：

| 策略 | 适用场景 | 执行方法 |
|------|----------|----------|
| `hybrid_traditional` | 简单直接的信息查找 | `hybrid_search()`（图双层 + 向量增强） |
| `graph_rag` | 复杂关系推理和知识发现 | `graph_rag_search()`（纯图谱遍历） |
| `combined` | 两种策略结合 | `_combined_search()`（并行执行两种策略） |

**降级机制**：LLM 分析失败时，自动降级为基于规则的关键词匹配（检查"为什么""如何""关系""比较"等关键词），选择 `hybrid_traditional` 或 `graph_rag` 策略。检索异常时，降级为传统混合检索。

## 六、生成层：流式答案生成

### 6.1 提示词构建

检索结果按 `retrieval_level` 标注层级，拼装为上下文：

```
[ENTITY] 红烧肉 — 五花肉 500g，冰糖 30g...
[STEP] 1. 五花肉切块，冷水下锅焯水...
[TOPIC] 相似菜品：东坡肉、卤肉...

用户问题：红烧肉怎么做？
```

系统提示词定位为"专业烹饪助手"，要求基于检索信息回答，不编造知识。

### 6.2 流式生成

```python
response = client.chat.completions.create(
    model=model_name,
    messages=[{"role": "user", "content": prompt}],
    stream=True,
    timeout=60
)

for chunk in response:
    if chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content  # 逐 token 产出
```

**重试机制**：流式生成支持最多 3 次重试，递增等待时间（2s → 4s → 6s）。所有重试失败后，降级为非流式生成作为后备。

## 七、服务层：Flask Web 服务

### 7.1 SSE 流式推送

后端通过 Server-Sent Events (SSE) 向前端推送数据，每个 SSE 事件格式为 `data: {json}\n\n`。

### 7.2 分阶段状态反馈

由于检索阶段（LLM 查询分析 + 三路并行检索）需要约 12-15 秒，期间无内容输出。系统通过后台线程执行检索，主线程按时间节点推送阶段性状态事件：

```
时间轴：
[  2s] cache_check    ⚡ 正在检查语义缓存...
[  2s] analyzing      🧠 正在分析问题...
[  7s] retrieving     📚 正在三路混合检索...
[ 13s] generating     ✍️ 正在生成回答...
[ 16s] CHUNK #1       ← 首个 token 开始流式输出
[ 76s] DONE           ← 1686 个内容块输出完毕
```

**实现机制**：

1. 发送 `cache_check` 状态后执行语义缓存查询
2. 缓存未命中，发送 `analyzing` 状态
3. 启动后台线程执行 `route_query`（含 LLM 分析 + 混合检索）
4. 主线程 `join(timeout=5)` 等待 5 秒后发送 `retrieving` 状态
5. 线程完成后发送 `generating` 状态
6. 进入流式生成，逐块 yield 内容

### 7.3 语义缓存

系统维护基于会话的语义缓存：对用户查询进行 BGE 嵌入，与缓存库中的历史查询计算 COSINE 相似度。相似度超过阈值（如 0.92）时直接返回缓存的答案，跳过检索和生成阶段，实现秒级响应。

### 7.4 多轮上下文

系统维护会话级别的对话历史，将前 N 轮问答作为上下文注入当前查询的提示词中，实现多轮对话的上下文连贯。

## 八、前端层：Next.js 交互

### 8.1 SSE 流式接收

前端通过 `fetch` + `ReadableStream.getReader()` 实现真流式接收：

```typescript
const response = await fetch('/api/chat/stream', { ... });
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    // 解析 SSE 事件，yield 内容块或状态标记
}
```

### 8.2 状态事件分流

前端解析 SSE 事件时区分**状态事件**和**内容事件**：

```
SSE 事件 → parsed.status ? yield "__STATUS__:xxx" : yield parsed.chunk
                ↓                              ↓
        setStreamStatus(status)         fullResponse += chunk
                ↓                              ↓
        ChatMessage 显示状态文本      updateMessage 更新消息内容
```

### 8.3 状态文本映射

```typescript
const statusTextMap: Record<string, string> = {
    cache_check: '⚡ 正在检查语义缓存...',
    analyzing:   '🧠 正在分析问题...',
    retrieving:  '📚 正在三路混合检索...',
    generating:  '✍️ 正在生成回答...',
    searching:   '🔍 正在检索知识库...'
};
```

当 `streamStatus` 有值时显示对应状态文本，流式内容开始后状态自动清除。

## 九、部署架构

### 9.1 Docker 容器拓扑

```
┌──────────────────────────────────────────────────┐
│                  Docker Desktop                  │
│                                                  │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  neo4j-db    │    │  milvus-standalone   │   │
│  │  (7474/7687) │    │  (19530)             │   │
│  │              │    │                      │   │
│  │  数据卷:      │    │  ┌────────────────┐ │   │
│  │  /data       │    │  │ milvus-etcd    │ │   │
│  │  /import ← CSV│   │  │ (2379) 元数据   │ │   │
│  └──────────────┘    │  └────────────────┘ │   │
│                      │  ┌────────────────┐ │   │
│                      │  │ milvus-minio   │ │   │
│                      │  │ (9002 S3 API)  │ │   │
│                      │  │ (9003 Console) │ │   │
│                      │  └────────────────┘ │   │
│                      └──────────────────────┘   │
└──────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│ Flask 后端 8001 │  │ Next.js 3000    │
│ (conda env)     │  │ (npm run dev)   │
└─────────────────┘  └─────────────────┘
```

### 9.2 数据持久化

| 组件 | 持久化路径 | 内容 |
|------|-----------|------|
| Neo4j | `volumes/neo4j/data/` | 图数据（节点、关系、索引） |
| Milvus etcd | `volumes/etcd/` | 集合/分段/节点状态元数据 |
| Milvus standalone | `volumes/milvus/` | RocksDB 索引配置/分段元数据 |
| MinIO | `volumes/minio/` | 向量数据 + HNSW 索引文件 |

### 9.3 关键镜像版本

| 组件 | 镜像 | 版本 |
|------|------|------|
| Neo4j | neo4j | 5.18 |
| Milvus | milvusdb/milvus | v2.5.11 |
| etcd | quay.io/coreos/etcd | v3.5.18 |
| MinIO | minio/minio | RELEASE.2023-03-20T20-16-18Z |

## 十、项目成果

### 10.1 数据规模

| 指标 | 数值 |
|------|------|
| 菜谱数量 | 323 道 |
| 食材节点 | 2906 个 |
| 烹饪步骤 | 2514 个 |
| 知识块数量 | 1138 个 |
| 嵌入维度 | 512 维 |
| HNSW 索引大小 | ~2.4 MB |

### 10.2 检索效果

以查询"需要鸡蛋的菜"为例：

| 检索路径 | 延迟 | 结果 |
|----------|------|------|
| 图双层检索 | ~200ms | 实体匹配"鸡蛋"→REQUIRES反向→关联菜谱 |
| 向量增强检索 | ~481ms | Milvus 语义检索 Top5 + 1跳邻居扩展 |
| Round-Robin 融合 | ~600ms | 两路交替合并去重 |

以查询"红烧肉怎么做"为例：

| 检索路径 | 延迟 | 结果 |
|----------|------|------|
| 图双层检索 | ~180ms | 实体匹配"红烧肉"→完整步骤 |
| 向量增强检索 | ~334ms | 语义聚类 Top5（红烧肉变体 + 回锅肉） |
| Round-Robin 融合 | ~500ms | 步骤完整 + 相似菜品推荐 |

### 10.3 端到端性能

| 指标 | 数值 |
|------|------|
| 首个状态反馈 | ~2s |
| 检索完成 | ~12s |
| 首 token 延迟 | ~16s |
| 完整回答 | ~76s（1686 个内容块） |
| 语义缓存命中 | ~2s |

### 10.4 系统特点

1. **一源三法**：同一批 1138 知识块，分别以图结构（Neo4j）、向量表示（Milvus）、词项统计（BM25）三种方式索引，发挥各自优势
2. **实时拼装**：菜谱文档非静态预生成，而是启动时实时 Cypher 查询拼装，保证与图谱数据一致
3. **语义切割 + 重叠补全**：按章节切分 + 50 字符重叠窗口 + 子块标题补回，确保知识块上下文完整性
4. **LLM 动态路由**：根据查询复杂度、关系强度、推理需求自动选择检索策略，避免一刀切
5. **分阶段状态反馈**：后台线程执行阻塞检索，主线程按时间节点推送 4 个阶段状态，消除用户等待焦虑
6. **全链路真流式**：LLM `stream=True` → Flask `yield` SSE → 前端 `getReader()` 逐块渲染，无缓冲堆积
7. **存算分离**：Milvus standalone 模式下计算无状态、元数据独立、存储可替换，支持弹性扩展
