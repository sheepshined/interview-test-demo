# AI 模拟面试官 — Code Wiki

> 本文档为 **AI 模拟面试官** 项目的结构化代码知识库，涵盖项目整体架构、模块职责、关键类与函数说明、依赖关系及运行方式等关键信息。
>
> - 技术栈：Python 3 + FastAPI + LangChain + ChromaDB（后端）；Vue 3 + Vite + Pinia（前端）
> - 核心能力：简历解析 → 岗位匹配 → 混合检索出题 → LLM 流式面试 → 四维度评分 → 追问决策 → 综合评价报告

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [后端模块详解](#4-后端模块详解)
   - 4.1 [全局配置 config.py](#41-全局配置-configpy)
   - 4.2 [服务入口 server.py（FastAPI）](#42-服务入口-serverpyfastapi)
   - 4.3 [CLI 入口 main.py](#43-cli-入口-mainpy)
   - 4.4 [Agent 模块（面试引擎核心）](#44-agent-模块面试引擎核心)
   - 4.5 [Retrieval 模块（混合检索）](#45-retrieval-模块混合检索)
   - 4.6 [Resume 模块（简历解析）](#46-resume-模块简历解析)
   - 4.7 [题库数据格式](#47-题库数据格式)
5. [前端模块详解](#5-前端模块详解)
6. [关键流程详解](#6-关键流程详解)
7. [依赖关系](#7-依赖关系)
8. [项目运行方式](#8-项目运行方式)
9. [配置说明](#9-配置说明)
10. [WebSocket 流式协议](#10-websocket-流式协议)

---

## 1. 项目概述

**AI 模拟面试官** 是一个面向应届生的智能模拟面试平台。系统通过两种入口（上传简历自动匹配岗位 / 自主选择岗位）启动一场模拟面试，面试过程中 AI 面试官会基于本地题库出题、对候选人回答进行四维度评分，并根据得分决定是否追问，最终生成一份结构化的综合评价报告。

### 核心特性

| 特性 | 说明 |
|------|------|
| **LangChain LCEL 架构** | 使用 LangChain Expression Language 声明式编排出题、评分、追问、总结四条 Chain |
| **混合检索（BM25 + 向量）** | 双路检索 + Reciprocal Rank Fusion（RRF）融合排序，兼顾关键词匹配与语义相似 |
| **流式输出** | 后端 LLM 流式生成，前端 WebSocket 实时推送逐字显示 |
| **简历智能解析** | pdfplumber 提取文本 + 正则提取联系方式 + LLM 提取结构化信息，规则兜底 |
| **岗位智能匹配** | 根据简历技能与岗位 tag 匹配度推荐最合适岗位 |
| **四维度评分** | 准确性 / 完整性 / 深度 / 清晰度，Pydantic 结构化输出 + 健壮容错解析 |
| **上下文压缩** | 对话超过阈值时自动调用 LLM 将旧消息压缩为摘要（ConversationSummaryBuffer 模式） |
| **双入口** | 同时提供 Web（FastAPI + WebSocket）与 CLI（终端流式）两种使用方式 |

---

## 2. 整体架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        浏览器（前端 SPA）                          │
│   Vue 3 + Vite + Pinia + Vue Router                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│   │ 登录/首页 │  │ 简历上传  │  │ 岗位匹配  │  │ 面试/总结页面 │    │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└───────────┬───────────────────────────────────┬─────────────────┘
            │ HTTP /api/*                       │ WebSocket /ws/chat
            ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端 FastAPI 服务                           │
│  server.py                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ REST 接口    │  │ 文件上传     │  │ WebSocket 流式面试        │  │
│  │ login/config│  │ resume PDF  │  │ config/answer/report     │  │
│  │ roles/parse │  │             │  │ ws_stream_generator       │  │
│  └─────────────┘  └─────────────┘  └──────────┬───────────────┘  │
└────────────────────────────────────────────────┼─────────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent 模块（面试引擎核心）                      │
│  agent/engine.py — InterviewEngine 状态机编排器                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ 出题 Chain│  │ 评分 Chain│  │ 追问 Chain│  │ 总结 Chain│         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │ LCEL        │ LCEL        │ LCEL        │ LCEL            │
│  ┌────┴─────────────┴────────────┴────────────┴─────┐           │
│  │ agent/memory.py  InterviewMemory（对话记忆+压缩） │           │
│  │ agent/tools.py   LangChain @tool 检索工具         │           │
│  │ agent/prompts.py ChatPromptTemplate 提示词模板    │           │
│  │ agent/models.py  Pydantic 结构化输出模型          │           │
│  └───────────────────────┬─────────────────────────┘           │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Retrieval 模块（混合检索） + Resume 模块             │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐  │
│  │ HybridRetriever         │    │ resume/parser.py            │  │
│  │  • BM25 (jieba 分词)     │    │  • pdfplumber 文本提取       │  │
│  │  • Chroma 向量检索       │    │  • 正则提取联系方式          │  │
│  │  • RRF 融合排序          │    │  • LLM 提取结构化信息        │  │
│  └───────────┬─────────────┘    │  • 规则兜底                  │  │
│              │                   └─────────────────────────────┘  │
└──────────────┼────────────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────┐   ┌──────────────────────────┐
│  ChromaDB（本地持久化向量库）      │   │  外部 LLM API             │
│  • BGE bge-base-zh-v1.5 嵌入模型  │   │  DeepSeek / 智谱 GLM      │
│  • collection: interview_questions│   │  (OpenAI 兼容接口)         │
└──────────────────────────────────┘   └──────────────────────────┘
```

### 2.2 后端分层架构

项目后端采用清晰的分层架构，依赖方向自上而下：

```
表现层（server.py / main.py）
    │
    ▼
业务编排层（agent/engine.py — InterviewEngine）
    │
    ├──► LangChain Chain 层（agent/chains.py）
    │        │
    │        ▼
    │    提示词层（agent/prompts.py）+ 数据模型层（agent/models.py）
    │
    ├──► 记忆层（agent/memory.py）
    │
    ├──► 工具层（agent/tools.py）──► 检索层（retrieval/retriever.py）
    │                                    │
    │                                    ▼
    │                              向量库（ChromaDB + BGE）
    │
    └──► 简历解析层（resume/parser.py ─► resume/llm_parser.py）
                 │
                 ▼
           LLM 工厂（agent/llm.py）
                 │
                 ▼
           外部 LLM API（DeepSeek / 智谱 GLM）
```

### 2.3 前端架构

前端为标准 Vue 3 SPA，采用组合式 API（`<script setup>`）：

```
main.js（应用入口，挂载 Pinia + Router）
  │
  ├── App.vue（根组件，仅 <router-view />）
  │
  ├── router/index.js（路由表，7 个懒加载视图）
  │
  ├── views/（页面级组件）
  │     ├── LoginView.vue       登录页（一键进入）
  │     ├── HomeView.vue        首页（选择面试方式）
  │     ├── ResumeUploadView.vue 简历上传/粘贴解析
  │     ├── JobMatchingView.vue  简历匹配岗位结果
  │     ├── ChooseJobView.vue    自主选择岗位配置
  │     ├── InterviewView.vue    面试对话主界面（WebSocket）
  │     └── SummaryView.vue      面试总结报告
  │
  ├── components/（通用组件）
  │     ├── TopNav.vue          顶部导航栏
  │     └── DSIcon.vue          SVG 图标组件（内置 30+ 图标）
  │
  ├── composables/
  │     └── useWebSocket.js     WebSocket 连接与消息处理组合式函数
  │
  ├── api/index.js              REST API 封装（fetch）
  │
  └── styles/
        ├── design-tokens.css   设计令牌（CSS 变量：颜色/字体/圆角/阴影）
        └── global.css          全局样式与 .ds-* 工具类
```

---

## 3. 目录结构

```
workspace/
├── backend/                          # Python 后端
│   ├── agent/                        # 面试引擎核心模块
│   │   ├── __init__.py
│   │   ├── chains.py                 # LangChain LCEL Chain 定义
│   │   ├── engine.py                 # 面试引擎状态机编排器（核心）
│   │   ├── llm.py                    # LLM / Embeddings 工厂
│   │   ├── memory.py                 # 对话记忆管理（带压缩）
│   │   ├── models.py                 # Pydantic 结构化数据模型
│   │   ├── prompts.py                # ChatPromptTemplate 提示词
│   │   ├── tools.py                  # LangChain @tool 检索工具
│   │   └── interview_records_*.md    # 面试过程记录（运行时生成）
│   ├── data/                         # 题库源文件（Markdown）
│   │   ├── python_dev.md
│   │   ├── java_dev.md
│   │   ├── frontend_dev.md
│   │   ├── product_manager.md
│   │   └── general_hr.md
│   ├── reports/                      # 生成的面试报告
│   │   └── interview_report.md
│   ├── resume/                       # 简历解析模块
│   │   ├── __init__.py
│   │   ├── llm_parser.py             # LLM 结构化提取
│   │   ├── models.py                 # ResumeInfo 数据模型
│   │   └── parser.py                 # PDF 解析主入口 + 规则兜底
│   ├── retrieval/                    # 检索模块
│   │   ├── __init__.py
│   │   ├── kb_builder.py             # 离线知识库构建器
│   │   └── retriever.py              # 混合检索器（BM25+向量+RRF）
│   ├── .env.example                  # 环境变量示例
│   ├── config.py                     # 全局配置
│   ├── main.py                       # CLI 入口
│   ├── requirements.txt              # Python 依赖
│   └── server.py                     # FastAPI 服务入口
├── frontend/                         # Vue 3 前端
│   ├── public/                       # 静态资源
│   │   ├── assets/hero-interview.jpg
│   │   └── icons/*.svg               # 30+ SVG 图标
│   ├── src/
│   │   ├── api/index.js              # REST API 封装
│   │   ├── components/
│   │   │   ├── DSIcon.vue            # SVG 图标组件
│   │   │   └── TopNav.vue            # 顶部导航
│   │   ├── composables/
│   │   │   └── useWebSocket.js       # WebSocket 组合式函数
│   │   ├── router/index.js           # 路由配置
│   │   ├── styles/
│   │   │   ├── design-tokens.css     # 设计令牌
│   │   │   └── global.css            # 全局样式
│   │   ├── views/                    # 7 个页面视图
│   │   ├── App.vue                   # 根组件
│   │   └── main.js                   # 应用入口
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js                # Vite 配置（含代理）
└── .gitignore
```

---

## 4. 后端模块详解

### 4.1 全局配置 config.py

[config.py](file:///workspace/backend/config.py) 是整个后端的配置中枢，从 `.env` 文件加载敏感信息（API Key），不硬编码。

#### 关键配置项

| 配置类别 | 配置项 | 说明 |
|---------|--------|------|
| **路径配置** | `BASE_DIR` / `DATA_DIR` / `CHROMA_DB_PATH` / `REPORTS_DIR` / `UPLOADS_DIR` | 项目根、题库、向量库、报告、上传目录 |
| **分块参数** | `CHUNK_SIZE=500` / `OVERLAP=50` | 文本分块大小与重叠 |
| **检索参数** | `TOP_K=5` / `BM25_WEIGHT=0.4` / `VECTOR_WEIGHT=0.6` / `RRF_K=60` | 检索数量、双路权重、RRF 融合参数 |
| **嵌入模型** | `EMBEDDING_MODEL_PATH` | 本地 BGE bge-base-zh-v1.5 模型路径（从环境变量读取） |
| **LLM 配置** | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TEMPERATURE=0.7` | DeepSeek API 配置 |
| **Memory 配置** | `MEMORY_WINDOW_SIZE=10` / `MEMORY_COMPRESS_THRESHOLD=6000` | 保留消息数、压缩触发字符阈值 |
| **面试角色** | `ROLES` | 5 个岗位配置（python/java/frontend/product/general_hr），每个含 title/tags/file |
| **评分维度** | `SCORE_DIMENSIONS` | `["accuracy", "completeness", "depth", "clarity"]` |

#### ROLES 配置示例

```python
ROLES = {
    "python_dev": {
        "title": "Python 开发工程师",
        "tags": ["Python", "Django", "Flask", "FastAPI", "数据库", "异步编程"],
        "file": "python_dev.md",
    },
    # ... java_dev / frontend_dev / product_manager / general_hr
}
```

> `tags` 字段用于简历技能匹配：简历技能与岗位 tag 的子串匹配数越多，匹配度越高。

---

### 4.2 服务入口 server.py（FastAPI）

[server.py](file:///workspace/backend/server.py) 提供 Web 服务，是前后端联调的主入口，基于 FastAPI 实现，支持 REST API + WebSocket 流式推送。

#### REST API 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/login` | 登录认证（admin / 123123，返回 MD5 token） |
| POST | `/api/config` | 配置面试参数，返回岗位/分类/难度信息 |
| GET | `/api/roles` | 获取所有可选岗位列表 |
| POST | `/api/resume/parse-text` | 解析粘贴的文本简历（关键词匹配技能） |
| POST | `/api/upload/resume` | 上传并解析 PDF 简历（含岗位匹配） |
| GET | `/` 或 `/index.html` | 静态前端页面（需将前端放入 static/） |

#### WebSocket 接口

`@app.websocket("/ws/chat")` 是面试对话的核心通道，支持三种消息类型：`config`（配置并出第一题）、`answer`（回答→评分→决策→追问/下一题）、`report`（生成总结报告）。

#### 关键组件

**`get_retriever()`**：懒加载单例 `HybridRetriever`，避免重复初始化向量模型。

**`ws_stream_generator(ws, gen, stream_type)`**：WebSocket 流式推送辅助函数，将 generator 的输出封装为 `stream_start` → `stream_chunk` → `stream_end` 三段式消息协议。

**Pydantic 请求模型**：

| 模型 | 字段 |
|------|------|
| `LoginRequest` | `username`, `password` |
| `InterviewConfig` | `role`, `question_count`, `difficulty`, `resume_context`, `resume_skills` |
| `ConfigResponse` | `success`, `message`, `role_key`, `role_title`, `difficulty_label`, `categories` 等 |
| `TextResumeRequest` | `content` |

---

### 4.3 CLI 入口 main.py

[main.py](file:///workspace/backend/main.py) 提供命令行交互式面试入口，支持三个子命令：

| 命令 | 功能 |
|------|------|
| `python main.py build` | 离线建库（题库更新后执行一次） |
| `python main.py chat` | 启动模拟面试（流式输出） |
| `python main.py rebuild` | 清空旧向量库并重建 |

#### CLI 面试流程

1. 选择启动方式：手动选岗位 / 上传简历自动匹配
2. 若选简历路径：`parse_resume()` 解析 → 展示解析结果 → 按技能匹配度排序岗位 → 确认推荐或手动选
3. 配置题量（默认 5）与难度（1/2/3，默认 2）
4. 初始化 `InterviewEngine`，调用 `configure()` 后流式输出第一题
5. 主循环：接收用户输入 → `quit` 结束出报告 / `skip` 换题 / 正常回答 → 评分 → 决策 → 追问或下一题

`stream_print()` 函数将 generator 的逐块输出实时打印到终端。

---

### 4.4 Agent 模块（面试引擎核心）

Agent 模块是整个系统的大脑，使用 LangChain LCEL 架构编排完整面试流程。

#### 4.4.1 engine.py — 面试引擎编排器

[agent/engine.py](file:///workspace/backend/agent/engine.py) 中的 `InterviewEngine` 是核心状态机编排器。

##### 状态机（Phase）

```
CONFIG → ASKING → RETRIEVED → SCORED → DECIDED → (FOLLOWUP | NEXT | SUMMARY)
```

| 阶段 | 说明 |
|------|------|
| `CONFIG` | 配置面试参数 |
| `ASKING` | 出题阶段 |
| `RETRIEVED` | 已检索标准答案 |
| `SCORED` | 已评分 |
| `DECIDED` | 已决策 |
| `FOLLOWUP` | 追问阶段 |
| `SUMMARY` | 生成总结报告 |

##### `InterviewEngine` 类

```python
class InterviewEngine:
    def __init__(self, retriever: HybridRetriever, llm: BaseChatModel = None)
```

**核心属性**：
- `retriever`：混合检索器实例
- `llm`：LangChain ChatModel（默认通过 `get_llm()` 获取）
- `memory`：`InterviewMemory` 对话记忆
- `tools`：LangChain 工具集
- 四条 LCEL Chain：`_question_chain` / `_scoring_chain` / `_followup_chain` / `_summary_chain`
- 面试状态：`role_key`、`difficulty`、`total_count`、`asked_ids`、`records`、`current_question` 等

##### 关键方法

| 方法 | 阶段 | 说明 |
|------|------|------|
| `configure(role_key, total_count, difficulty, resume_context, resume_skills)` | CONFIG | 配置参数，重置状态，初始化 .md 记录文件 |
| `_get_filtered_resume_skills()` | - | 过滤简历技能，只保留与当前岗位 tag 相关的，防止跨岗位出题 |
| `_select_topic_for_search()` | - | 选择搜索话题（随机抽取 2-3 个相关技能/tag），引入随机性避免重复 |
| `_select_preferred_category()` | - | 选择下一个优先分类，实现分类轮换 |
| `_prepare_question()` | ASKING | 出题准备：混合检索候选题 → 优先未问过的分类 → 构建 Chain 输入字典 |
| `generate_question_stream()` | ASKING | **流式生成面试题（generator）**，逐块 yield 文本 |
| `receive_answer(user_answer)` | RETRIEVED | 接收回答，存入 memory，检索标准答案，触发上下文压缩 |
| `score_answer()` | SCORED | 调用 scoring_chain 评分，返回带四维度细分的评分记录 |
| `decide()` | DECIDED | 决策：题量满→end；得分<5 且未追问过→followup；否则→next |
| `_prepare_followup(missed_topic)` | FOLLOWUP | 检索相关知识，构建追问 Chain 输入 |
| `generate_followup_stream(missed_topic)` | FOLLOWUP | **流式生成追问（generator）** |
| `_prepare_summary()` | SUMMARY | 统计数据，构建结构化报告文本 + AI 分析输入 |
| `generate_summary_stream()` | SUMMARY | **流式生成综合评价报告**：先输出结构化数据，再流式输出 AI 分析，保存到文件 |

##### 决策逻辑（`decide()`）

```python
def decide(self) -> Dict:
    if self.main_question_count >= self.total_count:
        return {"action": "end", "reason": f"已完成 {self.total_count} 道题"}
    if self.followup_count == 0 and last_score < 5:
        # 得分低于 5 且本轮未追问过 → 追问
        return {"action": "followup", "followup_topic": missed[0]}
    # 否则继续下一题
    return {"action": "next"}
```

##### 记录持久化

- `_append_to_md(record)`：每条回答立即追加到 `interview_records_{timestamp}.md` 文件
- `generate_summary_stream()` 末尾将完整报告保存到 `reports/interview_report.md`

#### 4.4.2 chains.py — LCEL Chain 定义

[agent/chains.py](file:///workspace/backend/agent/chains.py) 使用 LangChain Expression Language（LCEL）声明式构建四条 Chain + 一条压缩 Chain。

##### Chain 一览

| Chain 工厂函数 | 组成 | 输入参数 |
|---------------|------|---------|
| `build_question_chain(llm)` | `question_prompt \| llm \| StrOutputParser()` | role_title, difficulty_label, question_index, total_count, question_text, resume_section, history |
| `build_scoring_chain(llm)` | `scorer_prompt \| llm \| StrOutputParser() \| parse_score` | question, standard_answer, scoring_points, candidate_answer, format_instructions |
| `build_followup_chain(llm)` | `followup_prompt \| llm \| StrOutputParser()` | current_question, missed_topic, reference_knowledge, history |
| `build_summary_chain(llm)` | `summary_prompt \| llm \| StrOutputParser()` | role_title, difficulty_label, avg_score, total_questions, high/low_score_count, score_details |

> LCEL 优势：声明式组合、原生支持流式/异步/重试、可观测性（LangSmith 追踪）。

##### `RobustScoreParser` — 健壮的评分输出解析器

这是系统的容错核心，五级降级策略确保评分解析的鲁棒性：

1. 剥离 markdown 代码块（` ```json ... ``` `）
2. 尝试直接 `json.loads()`
3. 正则提取最外层花括号内容
4. **平衡花括号匹配**（`_balanced_json_extract`，处理嵌套 JSON 与字符串内的括号）
5. 从文本中正则提取分数（`_extract_score_from_text`，匹配 `"score": N` / `得分：N` / `N/10` 等模式）

最终全部失败返回 `_default_result()`（零分）。

##### `get_format_instructions()`

返回 `PydanticOutputParser(ScoreResult)` 的格式指令字符串，注入到 scorer_prompt 中，引导 LLM 输出结构化 JSON。

#### 4.4.3 llm.py — LLM / Embeddings 工厂

[agent/llm.py](file:///workspace/backend/agent/llm.py) 封装底层模型创建。

| 函数 | 说明 |
|------|------|
| `get_llm(temperature, max_tokens, model)` | 创建 `ChatOpenAI` 实例，兼容智谱 GLM / DeepSeek / OpenAI 接口；未配置 API Key 抛 `ValueError` |
| `get_embeddings()` | `@lru_cache(maxsize=1)` 装饰，全局只加载一次 `HuggingFaceEmbeddings`（本地 BGE 模型） |

> 使用 `lru_cache` 确保嵌入模型全局单例，避免重复加载大模型（BGE 模型加载耗时较长）。

#### 4.4.4 memory.py — 对话记忆管理

[agent/memory.py](file:///workspace/backend/agent/memory.py) 的 `InterviewMemory` 实现基于摘要的上下文压缩（ConversationSummaryBuffer 模式）。

##### 核心能力

1. 存储面试对话消息（Human/AI/System）
2. 超过阈值时自动压缩旧消息为摘要
3. 提供 history 参数供 LCEL Chain 使用

##### 关键方法

| 方法 | 说明 |
|------|------|
| `add_user_message(content)` / `add_ai_message(content)` / `add_system_message(content)` | 添加消息 |
| `get_history_for_chain()` | 返回最近 `window_size` 条消息，若有摘要则前置一条 SystemMessage |
| `get_total_chars()` | 计算所有消息总字符数 |
| `maybe_compress()` | **核心压缩逻辑**：超过 `threshold` 时，保留最近 `window_size` 条，旧消息发给 LLM 生成摘要，用「摘要 + 最近消息」重建历史 |
| `clear()` | 清空所有记忆 |

##### 压缩策略

```python
def maybe_compress(self):
    total = self.get_total_chars()
    if total < self.threshold:    # 默认 6000 字符
        return
    # 分割: 旧消息 → 压缩; 最近 window_size 条 → 保留
    old_msgs = all_msgs[:split]
    recent_msgs = all_msgs[split:]
    # 调用 compress_prompt | llm 生成摘要
    chain = compress_prompt | self.llm
    self.summary = chain.invoke({"conversation_text": old_text}).content
    # 用摘要 + 最近消息重建历史
    self.history = InMemoryChatMessageHistory()
    for m in recent_msgs:
        self.history.add_message(m)
```

#### 4.4.5 models.py — Pydantic 数据模型

[agent/models.py](file:///workspace/backend/agent/models.py) 定义结构化输出模型，用于 LangChain PydanticOutputParser。

| 模型 | 说明 |
|------|------|
| `ScoreBreakdown` | 四维度评分细分：accuracy / completeness / depth / clarity（各 1-10） |
| `ScoreResult` | LLM 评分结果：score, max_score, score_breakdown, hit_points, missed_points, feedback, is_correct；含 `to_record()` 转字典 |
| `InterviewAction` | 决策动作枚举：NEXT / FOLLOWUP / END |
| `DecisionResult` | 决策结果：action, reason, followup_topic |
| `QuestionCandidate` | 候选题目：id, question, category, difficulty, score |

#### 4.4.6 prompts.py — 提示词模板

[agent/prompts.py](file:///workspace/backend/agent/prompts.py) 统一使用 `ChatPromptTemplate` 管理所有提示词，便于版本控制和 A/B 测试。

| 模板 | 用途 | 关键约束 |
|------|------|---------|
| `question_prompt` | 出题 | 自然面试官口吻、题目核心技术必须来自题库、无简历时禁止提简历 |
| `scorer_prompt` | 评分 | 四维度评分标准、hit_points 禁止编造、feedback 基于实际回答 |
| `followup_prompt` | 追问 | 只输出一句话、有技术深度、语气自然 |
| `summary_prompt` | 总结 | 总体评价/优势/不足/学习方向/面试结论，Markdown 格式 |
| `compress_prompt` | 对话压缩 | 压缩为不超过 200 字摘要 |

出题与追问 Chain 使用 `MessagesPlaceholder(variable_name="history")` 注入对话历史；总结 Chain 使用独立上下文（不继承历史）。

#### 4.4.7 tools.py — LangChain 工具

[agent/tools.py](file:///workspace/backend/agent/tools.py) 使用 `@tool` 装饰器将检索器操作封装为 LangChain Tool。

| Tool | 功能 |
|------|------|
| `search_question(topic, role, difficulty, exclude_ids, top_k)` | 混合检索面试题，返回 JSON |
| `get_standard_answer(question_id)` | 按题号获取标准答案与得分点 |
| `get_categories(role)` | 获取岗位分类列表 |
| `get_random_question(role, difficulty, exclude_ids)` | 随机抽题（语义检索无结果时兜底） |

`create_tools(retriever)` 工厂函数返回绑定到特定检索器的工具列表，可被 LangChain Agent 调用，也可被 `InterviewEngine` 直接调用。

---

### 4.5 Retrieval 模块（混合检索）

#### 4.5.1 retriever.py — 混合检索器

[retrieval/retriever.py](file:///workspace/backend/retrieval/retriever.py) 的 `HybridRetriever` 是检索核心，实现 BM25 + 向量双路检索 + RRF 融合。

##### 核心组件

- `langchain_chroma.Chroma` → 向量检索
- `langchain_community.retrievers.BM25Retriever` → 关键词检索
- `jieba` 中文分词 → BM25 预处理
- RRF 融合算法 → 双路结果合并

##### 关键方法

| 方法 | 阶段 | 说明 |
|------|------|------|
| `_get_all_documents(role)` | - | 从 Chroma 底层 collection 获取所有文档（按 role 过滤），确保 ID 存入 metadata |
| `_get_bm25_retriever(role)` | - | 获取或创建指定 role 的 BM25 检索器（带缓存） |
| `_build_where_filter(role, difficulty)` | - | 构建 ChromaDB where 过滤条件（多条件用 `$and` 组合） |
| `_vector_search(topic, role, difficulty, top_k)` | 出题 | 向量相似度检索，返回 `(doc_id, page_content, metadata, distance)` 元组列表 |
| `_reciprocal_rank_fusion(...)` | 出题 | **RRF 融合算法**：`score(d) = Σ weight / (k + rank(d))` |
| `get_question(topic, role, category, difficulty, exclude_ids, top_k)` | 出题 | **出题阶段公共接口**：双路检索 + RRF 融合 + category 过滤 |
| `get_answer(question_id)` | 评分 | **评分阶段**：按题号精确检索标准答案 + 得分点 |
| `get_categories(role)` | - | 获取某岗位所有分类 |
| `get_random_question(role, difficulty, exclude_ids)` | 出题 | 随机抽一题（兜底） |

##### RRF 融合公式

```
score(d) = Σ  weight / (RRF_K + rank(d) + 1)

向量检索结果: weight = VECTOR_WEIGHT (0.6)
BM25 检索结果: weight = BM25_WEIGHT  (0.4)
RRF_K = 60
```

> 出题阶段只检索题目文本（不含答案，避免答案泄漏）；评分阶段按题号精确取答案与得分点。

##### 设计亮点

- BM25 检索器按 role 缓存（`_bm25_cache`），避免重复构建
- 使用 Chroma 底层 `_collection` 直接查询，确保文档 ID 可用
- 向量检索返回 `top_k * 3` 候选，给 RRF 融合更多选择空间

#### 4.5.2 kb_builder.py — 离线知识库构建器

[retrieval/kb_builder.py](file:///workspace/backend/retrieval/kb_builder.py) 的 `KnowledgeBaseBuilder` 负责离线建库。

##### 题库解析

`parse_questions_from_file(filepath)` 解析单个 .md 题库文件：

1. 按 `\n---\n` 分割每道题
2. 正则提取元信息注释：`<!-- id:xxx | category:xxx | difficulty:x | difficulty_label:xxx -->`
3. 正则提取 `### Q:` / `### A:` / `### S:` 三段（题目/答案/得分点）
4. 得分点解析为列表

##### 建库流程（`build()`）

```
[1/3] 解析面试题库 → load_all_questions() 遍历 data/*.md
[2/3] 加载 BGE 模型 + 创建 ChromaDB（force_recreate 时先删除旧集合）
[3/3] 构建 LangChain Document 列表 → Chroma.from_documents() 批量写入
```

##### Document 存储设计

```python
Document(
    page_content=q["question"],          # 检索键 = 题目文本（不含答案）
    metadata={
        "source_file", "role", "category", "difficulty", "difficulty_label",
        "answer": q["answer"],            # 答案存在 metadata
        "scoring_points": "||".join(...), # 得分点用 || 连接
        "max_score": 10,
    },
)
```

> 关键设计：**检索键只用题目文本，答案与得分点存在 metadata**，避免答案在检索阶段泄漏，评分阶段通过 `get_answer(id)` 精确取出。

---

### 4.6 Resume 模块（简历解析）

#### 4.6.1 parser.py — PDF 解析主入口

[resume/parser.py](file:///workspace/backend/resume/parser.py) 采用混合解析策略：

```
1. pdfplumber 提取原始文本（确定性）
2. 正则提取 phone/email/location（确定性，可靠）
3. LLM 提取 name/skills/experience/projects/education/summary（语义理解，普适）
4. LLM 失败时回退到规则提取（兜底）
```

##### 核心函数

| 函数 | 说明 |
|------|------|
| `parse_resume(pdf_path)` | **主入口**：返回结构化字典（raw_text/summary/skills/name/phone/email/location/experience/projects/education/char_count） |
| `build_resume_context(resume_data)` | 将简历数据转换为面试 Prompt 上下文（严格控制在 800 字以内，按预算截断） |
| `_clean_text(text)` | 清洗 PDF 文本（去页码、控制字符、多余空行） |
| `_extract_contact(text)` | 正则提取电话/邮箱/城市（内置 24 个中国城市列表） |
| `_extract_skills(text)` | 规则提取技能关键词（内置 80+ 技术关键词字典） |
| `_extract_name(text)` | 规则提取姓名（正则 + 黑名单过滤） |
| `_extract_section(text, keywords)` | 规则提取段落（按标题关键词定位段落边界） |
| `_build_summary(text)` | 规则构建摘要（过滤联系方式/纯数字行/标题行） |

#### 4.6.2 llm_parser.py — LLM 结构化提取

[resume/llm_parser.py](file:///workspace/backend/resume/llm_parser.py) 使用 LangChain LCEL Chain 调用 LLM 提取结构化简历信息。

##### Chain 构成

```
resume_extract_prompt | llm | StrOutputParser() | parse_resume_info
```

##### 关键函数

| 函数 | 说明 |
|------|------|
| `build_resume_extract_chain(llm)` | 构建简历解析 Chain |
| `get_resume_format_instructions()` | 获取 ResumeInfo 的 Pydantic 格式指令 |
| `parse_resume_info(text)` | 解析 LLM 输出为 ResumeInfo，带容错（剥离代码块 → 直接解析 → 正则提取 → 返回空对象） |
| `llm_extract(text)` | **核心入口**：截断到 4000 字后调用 Chain，LLM 不可用返回 None |

#### 4.6.3 models.py — ResumeInfo 数据模型

[resume/models.py](file:///workspace/backend/resume/models.py) 定义 `ResumeInfo`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 候选人姓名 |
| `skills` | List[str] | 技术技能关键词列表（按出现顺序去重） |
| `experience` | str | 工作经历压缩（每段一行：公司 职位 时间 + 1句核心成就） |
| `projects` | str | 项目经历压缩（每个一行：项目名 + 技术栈 + 1句成果） |
| `education` | str | 教育背景（1行：学校 专业 学历 时间） |
| `summary` | str | 核心背景概括（100字以内） |

> 依赖方向收拢设计：简历模块的 prompts/chains/models 从 agent 模块迁移至 resume/ 内部，使简历模块自包含。

---

### 4.7 题库数据格式

题库源文件位于 `backend/data/*.md`，每道题用 `---` 分隔，格式如下：

```markdown
<!-- id:py_001 | category:Python基础 | difficulty:1 | difficulty_label:初级 -->
### Q: 解释 Python 的 GIL 是什么？它如何影响多线程编程？
### A: GIL (Global Interpreter Lock) 是 CPython 解释器中的全局解释器锁...
### S:
- 准确解释了 GIL 是全局解释器锁且存在于 CPython
- 正确区分了 CPU 密集和 I/O 密集型任务的不同影响
- 提到了 multiprocessing 或 asyncio 作为解决方案
```

**字段说明**：

| 字段 | 位置 | 说明 |
|------|------|------|
| `id` | HTML 注释 | 题目唯一标识（如 `py_001`） |
| `category` | HTML 注释 | 知识分类（如 `Python基础`） |
| `difficulty` | HTML 注释 | 难度 1/2/3 |
| `difficulty_label` | HTML 注释 | 难度标签（初级/中级/高级） |
| `### Q:` | 正文 | 题目文本 |
| `### A:` | 正文 | 标准答案 |
| `### S:` | 正文 | 得分点列表（每行以 `-` 开头） |

**现有题库**：5 个岗位题库（python_dev / java_dev / frontend_dev / product_manager / general_hr）。

---

## 5. 前端模块详解

### 5.1 应用入口与路由

[main.js](file:///workspace/frontend/src/main.js) 挂载 Pinia + Vue Router，引入全局样式。

[router/index.js](file:///workspace/frontend/src/router/index.js) 定义 7 个懒加载路由：

| 路径 | 名称 | 组件 | 说明 |
|------|------|------|------|
| `/login` | Login | LoginView | 登录页（一键进入，写入 localStorage） |
| `/` | Home | HomeView | 首页（选择面试方式） |
| `/resume-upload` | ResumeUpload | ResumeUploadView | 简历上传/粘贴 |
| `/job-matching` | JobMatching | JobMatchingView | 简历匹配岗位结果 |
| `/choose-job` | ChooseJob | ChooseJobView | 自主选择岗位配置 |
| `/interview` | Interview | InterviewView | 面试对话主界面 |
| `/summary` | Summary | SummaryView | 面试总结报告 |

### 5.2 API 封装

[api/index.js](file:///workspace/frontend/src/api/index.js) 基于 `fetch` 封装 REST 请求，统一处理 JSON 序列化与错误：

| 函数 | 接口 | 说明 |
|------|------|------|
| `getRoles()` | GET `/api/roles` | 获取岗位列表 |
| `uploadResume(file)` | POST `/api/upload/resume` | 上传 PDF 简历（FormData） |
| `parseTextResume(content)` | POST `/api/resume/parse-text` | 解析粘贴文本简历 |

### 5.3 WebSocket 组合式函数

[composables/useWebSocket.js](file:///workspace/frontend/src/composables/useWebSocket.js) 是面试实时通信的核心，封装 WebSocket 连接与消息处理。

##### 返回的响应式状态与方法

| 成员 | 类型 | 说明 |
|------|------|------|
| `ws` | ref | WebSocket 实例 |
| `connected` | ref | 连接状态 |
| `messages` | ref | 消息列表（响应式） |
| `isStreaming` | computed | 是否正在流式输出 |
| `connect()` | function | 建立连接 |
| `sendConfig(...)` | function | 发送 config 配置消息 |
| `sendAnswer(content)` | function | 发送回答 |
| `requestReport()` | function | 请求生成报告 |
| `close()` / `clearMessages()` | function | 关闭/清空 |

##### 消息处理逻辑

`onmessage` 根据 `data.type` 分发：
- `stream_start` → 新建流式消息占位
- `stream_chunk` → 累加到当前流式消息
- `stream_end` → 完成流式消息（根据 stream_type 标记为 question/followup/report）
- `config_ok` / `decision` / `interview_ended` / `status` / `error` → 推入消息列表

### 5.4 页面视图说明

#### LoginView.vue
极简登录页，点击「进入系统」直接写入 `localStorage`（token/username）并跳转首页。

#### HomeView.vue
首页 Hero 区 + 两个面试方式卡片（简历智能匹配 / 自主选择岗位）+ 数据统计展示。

#### ResumeUploadView.vue
- 拖拽/点击上传 PDF（调用 `uploadResume`）
- 或粘贴文本解析（调用 `parseTextResume`）
- 解析结果存入 `sessionStorage`，跳转 `/job-matching`

#### JobMatchingView.vue
- 从 `sessionStorage` 读取简历数据
- 调用 `getRoles` 获取所有岗位
- 将推荐岗位置顶并高亮，点击「开始面试」存入 `selectedRole` 跳转 `/interview`

#### ChooseJobView.vue
- 调用 `getRoles` 加载岗位
- 选择岗位类别 / 面试类型（技术/HR/综合）/ 题量（5/10/15）
- 「开始面试」存入 `selectedRole` 跳转 `/interview`

#### InterviewView.vue（核心）
面试对话主界面，包含：
- **顶栏**：退出按钮 / 岗位标题 / 进度条（第 N/M 题）/ 计时器
- **对话区**：流式渲染 AI 题目与用户回答，支持「AI 思考中」loading 与「报告生成中」loading
- **侧栏**：面试信息卡片 / 题目状态列表 / 提前结束按钮
- **输入区**：回答输入框 + 发送按钮

关键逻辑：
- `onMounted` 连接 WebSocket，连接后发送 config（默认 5 题、难度 2）
- `watch(messages)` 监听消息：题目计数、面试结束标记、报告生成完成自动跳转 `/summary`（携带 sessionStorage 数据）
- `isThinking` computed 判断是否正在流式输出题目/追问

#### SummaryView.vue
- 从 `sessionStorage` 读取报告数据、岗位、题数、用时
- 简易 Markdown 解析器（按行识别 `#`/`##`/`###`/`---`/`-` 标签渲染）
- 支持复制报告

### 5.5 组件与样式

#### TopNav.vue
顶部导航栏，含返回按钮、Logo、首页/简历匹配/选择岗位链接、用户名、退出按钮。

#### DSIcon.vue
内置 30+ SVG 图标的图标组件，通过 `name` prop 选择图标，支持 `size` 与 `color`。覆盖 file、check、pen-line、user、star、arrow、chevron、circle-* 等常用图标。

#### 设计系统
- [design-tokens.css](file:///workspace/frontend/src/styles/design-tokens.css)：CSS 变量定义（brand/bg/text/border 色阶、字体、圆角、阴影、导航高度）
- [global.css](file:///workspace/frontend/src/styles/global.css)：全局 reset + `.ds-*` 工具类（btn/card/pill/navbar/input/progress）+ 响应式断点（640px）

设计风格：极简灰阶（Zinc 色系）、无彩色品牌色、注重留白与信息层次。

---

## 6. 关键流程详解

### 6.1 完整面试流程

```
用户登录
   │
   ├── 路径A：上传简历
   │     │
   │     ▼
   │   ResumeUploadView → POST /api/upload/resume
   │     │
   │     ▼  parse_resume(pdf_path)
   │     │   1. pdfplumber 提取文本
   │     │   2. 正则提取 phone/email/location
   │     │   3. LLM 提取 name/skills/experience/...（失败→规则兜底）
   │     │   4. build_resume_context() 生成 800 字上下文
   │     ▼
   │   JobMatchingView → GET /api/roles
   │     │  按简历技能 vs 岗位 tags 匹配度排序，推荐岗位置顶
   │     ▼
   │   选择岗位 → sessionStorage.selectedRole → /interview
   │
   ├── 路径B：自主选择
   │     │
   │     ▼
   │   ChooseJobView → GET /api/roles → 选择岗位/类型/题量
   │     │
   │     ▼
   │   sessionStorage.selectedRole → /interview
   │
   ▼
InterviewView → WebSocket /ws/chat
   │
   ├── 发送 {type:"config", role, question_count, difficulty, resume_context, resume_skills}
   │     │
   │     ▼  server.py ws_chat() → InterviewEngine.configure()
   │     │  → ws_stream_generator(engine.generate_question_stream(), "question")
   │     │
   │     │  engine.generate_question_stream():
   │     │    1. _select_topic_for_search()（随机选 2-3 个技能/tag）
   │     │    2. retriever.get_question()（BM25+向量+RRF 融合）
   │     │    3. _select_preferred_category()（分类轮换）
   │     │    4. _question_chain.stream()（LCEL 流式出题）
   │     │    5. memory.add_ai_message()
   │     ▼
   │   推送 stream_start → stream_chunk* → stream_end（第一题）
   │
   ├── 用户回答 → 发送 {type:"answer", content}
   │     │
   │     ▼  engine.receive_answer(answer)
   │     │    1. memory.add_user_message()
   │     │    2. retriever.get_answer(question_id)（取标准答案+得分点）
   │     │    3. memory.maybe_compress()（超阈值压缩）
   │     ▼
   │   engine.score_answer()
   │     │  调用 _scoring_chain.invoke()（RobustScoreParser 容错解析）
   │     │  → 记录存入 records，追加到 .md 文件
   │     ▼
   │   engine.decide()
   │     │  ┌─ 题量满 → action="end"
   │     │  ├─ 得分<5 且未追问 → action="followup"（遗漏点为 topic）
   │     │  └─ 否则 → action="next"
   │     ▼
   │   推送 {type:"decision", action, reason}
   │     │
   │     ├── followup → ws_stream_generator(generate_followup_stream(), "followup")
   │     ├── next     → ws_stream_generator(generate_question_stream(), "question")
   │     └── end      → {type:"interview_ended"}
   │
   └── 用户点击「生成面试报告」→ 发送 {type:"report"}
         │
         ▼  engine.generate_summary_stream()
         │    1. _prepare_summary()：统计平均分、构建结构化报告文本
         │    2. yield 结构化部分（逐题表格 + 完整记录 + 数据统计）
         │    3. _summary_chain.stream()（AI 定性分析：总体评价/优势/不足/学习方向/结论）
         │    4. 保存完整报告到 reports/interview_report.md
         ▼
       推送 stream_start(report) → stream_chunk* → stream_end
         │
         ▼
       InterviewView watch 检测到 report 完成
         → sessionStorage 携带报告数据 → 跳转 /summary
         │
         ▼
       SummaryView 渲染报告
```

### 6.2 出题去重与多样性机制

`InterviewEngine` 通过多重机制保证出题质量：

1. **题目去重**：`asked_ids` 列表记录已问题目 ID，传入 `exclude_ids` 参数排除
2. **分类轮换**：`_select_preferred_category()` 优先选择未问过的分类，问完一轮后逆序复用
3. **话题随机性**：`_select_topic_for_search()` 随机抽取 2-3 个技能/tag 作为检索话题
4. **难度放宽重试**：首次按难度检索无果时，放宽难度限制重试
5. **随机兜底**：检索完全无果时调用 `get_random_question()` 随机抽题
6. **简历技能过滤**：`_get_filtered_resume_skills()` 只保留与当前岗位 tag 相关的技能，防止跨岗位出题

### 6.3 评分容错机制

`RobustScoreParser` 五级降级策略（详见 [4.4.2](#442-chainspy--lcel-chain-定义)），确保即使 LLM 输出格式异常也能尽可能提取分数。

---

## 7. 依赖关系

### 7.1 后端依赖（requirements.txt）

| 类别 | 依赖 | 用途 |
|------|------|------|
| **LangChain Core** | `langchain` / `langchain-core` / `langchain-community` / `langchain-openai` / `langchain-chroma` / `langchain-huggingface` | LCEL Chain、Chroma 集成、OpenAI 兼容 LLM、HuggingFace Embeddings |
| **向量库与嵌入** | `chromadb` / `sentence-transformers` | 本地向量数据库、嵌入模型运行时 |
| **BM25 检索** | `rank-bm25` / `jieba` | 关键词检索、中文分词 |
| **LLM API** | `openai` | OpenAI 兼容 SDK |
| **数据模型** | `pydantic` | 结构化数据校验与输出解析 |
| **Web 服务** | `fastapi` / `uvicorn` / `python-multipart` | Web 框架、ASGI 服务器、文件上传支持 |
| **PDF 解析** | `pdfplumber` | PDF 文本提取 |
| **工具** | `python-dotenv` / `numpy` | .env 加载、数值计算 |

### 7.2 前端依赖（package.json）

| 类别 | 依赖 | 用途 |
|------|------|------|
| **核心** | `vue@^3.4.0` / `vue-router@^4.3.0` / `pinia@^2.1.0` | Vue 3 框架、路由、状态管理 |
| **UI** | `lucide-vue-next@^0.577.0` | 图标库（实际项目用自建 DSIcon） |
| **构建** | `vite@^5.4.0` / `@vitejs/plugin-vue@^5.0.0` | 构建工具与 Vue 插件 |

### 7.3 模块间依赖关系

```
server.py ─┬─► agent.engine.InterviewEngine
           ├─► retrieval.retriever.HybridRetriever
           ├─► resume.parser.parse_resume / build_resume_context
           └─► config

main.py ───┬─► retrieval.kb_builder.KnowledgeBaseBuilder  (build)
           ├─► retrieval.retriever.HybridRetriever         (chat)
           ├─► agent.engine.InterviewEngine                (chat)
           └─► resume.parser.parse_resume / build_resume_context

agent.engine ─┬─► agent.llm (get_llm)
              ├─► agent.memory.InterviewMemory
              ├─► agent.chains (build_*_chain)
              │      ├─► agent.prompts (*_prompt)
              │      └─► agent.models.ScoreResult
              ├─► agent.models.ScoreResult
              ├─► agent.tools.create_tools ─► retrieval.retriever
              └─► retrieval.retriever.HybridRetriever

retrieval.retriever ─► agent.llm.get_embeddings (lru_cache 单例)
retrieval.kb_builder ─► agent.llm.get_embeddings

resume.parser ─► resume.llm_parser.llm_extract
                    └─► agent.llm.get_llm
                        └─► resume.models.ResumeInfo
```

> **依赖方向收拢**：简历模块的 prompts/chains/models 从 agent 迁移至 resume/ 内部，使简历模块自包含，仅通过 `agent.llm.get_llm` 复用 LLM 工厂。

---

## 8. 项目运行方式

### 8.1 环境准备

1. **Python 环境**：Python 3.9+
2. **Node.js 环境**：Node.js 18+
3. **BGE 嵌入模型**：下载 `BAAI/bge-base-zh-v1.5` 模型到本地，配置路径
4. **LLM API Key**：申请 DeepSeek 或智谱 GLM 的 API Key

### 8.2 后端配置

```bash
cd backend

# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入：
#   DEEPSEEK_API_KEY=你的 DeepSeek API Key
#   LOCAL_BGE_MODEL_PATH=本地 BGE 模型路径
#   LLM_BASE_URL=https://api.deepseek.com（或其他 OpenAI 兼容接口）
#   LLM_MODEL=deepseek-v4-flash（或其他模型名）

# 3. 离线建库（首次运行必须，题库更新后重新执行）
python main.py build
# 或重建：python main.py rebuild
```

### 8.3 启动后端服务

```bash
cd backend
python server.py
# 默认监听 0.0.0.0:8000，开启 reload
# 访问 http://localhost:8000
```

### 8.4 启动前端服务

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
# 默认监听 http://localhost:3000
# 已配置代理：/api → http://localhost:8000，/ws → ws://localhost:8000

# 3. 构建生产版本
npm run build
# 产物在 frontend/dist/，可放入 backend/static/ 由 FastAPI 静态托管
```

### 8.5 CLI 模式运行（无需前端）

```bash
cd backend

# 建库后直接启动 CLI 面试
python main.py chat
# 按提示选择：1=手动选岗位 / 2=上传简历自动匹配
# 配置题量与难度后开始流式面试
# 输入 quit 退出并生成报告，输入 skip 换题
```

### 8.6 生产部署

1. 前端 `npm run build` 生成 `dist/`
2. 将 `dist/` 内容复制到 `backend/static/`
3. 启动 `python server.py`，FastAPI 自动托管前端静态文件（`/` 与 `/static/*`）
4. 通过 `http://server:8000` 访问完整应用

---

## 9. 配置说明

### 9.1 环境变量（.env）

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API Key（或其他 OpenAI 兼容服务） |
| `LLM_BASE_URL` | 否 | LLM API 地址，默认 `https://api.deepseek.com` |
| `LLM_MODEL` | 否 | 模型名，默认 `deepseek-v4-flash` |
| `LOCAL_BGE_MODEL_PATH` | 是 | 本地 BGE bge-base-zh-v1.5 模型路径 |
| `ZHIPUAI_API_KEY` | 可选 | 智谱 GLM API Key（备选 LLM） |
| `ALIYUN_API_KEY` | 可选 | 阿里云 API Key（备选 LLM） |

### 9.2 关键运行时参数（config.py）

| 参数 | 默认值 | 调节建议 |
|------|--------|---------|
| `TOP_K` | 5 | 检索候选数量，增大提高召回但增加延迟 |
| `BM25_WEIGHT` / `VECTOR_WEIGHT` | 0.4 / 0.6 | 双路权重，偏关键词匹配调高 BM25，偏语义调高 Vector |
| `RRF_K` | 60 | RRF 融合参数，越小头部权重越集中 |
| `MEMORY_WINDOW_SIZE` | 10 | 保留最近消息数，影响上下文长度与成本 |
| `MEMORY_COMPRESS_THRESHOLD` | 6000 | 压缩触发字符阈值，过小频繁压缩，过大成本高 |
| `LLM_TEMPERATURE` | 0.7 | 出题/追问温度；评分建议调低（llm_parser 已设 0） |

---

## 10. WebSocket 流式协议

### 10.1 客户端 → 服务端消息

| type | 字段 | 说明 |
|------|------|------|
| `config` | role, question_count, difficulty, resume_context, resume_skills | 配置面试并触发第一题 |
| `answer` | content | 提交回答（支持 quit/exit/skip 特殊指令） |
| `report` | - | 请求生成总结报告 |

### 10.2 服务端 → 客户端消息

| type | 字段 | 说明 |
|------|------|------|
| `stream_start` | stream_type (question/followup/report) | 流式输出开始 |
| `stream_chunk` | content | 流式文本片段（逐块推送） |
| `stream_end` | stream_type, full_text | 流式输出结束，附带完整文本 |
| `config_ok` | content, role_key, role_title, question_count, difficulty, difficulty_label, categories | 配置成功 |
| `decision` | action (next/followup/end), reason | 评分后决策结果 |
| `interview_ended` | content, can_report | 面试结束，可请求报告 |
| `status` | content | 状态提示（如「换下一题...」） |
| `error` | content | 错误信息 |

### 10.3 流式时序示例

```
客户端                          服务端
  │                              │
  │── {type:"config",...} ──────►│
  │                              │ (configure + 生成第一题)
  │◄── {type:"config_ok",...} ───│
  │◄── {type:"stream_start",     │
  │       stream_type:"question"}│
  │◄── {type:"stream_chunk",     │
  │       content:"请"}──────────│
  │◄── {type:"stream_chunk",     │
  │       content:"解释"}────────│
  │◄── {type:"stream_end",       │
  │       full_text:"请解释..."}─│
  │                              │
  │── {type:"answer",            │
  │     content:"GIL是..."} ────►│
  │                              │ (receive_answer + score + decide)
  │◄── {type:"decision",         │
  │       action:"next"}─────────│
  │◄── {type:"stream_start",...} │ (下一题)
  │   ...                        │
  │                              │
  │── {type:"report"} ──────────►│
  │◄── {type:"stream_start",     │
  │       stream_type:"report"}──│
  │◄── {type:"stream_chunk",...} │ (报告逐块)
  │◄── {type:"stream_end",       │
  │       full_text:"# AI面试..."}│
```

---

> **文档版本**：v1.0
> **生成日期**：2026-07-09
> **覆盖范围**：backend/（agent、retrieval、resume、config、main、server）+ frontend/（views、components、composables、api、styles）
