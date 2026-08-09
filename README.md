# AI 模拟面试官系统

> 基于 **LangGraph** 的 AI 模拟面试系统：简历解析 → 按岗位出题 → 流式问答 → 四维评分 → 智能追问 → 综合评价报告

## 项目简介

一个面向技术岗位的 AI 模拟面试官，能根据候选人简历和所选岗位自动出题、流式追问、四维度评分并生成面试报告。后端用 **LangGraph 状态图** 编排面试全流程（人在回路 + 断线续接），前端为 Vue 3 SPA。

## 技术栈

| 层 | 技术 |
|----|------|
| 面试编排 | **LangGraph** StateGraph（节点 + 条件边 + interrupt 人在回路 + checkpointer） |
| LLM | LangChain ChatOpenAI（兼容 DeepSeek / 智谱 GLM / OpenAI） |
| 检索 | LangChain-Chroma 向量 + BM25 关键词 + RRF 融合（混合检索） |
| Embedding | HuggingFace BGE-base-zh-v1.5（本地，可回退 Hub 下载） |
| 后端 | Python + FastAPI + WebSocket（流式推送） |
| 前端 | Vue 3 + Vite + vue-router + Pinia |
| 简历解析 | pdfplumber + LLM 结构化（规则兜底） |

## 架构（阶段1 重构后）

面试流程由 LangGraph StateGraph 声明式驱动，WebSocket 仅作"人在回路驱动器"：

```
START → configure → opening → ask ──interrupt(等回答)──▸ receive_answer → score → decide
                                                                       │
              ┌────────────────────────────────────────────────────────┤
              ▼ next               ▼ followup                          ▼ end
            ask(interrupt)     followup(interrupt)──▸receive_answer   closing ──interrupt(等报告)──▸ summary → END
```

- **状态集中**：`agent/state.py` 的 `InterviewState` 替代散落的实例变量，断线可由 checkpointer 按 `thread_id` 恢复。
- **人在回路**：`ask`/`followup` 节点末尾 `interrupt()` 暂停，等用户回答后 `Command(resume=...)` 恢复。
- **流式输出**：节点内 `get_stream_writer()` 推 custom event，server 经 `graph.astream(stream_mode=["custom","values"])` 转发 WebSocket。

## 目录结构

```
TOtal/
├── backend/
│   ├── server.py              FastAPI 后端 (LangGraph 驱动, WebSocket 流式)
│   ├── main.py                CLI 入口 (build / chat / rebuild)
│   ├── config.py              全局配置 (模型/路径/岗位/难度/CORS)
│   ├── common.py              公共工具 (match_role/extract_skills/extract_json_object)
│   ├── agent/
│   │   ├── graph.py           ★ LangGraph 面试状态图 (节点+边+interrupt)
│   │   ├── state.py           ★ InterviewState 共享状态
│   │   ├── chains.py          LCEL Chain 工厂 (question/scoring/followup/summary/opening/closing)
│   │   ├── prompts.py         ChatPromptTemplate 提示词
│   │   ├── models.py          ScoreResult Pydantic 模型
│   │   ├── memory.py          对话记忆 + 摘要压缩
│   │   ├── llm.py             ChatOpenAI 工厂
│   │   └── engine.py          旧 InterviewEngine (CLI/回退用)
│   ├── retrieval/
│   │   ├── retriever.py       HybridRetriever (BM25+向量+RRF)
│   │   ├── embeddings.py      BGE Embeddings 工厂 (独立, 打破循环依赖)
│   │   └── kb_builder.py      离线知识库构建
│   ├── resume/                简历解析 (PDF+LLM)
│   ├── data/                  岗位题库 (python/java/frontend/product_manager/general_hr)
│   ├── reports/               面试报告
│   └── requirements.txt
├── frontend/                  Vue 3 SPA
└── defense-ppt/               答辩演示文稿
```

## 快速启动

### 1. 后端

```bash
cd TOtal/backend
pip install -r requirements.txt        # 含 langgraph / langchain / chromadb 等

# 配置 API Key
cp .env.example .env                  # 填入 LLM_API_KEY (DeepSeek/智谱/OpenAI 兼容)
# 可选: 设 LOCAL_BGE_MODEL_PATH 指向本地 BGE 加速, 否则首次自动从 Hub 下载

# 离线建库 (题库更新后执行一次)
python main.py build

# 启动服务 (开发态)
python server.py                      # http://localhost:8000
```

### 2. 前端

```bash
cd TOtal/frontend
npm install
npm run dev                           # http://localhost:5173 (Vite 代理 /api /ws → :8000)
```

### 3. CLI 模式 (无需前端)

```bash
cd TOtal/backend
python main.py build                  # 建库
python main.py chat                   # 终端流式面试
```

### 4. 生产部署（Docker + 前端集成）

**前端构建集成**（让后端单服务托管前端，无需单独跑前端 dev server）：
```bash
cd TOtal/frontend
npm install && npm run build
cp -r dist/* ../backend/static/       # 构建产物拷入后端静态目录
# 之后 python server.py 即 http://localhost:8000 单服务访问
```

**Docker 容器化**（`TOtal/docker-compose.yml` + `backend/Dockerfile`）：
```bash
cd TOtal
cp backend/.env.example backend/.env   # 填入 LLM_API_KEY
docker compose up --build             # 构建并启动后端 (:8000)
# 首次建库 (chroma_db 卷持久化, 仅需一次):
docker compose run --rm backend python main.py build
# 前端: npm run build 后 cp dist/* backend/static/ (compose 已挂载该目录)
```
> 容器内无宿主本地 BGE 路径，compose 已设 `LOCAL_BGE_MODEL_PATH=BAAI/bge-base-zh-v1.5`（首次从 Hub 下载，约 500MB）。

## 配置说明 (.env)

| 变量 | 说明 | 默认 |
|------|------|------|
| `LLM_API_KEY` | LLM API Key (兼容读 `DEEPSEEK_API_KEY`) | 必填 |
| `LLM_BASE_URL` | LLM 服务地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名 | `deepseek-chat` |
| `LOCAL_BGE_MODEL_PATH` | 本地 BGE 路径 (留空则 Hub 下载) | `BAAI/bge-base-zh-v1.5` |
| `EMBEDDING_ONLINE` | 在线 Embedding 回退 | `false` |
| `CORS_ORIGINS` | 允许的前端来源 (逗号分隔) | `http://localhost:5173,...` |

## 面试流程

1. **配置**：前端选岗位/题数/难度，上传简历（PDF 或粘贴文本）→ LLM 解析技能、推荐岗位。
2. **开场**：graph `opening` 节点流式生成开场白 + 引出第一个话题。
3. **问答循环**：`ask`（检索+出题，interrupt 等回答）→ 候选人回答 → `receive_answer`（取标准答案）→ `score`（四维评分）→ `decide`（追问/下一题/结束）。
4. **追问**：得分<5 且未追问过 → `followup` 节点针对遗漏点深挖。
5. **收尾+报告**：题数到 → `closing` 收尾 → `summary` 生成结构化+AI 分析报告（时间戳命名，防并发覆盖）。

评分四维度：准确性 / 完整性 / 深度 / 清晰度（每维 1-10，Pydantic 结构化输出 + 5 级容错解析）。

## 优化演进记录

### 阶段0 · 基线清理与修复（已完成）
- 配置：模型名 `deepseek-v4-flash`→`deepseek-chat`；API Key 统一 `LLM_API_KEY`；Embedding 路径可移植化。
- 服务器：CORS 收紧；`import shutil` 删除；纯 CPU 接口 `async`→`def`。
- 死代码：删除 `reaction_chain` 全套、`build_scoring_chain` 死变量、models 注释类、无用 import。
- 去重：新建 `common.py`（`match_role`/`score_roles`/`get_difficulty_label`/`extract_skills`/`extract_json_object`），消除岗位匹配/难度映射/技能词表/JSON 解析重复。
- 循环依赖：`get_embeddings` 下沉到 `retrieval/embeddings.py`，retrieval 不再反向依赖 agent。
- 异常：4 处 `except: pass` 改 `logger.warning`；报告时间戳命名。
- 瘦身：归档 `mock_interview_langchain`/`total DEMO` 旧版本、根目录答辩 HTML 快照。

### 阶段1 · LangGraph 核心迁移（已完成）
- 新建 `agent/state.py`（`InterviewState`）、`agent/graph.py`（StateGraph + 9 节点 + interrupt + 条件边）。
- 重构 `server.py` `ws_chat` 为 graph 驱动器（`astream` + `Command(resume)`）。
- 7 个 LCEL Chain 的手动 if/elif 编排 → 图的节点+边声明式定义。
- MemorySaver checkpointer 持久化暂停点（断线续接基础）。
- WebSocket 集成测试：config→opening→question→answer→resume→下一题 全链路打通。

### 阶段2 · 功能增强（已完成）
- 新增 3 岗位题库（algorithm/devops/data_analyst，共 86 题 8 岗位），`main.py build` 重建。
- 报告管理 API：`GET /api/reports`（列表）、`GET /api/reports/{id}`（md 全文）、`GET /api/reports/{id}/radar`（雷达数据，实测通过）。
- 报告维度：summary 节点额外存 `.json`（四维均值 + 分类均值 + 逐题 + 强弱项），供前端 ECharts 雷达图。
- 断线续接：会话登记 `_sessions` + `GET /api/interviews` + ws_chat 支持 thread_id 重连（MemorySaver 进程内持久；磁盘级 SqliteSaver 待续）。

### 阶段3 · 性能与提示词优化（已完成）
- 模型分层：`LLM_MODEL_FAST`（出题/评分/追问/开场/收尾）/`LLM_MODEL_STRONG`（总结，低温）；`get_fast_llm`/`get_strong_llm`。
- 标准答案缓存：`retriever.get_answer` 按 question_id 内存缓存。
- scorer 提示词强约束纯 JSON（减少 RobustScoreParser 兜底）。

### 阶段4 · 工程化与文档（部分完成）
- README + 优化方案 + 项目 memory 已完成；Docker / 前端构建集成 backend/static 待续。

## 已知限制
- `decision` 事件推送采用双保险（节点兜底 + values-stream 补发），因 LangGraph astream custom 在 resume 后首个 event 偶发丢失。
- Memory（对话历史摘要）在 graph 节点内暂传空，跨轮记忆待补。
- 登录为演示用固定账号（admin/123123），非生产级。

## 答辩要点
- **状态机可视化**：LangGraph 图结构清晰表达面试流程，替代散落的 if/elif 编排。
- **人在回路**：`interrupt()` + `Command(resume)` 实现出题后暂停等回答，符合面试交互本质。
- **持久化基础**：checkpointer 按 thread_id 保存暂停点，为断线续接铺路。
- **混合检索**：BM25 + 向量 + RRF 融合，兼顾关键词匹配与语义召回。
- **结构化评分**：PydanticOutputParser + 5 级容错解析，LLM 输出可靠结构化。
