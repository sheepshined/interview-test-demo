# AI 模拟面试官系统

> 基于 **LangGraph** 的 AI 模拟面试系统：简历解析 → 按岗位出题 → 流式问答 → 四维评分 → 智能追问 → 综合评价报告

## 项目简介

一个面向技术岗位的 AI 模拟面试官，能根据候选人简历和所选岗位自动出题、流式追问、四维度评分并生成面试报告。后端用 **LangGraph 状态图** 编排面试全流程（人在回路 + 进程内 checkpointer），前端为 Vue 3 SPA。

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

## 架构（答辩稳定版）

面试流程由 LangGraph StateGraph 声明式驱动，WebSocket 仅作"人在回路驱动器"：

```text
START → configure → opening → prepare_question → emit_question → wait_answer(interrupt)
                                                                      │
                                                                      ▼
                                                               score_initial
                                                             ┌────────┴────────┐
                                                        score >= 5          score < 5
                                                             │                 ▼
                                                             │       prepare_followup
                                                             │        → emit_followup
                                                             │        → wait_followup(interrupt)
                                                             │        → score_combined
                                                             └────────┬────────┘
                                                                      ▼
                                                             finalize_question
                                                              │ next       │ end
                                                              ▼            ▼
                                                    prepare_question     closing
                                                                        → wait_report(interrupt)
                                                                        → summary → END
```

- **恢复安全**：随机选题和 LLM 流式输出在独立节点内完成；`wait_answer`、`wait_followup`、`wait_report` 在 `interrupt()` 前不执行副作用，恢复时不会重复出题。
- **人在回路**：结构化 `Command(resume={"action": ...})` 驱动回答、提前结束和报告生成。
- **追问重评**：低于 5 分最多追问一次，原回答与补充回答合并重评；主问题仍只计一道，并同时保留初始分和最终分。
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
│   │   ├── protocol.py        WebSocket 命令/phase 约束
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
│   ├── data/                  8 岗位题库 (86 题)
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
npm run dev                           # http://localhost:3000 (Vite 代理 /api /ws → :8000)
```

### 3. CLI 模式 (无需前端)

```bash
cd TOtal/backend
python main.py build                  # 建库
python main.py chat                   # 终端流式面试
```

### 4. 可选容器实验（不属于答辩稳定版验收）

当前答辩演示采用本机双服务。仓库保留了 Docker 与静态构建实验文件，但单服务 SPA fallback 尚未列入本轮验收，不应替代上面的双服务启动方式。

前端构建命令：
```bash
cd TOtal/frontend
npm install && npm run build
cp -r dist/* ../backend/static/       # 构建产物拷入后端静态目录
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

## 面试流程与协议

1. **配置**：前端选岗位/题数/难度，上传简历（PDF 或粘贴文本）→ LLM 解析技能、推荐岗位。
2. **开场**：graph `opening` 节点流式生成开场白 + 引出第一个话题。
3. **问答循环**：准备并固定题目 → 一次性流式输出 → `wait_answer` 暂停 → 四维评分。
4. **追问**：初始得分 `<5` 时最多追问一次，补充回答与原回答合并重评；报告中的 `score` 为最终分，`initial_score` 保留初始表现。
5. **收尾+报告**：题量完成或收到 `end` → `closing` → `wait_report` 暂停 → 用户点击后生成带唯一 `report_id` 的 Markdown + JSON 报告。

WebSocket 输入消息：`config`、`answer`、`end`、`report`。服务端按 `phase` 校验命令；只有 `await_answer/await_followup` 可回答或提前结束，只有 `await_report` 可首次生成报告。

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

### 阶段1 · LangGraph 核心迁移与稳定化（已完成）
- `agent/state.py` 集中状态；`agent/graph.py` 使用 14 个职责单一节点和条件边。
- 重构 `server.py` `ws_chat` 为 graph 驱动器（`astream` + `Command(resume)`）。
- 选题/输出与 interrupt 等待节点分离，消除 resume 重跑导致的重复题目和题目 ID 漂移。
- MemorySaver 仅提供当前进程内的暂停点；服务重启恢复不在答辩稳定版范围。

### 阶段2 · 功能增强（已完成）
- 新增 3 岗位题库（algorithm/devops/data_analyst，共 86 题 8 岗位），`main.py build` 重建。
- 报告管理 API：`GET /api/reports`（列表）、`GET /api/reports/{id}`（md 全文）、`GET /api/reports/{id}/radar`（雷达数据，实测通过）。
- 报告维度：summary 节点额外存 `.json`（四维均值 + 分类均值 + 逐题 + 强弱项），供前端 ECharts 雷达图。
- 会话登记：`_sessions` + `thread_id` 用于当前进程内状态识别；磁盘级续接待后续实现。

### 阶段3 · 性能与提示词优化（已完成）
- 模型分层：`LLM_MODEL_FAST`（出题/评分/追问/开场/收尾）/`LLM_MODEL_STRONG`（总结，低温）；`get_fast_llm`/`get_strong_llm`。
- 标准答案缓存：`retriever.get_answer` 按 question_id 内存缓存。
- scorer 提示词强约束纯 JSON（减少 RobustScoreParser 兜底）。

### 阶段4 · 工程化与文档（部分完成）
- README + 优化方案 + 项目 memory 已完成；Docker / 前端构建集成 backend/static 待续。

## 已知限制
- checkpointer 和会话登记均在进程内，服务重启后不能恢复面试。
- Memory（对话历史摘要）在 graph 节点内暂传空，跨轮记忆待补。
- 登录为演示用固定账号（admin/123123），非生产级。
- Docker 单服务静态托管、生产鉴权、限流、CI 和监控不属于当前答辩稳定版。

## 自动化验证

```bash
cd TOtal/backend
pip install -r requirements-dev.txt
python -m pytest -q

cd ../frontend
npm run build
```

测试覆盖：恢复后不重复出题、低分追问合并重评、主问题计数、提前结束不产生虚假评分、报告 ID/雷达题目一致性、协议阶段约束和评分解析容错。

需要真实 LLM 的手动烟雾测试（先启动后端）：

```bash
cd TOtal/backend
python tests/real_smoke.py
```

### 2026-08-09 最终验收记录

- Fake LLM/Fake Retriever：`5 passed`（最终复跑通过）。
- Python：27 个项目文件语法通过；8 个岗位、86 道题、86 个唯一 ID；本地 Chroma 实际记录数 86。
- 前端：Vite 5.4.21 production build 通过，635 个模块完成转换。
- 真实 2 题协议闭环：第一题低分只追问一次，第二题正常回答不追问，报告为 `interview_report_20260809_174222_c842b535_python_dev`，事件、Markdown 和雷达 JSON 的题目 ID 一致。
- 页面闭环：FastAPI `:8000` + Vite `:3000` 下完成流式问答、提前结束（真实完成数 2）、点击生成报告和 `/summary/:reportId` 精确跳转；页面报告为 `interview_report_20260809_174732_732b5434_python_dev`。

## 答辩要点
- **状态机可视化**：LangGraph 图结构清晰表达面试流程，替代散落的 if/elif 编排。
- **人在回路**：`interrupt()` + `Command(resume)` 实现出题后暂停等回答，符合面试交互本质。
- **持久化基础**：checkpointer 按 thread_id 保存暂停点，为断线续接铺路。
- **混合检索**：BM25 + 向量 + RRF 融合，兼顾关键词匹配与语义召回。
- **结构化评分**：PydanticOutputParser + 5 级容错解析，LLM 输出可靠结构化。
