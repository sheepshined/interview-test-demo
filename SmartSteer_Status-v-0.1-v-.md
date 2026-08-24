# SmartSteer — AI 模拟面试官 · 交接状态文档 (v0.1)

> **生成日期**: 2026-08-11
> **适用范围**: `E:\hiagent\DEMO3\TOtal`（当前主线工作区，即"答辩稳定版"）
> **用途**: 在新窗口继续开发的交接文档。本文件只做"现状盘点"，未修改任何代码。
> **配套文档**: [README.md](README.md)（项目说明）、[START_GUIDE.md](START_GUIDE.md)（启动手册）、[OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)（历史优化方案）、[PROJECT_EVALUATION_AND_OPTIMIZATION.md](PROJECT_EVALUATION_AND_OPTIMIZATION.md)（完成度评估，2026-08-09）。

---

## 1. 已完成内容

### 1.1 核心架构：LangGraph 重构（阶段 0–1）
- 弃用旧 LangChain 手动状态机（`engine.py` 的 `Phase` 枚举 + 大量实例变量），改用 **LangGraph StateGraph** 编排：
  - `agent/state.py` — `InterviewState`（TypedDict）集中全部状态
  - `agent/graph.py` — 14 节点状态图：`configure → opening → prepare_question → emit_question → wait_answer → score_initial → (prepare_followup → emit_followup → wait_followup → score_combined) → finalize_question → ... → closing → wait_report → summary → END`
  - 3 个 `interrupt()` 等待节点（`wait_answer` / `wait_followup` / `wait_report`）实现"人在回路"
  - `MemorySaver` checkpointer 按 `thread_id` 保存暂停点
- **恢复安全语义（答辩稳定版核心，2026-08-09 落实）**：`interrupt` 之前的节点不做随机选题 / LLM 调用 / 文件写入，恢复回答不会重复出题或重复输出；`prepare_question`（随机选题）已与 `emit_question`（流式输出）拆成独立节点。

### 1.2 功能增强（阶段 2–3）
- **题库扩充**：8 岗位、86 道题（data/*.md），`main.py build/rebuild` 构建 Chroma 向量库
- **报告体系**：summary 节点生成 Markdown 报告 + 雷达 JSON（四维均值/分类均值/逐题/强弱项）；REST 接口 `GET /api/reports`、`GET /api/reports/{id}`、`GET /api/reports/{id}/radar`；前端 ECharts 雷达图（`RadarChart.vue`）
- **会话登记与续接**：`_sessions` 进程内登记，`GET /api/interviews` 列出；`ws_chat` 支持带 `thread_id` 的 config 恢复会话
- **模型分层**：`LLM_MODEL_FAST`（出题/评分/追问/开场/收尾，求速度）vs `LLM_MODEL_STRONG`（总结报告，低温求质量）；标准答案缓存 `retriever._answer_cache`
- **WS 阶段协议**：`agent/protocol.py` 纯函数校验（`answer`/`end` 仅在 `await_answer`/`await_followup`，`report` 仅在 `await_report`），错误提示稳定返回前端

### 1.3 工程与质量（阶段 4–5）
- **测试**：`pytest` 套件（协议、评分解析器、API 入口、LangGraph 全流程 Fake LLM 回归），真实 LLM WebSocket 冒烟脚本 `tests/real_smoke.py`
- **清理**：删除 reaction 死代码、`agent/engine.py`、`agent/memory.py`、`agent/tools.py`（工作区已删，未提交——见 §4.1）；`common.py` 去重（`match_role`/`extract_skills`/`extract_json_object`/`get_difficulty_label`）；`get_embeddings` 下沉 `retrieval/embeddings.py` 破循环依赖；静默异常补 logging
- **文档**：README.md、START_GUIDE.md 已更新为本机双服务启动方式
- **前端细节**：登录/鉴权封装 `auth.js`；请求超时/错误提示优化；`sendConfig` 题量传参修复（进度条与实际题量一致）

### 1.4 已实测通过的链路
- WebSocket 全链路：config → opening → 出题 → 回答 → 低分追问 → 合并重评 → 下一题 → 收尾 → 生成报告 → `report_ready`（含 `[decision]` 双保险推送）
- 自动化测试 10/10 通过（详见 §4.4 环境注意项）；真实烟雾脚本通过一次完整 2 题面试

---

## 2. 当前代码结构

### 2.1 目录总览

```text
E:\hiagent\DEMO3\                  ← 顶层（旧根仓库，含 _archive 归档，非主线）
└── TOtal\                         ← ★ 当前主线（独立 git 仓库）
    ├── README.md / START_GUIDE.md / OPTIMIZATION_PLAN.md / PROJECT_EVALUATION_AND_OPTIMIZATION.md
    ├── backend/
    │   ├── server.py              FastAPI 入口：REST + WebSocket /ws/chat（graph 驱动）
    │   ├── main.py                题库 build/rebuild 入口
    │   ├── config.py              全局配置（路径/检索/模型/角色/难度/评分维度）
    │   ├── common.py              跨模块公共工具（岗位匹配/技能提取/JSON 容错/难度标签）
    │   ├── .env.example           API Key 与模型配置模板（已存在 backend/.env）
    │   ├── agent/
    │   │   ├── graph.py           StateGraph 14 节点 + interrupt（核心）
    │   │   ├── state.py           InterviewState TypedDict
    │   │   ├── protocol.py        WS 阶段约束（answer/end/report 允许阶段）
    │   │   ├── chains.py          LCEL Chain 工厂 + RobustScoreParser
    │   │   ├── prompts.py         6 套 ChatPromptTemplate（question/scorer/followup/summary/opening/closing + compress 备用）
    │   │   ├── llm.py             ChatOpenAI 工厂（get_fast_llm/get_strong_llm）
    │   │   └── models.py          ScoreResult / ScoreBreakdown（Pydantic）
    │   ├── retrieval/
    │   │   ├── retriever.py       HybridRetriever：BM25 + 向量 + RRF 融合
    │   │   ├── kb_builder.py      离线题库解析与 Chroma 构建
    │   │   └── embeddings.py      HuggingFaceEmbeddings 工厂（lru_cache，本地/Hub 回退）
    │   ├── resume/
    │   │   ├── parser.py          PDF 解析（pdfplumber + 正则 + LLM 混合，规则兜底）
    │   │   ├── llm_parser.py      LLM 简历信息提取（ResumeInfo）
    │   │   └── models.py          ResumeInfo Pydantic
    │   ├── data/                  8 岗位题库 .md（86 题，`### Q/A/S` + `<!-- id|category|difficulty -->` 格式）
    │   ├── reports/               生成的报告（.md + .json 雷达对）
    │   ├── tests/                 test_protocol / test_score_parser / test_api_entrypoints / test_interview_graph / real_smoke
    │   ├── requirements.txt / requirements-dev.txt
    │   └── chroma_db/  uploads/   （.gitignore，运行时生成）
    └── frontend/                  Vue 3 + Vite (port 3000)
        └── src/
            ├── api/index.js       REST 封装（超时 AbortController）
            ├── auth.js            登录态（localStorage token）
            ├── composables/useWebSocket.js   WS 封装（stream 事件聚合）
            ├── router/index.js    7 路由 + 登录守卫
            ├── views/             Login/Home/ResumeUpload/JobMatching/ChooseJob/Interview/Summary
            └── components/        TopNav / RadarChart / DSIcon
```

### 2.2 核心数据流

```text
登录(admin/123123) → Home → 简历匹配(ResumeUpload→JobMatching) 或 自主选岗(ChooseJob)
  → InterviewView: sessionStorage.selectedRole → connect → sendConfig
  → server: /ws/chat config → run_graph_stream(initial_state, thread_id)
  → graph: configure→opening→prepare_question→emit_question→wait_answer(interrupt)
  → 前端输入回答 → answer 消息 → Command(resume) → score_initial
  → score<5: prepare_followup→emit_followup→wait_followup→score_combined
  → finalize_question → 循环或 closing → wait_report(interrupt) → report 消息 → summary
  → report_ready {report_id} → 前端跳 /summary/:reportId → 拉 /api/reports/{id} + /radar
```

### 2.3 WebSocket 协议（前端 ↔ 后端）

| 方向 | 消息 |
|---|---|
| 客户端→服务端 | `config`(role/question_count/difficulty/resume_context/resume_skills/thread_id) · `answer`(content) · `end` · `report` |
| 服务端→客户端 | `config_ok` · `status` · `stream_start` · `stream_chunk` · `stream_end`(含 full_text/report_id) · `decision` · `interview_ended` · `report_ready` · `error` |
| stream_type | `opening` / `question` / `followup` / `closing` / `report` |

---

## 3. 关键参数

### 3.1 模型与 API（backend/.env，已有本地配置）
| 参数 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 必填（兼容 `DEEPSEEK_API_KEY`） | DeepSeek Key |
| `LLM_BASE_URL` | `https://api.deepseek.com` | 换智谱需改 base_url + model |
| `LLM_MODEL` | `deepseek-chat` | 兼容旧引用 |
| `LLM_MODEL_FAST` | `deepseek-chat` | 出题/评分/追问/开场/收尾 |
| `LLM_MODEL_STRONG` | `deepseek-chat` | 总结报告（可配 deepseek-reasoner/glm-4.5） |
| `LLM_TEMPERATURE` / `_STRONG` | 0.7 / 0.3 | 常规 vs 总结低温 |
| `LLM_MAX_TOKENS` / `MAX_RETRIES` | 4096 / 2 | |
| `LOCAL_BGE_MODEL_PATH` | 空=Hub 自动下载 `BAAI/bge-base-zh-v1.5` | 本地路径不存在自动回退 Hub |
| `EMBEDDING_ONLINE` | false | 智谱 embedding-2 在线回退（未接入实现，仅配置项） |

### 3.2 检索（config.py）
- `TOP_K=5`、`CHUNK_SIZE=500`、`OVERLAP=50`
- RRF：`BM25_WEIGHT=0.4`、`VECTOR_WEIGHT=0.6`、`RRF_K=60`
- Chroma：`collection_name=interview_questions`、cosine 空间、答案/得分点存 metadata（检索不泄漏答案）
- jieba 分词做 BM25 中文检索

### 3.3 面试业务参数
- 8 岗位（`config.ROLES`）：python/java/frontend_dev/product_manager/general_hr/algorithm/devops/data_analyst；题库 86 题（python 16 / java 15 / frontend 15 / product 12 / general_hr 10 / algorithm 6 / devops 6 / data_analyst 6）
- 难度 1–3（Junior/Intermediate/Senior），默认 2；题量 1–20，默认 5
- **低分追问阈值**：初始分 `< 5` → 一次针对性追问，合并回答后重评得最终分
- **结束条件**：答满题量、或回答内容为 `quit/exit/q`、或前端发 `end`
- 单次回答 ≤ 5000 字；`resume_context` ≤ 6000 字；`resume_skills` ≤ 30 个
- 评分四维：accuracy/completeness/depth/clarity（各 1–10，总分=均值）
- 报告命名：`interview_report_{时间戳}_{thread_tag}_{role_key}.md/.json`

### 3.4 环境与版本（实测）
| 项 | 值 |
|---|---|
| 后端 | FastAPI + uvicorn `127.0.0.1:8000`（`python server.py` 或 uvicorn） |
| 前端 | Vite `127.0.0.1:3000`（proxy `/api`、`/ws` → 8000） |
| Python（venv） | 3.12.13（注意：记忆里写的 3.13.5 是系统解释器，venv 实为 3.12.13） |
| 关键包 | langgraph 1.2.10 · langchain 1.3.14 · langchain-chroma 1.1.0 · langchain-openai 1.4.2 · langchain-community 0.4.2 · fastapi 0.141.1 · chromadb 1.5.9 · pydantic 2.13.4 · sentence-transformers 5.7.0 · pdfplumber 0.11.10 |
| 前端依赖 | vue 3.4 · vue-router 4 · pinia 2.1（未实际使用）· echarts 6.1 + vue-echarts 8.1 · vite 5.4 |
| 登录 | 固定 `admin / 123123`，token=MD5(username+password+"interview")，后续接口不校验 |

### 3.5 测试现状
- `pytest` 全量：**10 通过 / 0 失败**（8 常规 + 2 graph 回归）
- ⚠️ Windows 环境：`tests/test_interview_graph.py` 的 `tmp_path` 清理会报 `.pytest_tmp PermissionError [WinError 5]`（文件被占用），测试本身通过；建议 `pytest --basetemp=<外部临时目录>` 规避
- 真实冒烟：`tests/real_smoke.py`（需后端已启动 + .env 配好 Key），完整走 2 题 + 追问 + 报告

---

## 4. 未解决问题

### 4.1 ⚠️ 当前稳定版**未提交**（最高优先级）
TOtal git 仓库（`dc97774 fix: stabilize LangGraph interview workflow`）提交之后，工作区有**未提交的删除与新增**，当前"稳定版"实际只存在于工作区：
- 已删未提交：`backend/Dockerfile`、`backend/.dockerignore`、`docker-compose.yml`、`cleanup_html.py`、`fix_encoding.py`、`backend/agent/{engine,memory,tools}.py`
- 新增未跟踪：`START_GUIDE.md`、`backend/tests/test_api_entrypoints.py`、`frontend/src/auth.js`
- 修改未提交：`README.md`、`backend/main.py`、`backend/retrieval/{embeddings,kb_builder}.py`、`backend/server.py`、`requirements.txt`、前端 `api/index.js`、`TopNav.vue`、`router/index.js`、多个 views、`vite.config.js` 等
- 顶层 `E:\hiagent\DEMO3` 还有一套**旧根仓库**（提交 0a45d3e/3dacf1f，跟踪含 `_archive/`），与 TOtal 仓库重叠；开发与提交请**只认 TOtal 仓库**

### 4.2 功能缺口
- **断线续接仅进程内**：checkpointer 用 `MemorySaver`，后端重启后 thread 丢失；磁盘级 `SqliteSaver`（langgraph-checkpoint-sqlite）未接入；`_sessions` 登记同样在进程内
- **graph 节点 history 未接入 Memory**：`emit_question`/`prepare_followup` 里 `"history": []` 恒为空；`compress_prompt`/`MEMORY_WINDOW_SIZE`/`MEMORY_COMPRESS_THRESHOLD` 配置存在但未生效
- **打字机逐字效果未做**：当前是 stream_chunk 实时刷新 + 闪烁光标
- **报告可靠性依赖外部 LLM**：DeepSeek 偶发中断时 AI 评价段降级为模板文字（已兜底，但报告不完整）
- **扫描图片型 PDF 不支持 OCR**：解析失败只能走"粘贴文本"入口
- **登录非生产级**：固定账号 + MD5 token + 后端不校验，仅答辩演示
- `EMBEDDING_ONLINE`（智谱在线嵌入回退）只有配置项，没有对应实现

### 4.3 工程遗留
- `langchain-community` BM25Retriever 已弃用警告（官方将停止维护，建议迁移）
- `backend/reports/interview_report.md` 是旧固定命名遗留文件（新报告均已带时间戳+ID）
- `agent/` 下有多份历史 `interview_records_*.md`（运行时产物，.gitignore 已排除）
- 前端 `pinia` 已装未用；HomeView 有营销数据（10,000+ 等）属演示占位
- `backend/.pytest_cache`、`.pytest_tmp` 存在权限问题（Windows 下无法删除，已 no-cacheprovider 规避）

### 4.4 已知风险
- 双服务演示（8000 + 3000）依赖本机 Node 与 Python 环境；`backend/static/` 单服务托管方案已移除（`test_backend_root_no_longer_serves_frontend` 断言 GET / 返回 404）
- BGE 模型若走 Hub 首次下载较慢（本地有快照可配 `LOCAL_BGE_MODEL_PATH` 加速）

---

## 5. 下一步建议

### 5.1 立即（答辩/交付前）
1. **提交当前工作树**为 TOtal 仓库新 commit（含删除与新增），让"稳定版"进入版本控制
2. 决定 Docker/static 方案去留：若答辩只需双服务，建议正式 `git rm` 掉 Docker 相关文件并同步更新文档（README 已写双服务，文档一致）

### 5.2 短期迭代（按优先级）
3. **磁盘级持久化**：接入 `langgraph-checkpoint-sqlite` 的 `SqliteSaver` + `_sessions` 落盘，实现重启后可续接面试
4. **Memory 摘要接入**：把 `records`/历史接入 `emit_question`/`prepare_followup` 的 `history` 参数，启用 `compress_prompt` 做长会话压缩
5. **前端体验**：实现打字机逐字效果（stream_chunk 按字缓冲渲染）
6. **补齐 EMBEDDING_ONLINE** 实现，或删除该配置避免误导

### 5.3 中期（生产化，答辩不做承诺）
7. 生产鉴权（JWT/会话 + 接口校验）、用户与面试记录落库
8. PDF OCR 兜底（如 PaddleOCR/RapidOCR）支持扫描件
9. `langchain-community` → 独立集成包迁移；CI（GitHub Actions：pytest + npm build）
10. 单服务部署回归（如需）：重建 `backend/static` 集成与 Dockerfile

### 5.4 继续开发速查
```powershell
# 后端（窗口1）
cd E:\hiagent\DEMO3\TOtal\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn server:app --host 127.0.0.1 --port 8000   # 或 python server.py

# 前端（窗口2）
cd E:\hiagent\DEMO3\TOtal\frontend
npm run dev -- --host 127.0.0.1    # http://127.0.0.1:3000，账号 admin/123123

# 题库变更后重建向量库
cd E:\hiagent\DEMO3\TOtal\backend && python main.py rebuild

# 测试（Windows 下建议外部临时目录）
python -m pytest -q -p no:cacheprovider --basetemp="$TEMP\pytest_demo3"
```

## 6. 修复记录 (2026-08-11, v0.2)

基于 2026-08-11 垃圾输入测试暴露的 4 个问题完成修复（已用 pytest 16/16 + 真实 LLM 冒烟验证）：

| # | 问题 | 修复 | 验证 |
|---|---|---|---|
| 1 | 追问"反馈句"虚构候选人言论（如说候选人提到过"JOIN方式"，实际只答了"dwdas"） | `agent/prompts.py`：FOLLOWUP_SYSTEM/USER 加反幻觉约束（反馈句只能引用候选人回答原文，命中/遗漏点与参考知识标注为"内部参考，禁止当作候选人说过"）；SCORER_SYSTEM 加"问题/提示内容不计入候选人得分" | 真实 LLM 部分回答触发追问，反馈句只引用候选人原文，无虚构 |
| 2 | 题库 py_015 标准答案句首缺失（`**A:** ，不是值传递…`） | `data/python_dev.md` 补全 py_015 答案（覆盖 3 个得分点）；`python main.py rebuild` 重建向量库；新增 `tests/test_data_integrity.py`（5 个用例：A 非空/不以标点开头/长度≥40/id 唯一/每岗位有题） | rebuild 后 86 题，Chroma 中 py_015 答案已验证完整 |
| 3 | 完全不会（1-2 分）也触发追问，浪费且观感假 | `agent/graph.py` `initial_score_router` 分档：`3 ≤ score < 7` 才追问，`<3`（完全不会/跑题）与 `≥7`（已答好）直接下一题；decision 文案同步更新 | 垃圾输入回归测试：2 题垃圾回答 0 次追问 |
| 4 | 合并重评"加分幻觉"（Q2 两个垃圾回答 1→2 分） | `agent/graph.py` `score_combined_node` 拼接去掉追问问题文本（只拼候选人两段回答） | 单元测试通过 |

**测试变化**：pytest 10 → 16 用例（改 `test_interview_graph.py` 低分用例 2→4 分，新增 `test_zero_or_low_score_skips_followup`；新增 `test_data_integrity.py` 5 用例；`tests/real_smoke.py` Q1 回答改"方向性但模糊"、追问断言放宽为 `[q1] 或 []`）。

**重启注意**：后端以 `D:\anaconda\envs\interview\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000` 运行（用户环境，非项目 .venv），无 `--reload`，改代码后需手动重启。

---

*本文件为交接文档，不替代 README/START_GUIDE；内容基于 2026-08-11 工作区静态审阅与测试复验。*
