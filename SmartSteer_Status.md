# SmartSteer — AI 模拟面试官 · 交接状态文档

> **生成日期**: 2026-08-11 (v0.3, 反幻觉 + 评分校准 + history 接线)
> **适用范围**: `E:\hiagent\DEMO3\TOtal`（当前主线工作区）
> **用途**: 在新窗口继续开发的交接文档。本文件只做"现状盘点"。
> **配套文档**: [README.md](README.md)、[START_GUIDE.md](START_GUIDE.md)、[SmartSteer_Status-v-0.1-v-.md](SmartSteer_Status-v-0.1-v-.md)（v0.1 交接，历史参考）、[PROJECT_EVALUATION_AND_OPTIMIZATION.md](PROJECT_EVALUATION_AND_OPTIMIZATION.md)（完成度评估，2026-08-09）

---

## 1. 已完成内容

### 1.1 核心架构：LangGraph 重构（阶段 0–1）
- 弃用旧 LangChain 手动状态机（`engine.py` 的 `Phase` 枚举 + 大量实例变量），改用 **LangGraph StateGraph** 编排：
  - `agent/state.py` — `InterviewState`（TypedDict）集中全部状态
  - `agent/graph.py` — 14 节点状态图：`configure → opening → prepare_question → emit_question → wait_answer → score_initial → (prepare_followup → emit_followup → wait_followup → score_combined) → finalize_question → ... → closing → wait_report → summary → END`
  - 3 个 `interrupt()` 等待节点（`wait_answer` / `wait_followup` / `wait_report`）实现"人在回路"
  - `MemorySaver` checkpointer 按 `thread_id` 保存暂停点
- **恢复安全语义**：`interrupt` 之前的节点不做随机选题 / LLM 调用 / 文件写入，恢复回答不会重复出题或重复输出；`prepare_question`（随机选题）已与 `emit_question`（流式输出）拆成独立节点。

### 1.2 功能增强（阶段 2–3）
- **题库扩充**：8 岗位、86 道题（data/*.md），`main.py build/rebuild` 构建 Chroma 向量库
- **报告体系**：summary 节点生成 Markdown 报告 + 雷达 JSON（四维均值/分类均值/逐题/强弱项）；REST 接口 `GET /api/reports`、`GET /api/reports/{id}`、`GET /api/reports/{id}/radar`；前端 ECharts 雷达图（`RadarChart.vue`）
- **会话登记与续接**：`_sessions` 进程内登记，`GET /api/interviews` 列出；`ws_chat` 支持带 `thread_id` 的 config 恢复会话
- **模型分层**：`LLM_MODEL_FAST`（出题/评分/追问/开场/收尾/压缩，求速度）vs `LLM_MODEL_STRONG`（总结报告，低温求质量）；标准答案缓存 `retriever._answer_cache`
- **WS 阶段协议**：`agent/protocol.py` 纯函数校验（`answer`/`end` 仅在 `await_answer`/`await_followup`，`report` 仅在 `await_report`）

### 1.3 反幻觉 + 评分校准 + history 接线（v0.3，本轮核心）

本轮针对"出题衔接环节的幻觉"做了系统性修复，并顺带补齐了 history 记忆和评分一致性。**经真实 LLM 验证：全垃圾回答 0 幻觉，正常回答面试官能精准回指候选人具体内容。**

#### 1.3.1 出题/收尾衔接反幻觉
- **根因**：`_build_prev_context` 把评分链的 `hit_points`/`missed_points`（评分依据）当作"候选人回答要点/可衔接方向"喂给出题 LLM，出题 LLM 是"冷"的（没读过候选人原话），于是把评分链转述的内容当成候选人说过的话复述——产生"你刚刚提到了..."幻觉。
- **修复**：`graph.py` `_build_prev_context` 重构——出题衔接**只读候选人原文 + 表现档位**，完全不接触评分产出。低分（score<3）时额外提示"不可虚构候选人说过的话"。`closing_node` 同理：低分时不传 hit/missed 内容。
- **prompt 加固**：`prompts.py` QUESTION/CLOSING 补反幻觉约束（镜像已有 FOLLOWUP 规则7/8）：反馈句只能基于候选人回答原文；过短/跑题时直接说明无法判断，绝不虚构。
- **验证**：算法岗 5 题全垃圾回答（"不知道/不清楚/哈哈/有吗"），5 段衔接全部诚实反映"没答"，0 处把标准答案安到候选人头上。

#### 1.3.2 评分总分一致性校准（④）
- **问题**：`RobustScoreParser._dict_to_result` 直接信任 LLM 顶层 `score` 字段，不按四维均值校准——出现 score=0 但四维全 1 的自相矛盾（垃圾输入测试 Q1 暴露）。
- **修复**：`chains.py` 解析出 `score_breakdown` 后，以四维均值为基准兜底：
  - 偏差 > 2 → 采用均值
  - 方向性矛盾（score=0 但均值≥1，或 score≥1 但均值=0）→ 采用均值
  - 正数四舍五入用 `int(x+0.5)`，避免 `round()` 的银行家舍入
- **影响**：追问分档阈值（3–7）依赖这个 score，校准后分档更可靠。

#### 1.3.3 对话历史 history 接线（①）
- **背景**：交接文档(v0.1)列 `agent/memory.py` 为"已删未提交"，但核实发现它在 HEAD(dc97774) 里是**完整的 `ConversationSummaryBuffer` 实现**——`maybe_compress()` / `get_history_for_chain()` / 压缩失败 fallback 硬截断，全部就绪。本轮 `git checkout` 恢复并接线。
- **接线**：`graph.py` 5 个节点接入 `InterviewMemory`（按 thread_id 闭包字典管理，不进 state 因不可序列化）：
  - `opening_node`：开场白入记忆（AI 消息）
  - `emit_question_node`：读 history + 出题文本入记忆
  - `wait_answer_node`：候选人回答入记忆（Human 消息）
  - `emit_followup_node` / `wait_followup_node`：追问文本 + 补充回答入记忆
  - `finalize_question_node`：每轮结束触发 `maybe_compress()`
  - `prepare_followup_node`：读 history
- **摘要护栏**（B + 两条护栏）：
  - `compress_prompt` 改为"话题级"摘要——只记主题方向/表现档位，**不得逐字引用候选人原话或具体技术细节**
  - QUESTION/FOLLOWUP prompt 补规则9：对话历史中 `[之前对话摘要]` 只可话题级引用，**严禁逐字引用**——逐字引用只允许来自窗口内原始消息
- **验证**：算法岗 3 题正常回答，面试官能精准回指候选人具体内容（如"归并排序和二分查找这两个例子选得很典型"），体现连续心智。

#### 1.3.4 节点间数据契约系统化（②）
- **契约定义**：
  - 评分链产出（hit_points/missed_points/score_breakdown）→ **只进报告**，禁止回流出题衔接
  - 出题衔接（`_build_prev_context`）→ **只读候选人原文 + history**，不读评分产出
  - 追问链（`prepare_followup_node`，同题内深挖）→ **可读评分产出**作为追问方向依据，但 prompt 约束"禁止当作候选人说过"
- `graph.py` 相关节点已加契约注释。

### 1.4 工程与质量
- **测试**：pytest **27/27 通过**（协议 4 + 评分解析 5 + API 入口 + 数据完整性 5 + LangGraph 全流程 6 + memory 5 + 其他）。真实 LLM 冒烟脚本 3 个：`real_smoke.py`（2题流程）、`real_smoke_antihall.py`（反幻觉）、`real_smoke_history.py`（连续心智）
- **清理**：删除 `engine.py`、`tools.py`、Docker 相关文件、`cleanup_html.py`/`fix_encoding.py`（工作区已删，未提交）；`common.py` 去重；`get_embeddings` 下沉 `retrieval/embeddings.py` 破循环依赖
- **文档**：README.md、START_GUIDE.md 已更新为本机双服务启动方式

---

## 2. 当前代码结构

```text
E:\hiagent\DEMO3\                  ← 顶层（旧根仓库，含 _archive 归档，非主线）
└── TOtal\                         ← ★ 当前主线（独立 git 仓库, HEAD=dc97774）
    ├── README.md / START_GUIDE.md / SmartSteer_Status.md ← 本文件
    ├── SmartSteer_Status-v-0.1-v-.md  ← v0.1 交接（历史参考）
    ├── OPTIMIZATION_PLAN.md / PROJECT_EVALUATION_AND_OPTIMIZATION.md
    ├── backend/
    │   ├── server.py              FastAPI 入口：REST + WebSocket /ws/chat（graph 驱动）
    │   ├── main.py                题库 build/rebuild 入口
    │   ├── config.py              全局配置（路径/检索/模型/角色/难度/评分维度/MEMORY_*）
    │   ├── common.py              跨模块公共工具（岗位匹配/技能提取/JSON 容错/难度标签）
    │   ├── .env.example           API Key 与模型配置模板（已存在 backend/.env）
    │   ├── agent/
    │   │   ├── graph.py           StateGraph 14 节点 + interrupt + memory 接线（核心）
    │   │   ├── state.py           InterviewState TypedDict
    │   │   ├── memory.py          InterviewMemory: ConversationSummaryBuffer（①恢复+接线）
    │   │   ├── protocol.py        WS 阶段约束（answer/end/report 允许阶段）
    │   │   ├── chains.py          LCEL Chain 工厂 + RobustScoreParser（④总分校准）
    │   │   ├── prompts.py         8 套 ChatPromptTemplate（含反幻觉约束+摘要护栏）
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
    │   ├── data/                  8 岗位题库 .md（86 题，`### Q/A/S` + `<!-- id|category|difficulty -->`）
    │   ├── reports/               生成的报告（.md + .json 雷达对）
    │   ├── tests/                 见 §2.1
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

### 2.1 测试文件

| 文件 | 用途 | 用例数 |
|---|---|---|
| `test_protocol.py` | WS 阶段协议校验 | 4 |
| `test_score_parser.py` | 评分解析 + ④总分校准 | 5 |
| `test_api_entrypoints.py` | REST API 入口 | — |
| `test_data_integrity.py` | 题库数据完整性 | 5 |
| `test_interview_graph.py` | LangGraph 全流程（FakeLLM）+ 反幻觉 prev_context | 6 |
| `test_memory.py` | InterviewMemory 接线（①） | 5 |
| `real_smoke.py` | 真实 LLM 冒烟（2题流程） | 手动 |
| `real_smoke_antihall.py` | 真实 LLM 反幻觉（全垃圾回答） | 手动 |
| `real_smoke_history.py` | 真实 LLM 连续心智（正常回答） | 手动 |

### 2.2 核心数据流

```text
登录(admin/123123) → Home → 简历匹配(ResumeUpload→JobMatching) 或 自主选岗(ChooseJob)
  → InterviewView: sessionStorage.selectedRole → connect → sendConfig
  → server: /ws/chat config → run_graph_stream(initial_state, thread_id)
  → graph: configure→opening(入memory)→prepare_question→emit_question(读memory+入memory)→wait_answer(interrupt)
  → 前端输入回答 → answer 消息 → Command(resume) → wait_answer(入memory)→score_initial
  → score 3-6: prepare_followup(读memory)→emit_followup(入memory)→wait_followup(入memory)→score_combined
  → finalize_question(触发maybe_compress) → 循环或 closing → wait_report(interrupt) → report → summary
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

### 3.1 模型与 API（backend/.env）
| 参数 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 必填（兼容 `DEEPSEEK_API_KEY`） | DeepSeek Key |
| `LLM_BASE_URL` | `https://api.deepseek.com` | 换智谱需改 base_url + model |
| `LLM_MODEL` | `deepseek-chat` | 兼容旧引用 |
| `LLM_MODEL_FAST` | `deepseek-chat` | 出题/评分/追问/开场/收尾/压缩 |
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

### 3.3 记忆（config.py，① 接线后生效）
| 参数 | 值 | 说明 |
|---|---|---|
| `MEMORY_WINDOW_SIZE` | 10 | 保留最近 N 条消息（压缩时） |
| `MEMORY_COMPRESS_THRESHOLD` | 6000 | 对话超过此字符数触发摘要压缩 |

- 压缩策略：超阈值 → 保留最近 window_size 条 → 旧消息过 `compress_prompt` 压成话题级摘要 → 以 `[之前对话摘要]` SystemMessage 前置
- 压缩失败 fallback：硬截断保留最近消息（不崩）
- memory 按 thread_id 闭包字典管理，**进程内**（不随 checkpointer 持久化，见 §4.1）

### 3.4 面试业务参数
- 8 岗位（`config.ROLES`）：python/java/frontend_dev/product_manager/general_hr/algorithm/devops/data_analyst；题库 86 题
- 难度 1–3（Junior/Intermediate/Senior），默认 2；题量 1–20，默认 5
- **低分追问阈值**：初始分 `3 ≤ score < 7` → 一次针对性追问，合并回答后重评；`<3`（完全不会/跑题）与 `≥7`（已答好）直接下一题
- **评分总分校准**（④）：顶层 score 与四维均值偏差>2 或方向性矛盾时，以四维均值为准
- 结束条件：答满题量、或回答内容为 `quit/exit/q`、或前端发 `end`
- 单次回答 ≤ 5000 字；`resume_context` ≤ 6000 字；`resume_skills` ≤ 30 个
- 评分四维：accuracy/completeness/depth/clarity（各 1–10，总分=均值，经校准）
- 报告命名：`interview_report_{时间戳}_{thread_tag}_{role_key}.md/.json`

### 3.5 环境与版本（实测）
| 项 | 值 |
|---|---|
| 后端 | FastAPI + uvicorn `127.0.0.1:8000`（`python server.py` 或 uvicorn） |
| 前端 | Vite `127.0.0.1:3000`（proxy `/api`、`/ws` → 8000） |
| Python | 项目 `.venv` 为 3.12.13（有 pytest+pytest-asyncio）；用户日常用 `D:\anaconda\envs\interview` 环境（无 pytest，跑服务用） |
| 关键包 | langgraph 1.2.10 · langchain 1.3.14 · langchain-chroma 1.1.0 · langchain-openai 1.4.2 · langchain-community 0.4.2 · fastapi 0.141.1 · chromadb 1.5.9 · pydantic 2.13.4 · sentence-transformers 5.7.0 · pdfplumber 0.11.10 |
| 前端依赖 | vue 3.4 · vue-router 4 · pinia 2.1（未实际使用）· echarts 6.1 + vue-echarts 8.1 · vite 5.4 |
| 登录 | 固定 `admin / 123123`，token=MD5(username+password+"interview")，后续接口不校验 |

### 3.6 测试现状
- `pytest` 全量：**27 通过 / 0 失败**（用 `.venv` 跑；`D:\anaconda\envs\interview` 无 pytest）
- ⚠️ Windows 环境：`test_interview_graph.py` 的 `tmp_path` 清理会报 `.pytest_tmp PermissionError [WinError 5]`（文件被占用），测试本身通过；建议 `pytest --basetemp=<外部临时目录>` 规避
- 真实冒烟：3 个脚本（见 §2.1），需后端已启动 + .env 配好 Key

---

## 4. 未解决问题

### 4.1 ⚠️ 当前所有成果**未提交**（最高优先级）
TOtal git 仓库（`dc97774`）之后，工作区有大量未提交变更（v0.2 追问修复 + v0.3 反幻觉/校准/history 全部未提交）：
- **修改未提交**：`agent/{chains,graph,prompts}.py`、`data/python_dev.md`、`main.py`、`retrieval/{embeddings,kb_builder}.py`、`server.py`、`requirements.txt`、前端多文件
- **新增未跟踪**：`START_GUIDE.md`、`SmartSteer_Status*.md`、`tests/{test_api_entrypoints,test_data_integrity,test_memory,real_smoke_antihall,real_smoke_history}.py`、`frontend/src/auth.js`
- **已删未提交**：`backend/{Dockerfile,.dockerignore}`、`docker-compose.yml`、`cleanup_html.py`、`fix_encoding.py`、`agent/{engine,tools}.py`
- `agent/memory.py` 已从 HEAD 恢复（git checkout），状态干净，无需重新提交
- 顶层 `E:\hiagent\DEMO3` 还有一套旧根仓库，与 TOtal 仓库重叠；开发与提交**只认 TOtal 仓库**

### 4.2 功能缺口
- **断线续接仅进程内**：checkpointer 用 `MemorySaver`，后端重启后 thread 丢失；`InterviewMemory` 闭包字典同样进程内——重启后对话历史也丢。磁盘级 `SqliteSaver`（langgraph-checkpoint-sqlite）未接入（见 §5.2）。**注意**：接 SqliteSaver 后，InterviewMemory 的进程内字典与 checkpointer 持久化会不一致，需统一方案（见 §5.2）。
- **打字机逐字效果未做**：当前是 stream_chunk 实时刷新 + 闪烁光标
- **报告可靠性依赖外部 LLM**：DeepSeek 偶发中断时 AI 评价段降级为模板文字（已兜底，但报告不完整）
- **扫描图片型 PDF 不支持 OCR**：解析失败只能走"粘贴文本"入口
- **登录非生产级**：固定账号 + MD5 token + 后端不校验，仅答辩演示
- `EMBEDDING_ONLINE`（智谱在线嵌入回退）只有配置项，没有对应实现

### 4.3 工程遗留
- `langchain-community` BM25Retriever 已弃用警告（官方将停止维护，建议迁移）
- `backend/reports/interview_report.md` 是旧固定命名遗留文件（新报告均已带时间戳+ID）
- 前端 `pinia` 已装未用；HomeView 有营销数据（10,000+ 等）属演示占位
- `backend/.pytest_cache`、`.pytest_tmp` 存在权限问题（Windows 下无法删除）

### 4.4 已知风险
- 双服务演示（8000 + 3000）依赖本机 Node 与 Python 环境；`backend/static/` 单服务托管方案已移除
- BGE 模型若走 Hub 首次下载较慢（本地有快照可配 `LOCAL_BGE_MODEL_PATH` 加速）
- **真实 LLM 幻觉可能随模型版本漂移回归**：v0.3 的反幻觉是结构性修复（出题链不接触评分产出），但 prompt 约束对强 LLM 不可靠——需用 `real_smoke_antihall.py` 定期回归

---

## 5. 下一步建议

### 5.1 立即
1. **提交当前工作树**为 TOtal 仓库新 commit（含 v0.2 追问修复 + v0.3 反幻觉/校准/history 全部改动），让成果进入版本控制
2. 决定 Docker/static 方案去留：若只需双服务，建议正式 `git rm` 掉 Docker 相关文件并同步文档

### 5.2 短期迭代（按优先级）
3. **磁盘级持久化**（③）：接入 `langgraph-checkpoint-sqlite` 的 `SqliteSaver`。**关键设计点**：当前 `InterviewMemory` 是进程内闭包字典，接 SqliteSaver 后需统一——方案一是把消息列表序列化进 `InterviewState`（随 checkpointer 持久化），方案二是 memory 也落盘。推荐方案一：state 加 `history: List[Dict]` 字段，节点内就地压缩（放弃 InterviewMemory 实例，复用其压缩逻辑）。
4. **幻觉扫描断言基线**（⑥）：把 `real_smoke_antihall.py` 的幻觉检查（"你刚刚提到/你刚才提到/你提到了/正如你所说"等措辞扫描）固化成可重复的回归断言。**作用**：决定 ⑦（模型分层）是否需要——若当前 FAST 模型在接 history 后幻觉率已达标，⑦ 就没必要做，省延迟和成本。让 ⑥ 的数据决定 ⑦。
5. **前端体验**：实现打字机逐字效果（stream_chunk 按字缓冲渲染）
6. **补齐 EMBEDDING_ONLINE** 实现，或删除该配置避免误导

### 5.3 中期（生产化）
7. 生产鉴权（JWT/会话 + 接口校验）、用户与面试记录落库
8. PDF OCR 兜底（如 PaddleOCR/RapidOCR）支持扫描件
9. `langchain-community` → 独立集成包迁移；CI（GitHub Actions：pytest + npm build）

### 5.4 继续开发速查
```powershell
# 后端（窗口1）—— 注意用加载了最新代码的环境
cd E:\hiagent\DEMO3\TOtal\backend
D:\anaconda\envs\interview\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
#   (用户日常环境, 无 --reload, 改代码后需手动重启; 无 pytest)
#   或用 .venv (有完整依赖含 pytest): .\.venv\Scripts\Activate.ps1 && python -m uvicorn server:app --host 127.0.0.1 --port 8000

# 前端（窗口2）
cd E:\hiagent\DEMO3\TOtal\frontend
npm run dev -- --host 127.0.0.1    # http://127.0.0.1:3000，账号 admin/123123

# 题库变更后重建向量库
cd E:\hiagent\DEMO3\TOtal\backend && python main.py rebuild

# 测试（用 .venv，Windows 下建议外部临时目录）
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp="$TEMP\pytest_demo3"

# 真实 LLM 冒烟（需后端已启动 + .env 配好 Key）
.\.venv\Scripts\python.exe tests/real_smoke_antihall.py   # 反幻觉(全垃圾回答)
.\.venv\Scripts\python.exe tests/real_smoke_history.py    # 连续心智(正常回答)
.\.venv\Scripts\python.exe tests/real_smoke.py            # 2题完整流程
```

---

## 5.5 补充变更记录 (2026-08-11 晚, v0.3.1, 未提交)

用户拍板后执行的小迭代（**仍未提交**，与 v0.3 变更一起在工作区）：

| 变更 | 内容 | 验证 |
|---|---|---|
| 打字机逐字效果 | `useWebSocket.js`：chunk 进 pending 缓冲，24ms 定时器逐字释放（积压>30字×3、>80字×6 自适应加速）；`stream_end` 延迟到吐完才解除 streaming；report 流旁路直显 | npm build 通过 |
| Docker 正式移除 | `git rm --cached` 已暂存 `backend/Dockerfile`、`backend/.dockerignore`、`docker-compose.yml` 删除（按用户要求不提交） | git status 确认 |
| `EMBEDDING_ONLINE` 删除 | 该配置无实现、属误导项；已从 `config.py`、`.env.example` 移除（用户 .env 本就未配置） | pytest 27/27 |
| 报告兜底增强 | `summary_node`：强模型失败 → 降级 FAST 模型重试（同 prompt）→ 双失败才用模板；降级时报告与雷达 JSON（`ai_summary_mode`: strong/fast_fallback/template）均显式标注 | pytest 27/27 |
| 工程清理 | 删除旧固定命名 `reports/interview_report.md`；卸载未使用的 pinia（main.js + package.json）；HomeView 虚构营销数字（10,000+/500+/95%）替换为真实数据（8 岗位/86 题/4 维评估） | npm build 通过 |

**用户明确不做**：git 提交、幻觉回归断言化（用户亲自手动测试）、SqliteSaver 磁盘持久化。

**v0.3.2 追加（同日晚，仍未提交）**：

| 变更 | 内容 | 验证 |
|---|---|---|
| 千问视觉读简历（扫描件兜底） | 新增 `resume/vision_parser.py`：PyMuPDF 渲染 PDF 页为 PNG（150dpi，≤5页）→ base64 → qwen-vl（DashScope OpenAI 兼容接口，直连 `openai` SDK）→ 一次性输出「全文转写+ResumeInfo 字段」JSON；`parser.py` 在 pdfplumber 提取为空时接入该兜底。配置：`DASHSCOPE_API_KEY`（系统环境变量，用户已配）+ `VISION_MODEL`（默认 qwen-vl-plus）+ `VISION_BASE_URL`；未配置 Key 时 `vision_available()=False`，行为与接入前一致。返回 dict 带 `parse_mode: "vision"` 标识 | pytest 27/27；真实视觉调用待用户实测扫描件 |
| 语音输入 | `InterviewView.vue` 输入框旁加🎤按钮，Web Speech API（`webkitSpeechRecognition`，zh-CN，continuous+interim）；interim 实时显示、final 累积拼接在已有文字后；不支持浏览器（Firefox）自动隐藏按钮；后端零改动 | npm build 通过 |
| 依赖 | `requirements.txt` 增加 `pymupdf>=1.24.0`（两个 Python 环境均已安装） | — |

---

## 6. 本轮修复记录 (2026-08-11, v0.3)

针对"出题衔接环节幻觉"做的系统性修复，并顺带补齐 history 记忆和评分一致性。**真实 LLM 验证通过。**

| # | 问题 | 根因 | 修复 | 验证 |
|---|---|---|---|---|
| 1 | 下一题开场"你刚刚提到了XX"，把标准答案/评分 hit_points 安到候选人头上 | `_build_prev_context` 把评分链的 hit/missed 当"候选人回答要点"喂给出题 LLM；出题链是"冷"的，没读过候选人原话 | 出题衔接只读候选人原文+档位，切断评分回流；prompt 补反幻觉约束；closing 同理 | 全垃圾回答 5 段衔接 0 幻觉 |
| 2 | 评分 score=0 但四维全 1（Q1），总分与维度不一致 | `RobustScoreParser` 直接信任 LLM 顶层 score，不按四维均值校准 | 四维均值兜底（偏差>2 或方向性矛盾时采用均值） | 3 用例覆盖 |
| 3 | `history: []` 恒为空，面试官无连续心智，被迫依赖转述桥（幻觉根源之一） | memory.py 被误删（HEAD 里完整），节点未接线 | 恢复 memory.py + 5 节点接线 + 摘要护栏（话题级、禁逐字引用） | 正常回答面试官能精准回指候选人具体内容 |
| 4 | 节点间数据契约不显式，评分产出可回流出题链 | 无系统约束 | 契约文档化：出题衔接不读评分产出，追问同题内可读但禁当原话 | 更新断言 |

**测试变化**：pytest 16 → 27 用例（新增 test_score_parser 3 + test_memory 5 + test_interview_graph 反幻觉断言更新）。

---

## 7. v0.5 变更记录 (2026-08-25)

### 7.1 新增岗位：大模型应用开发工程师（llm_app）

- `config.py` ROLES 新增 `llm_app`：标题"大模型应用开发工程师"，tags 含 Agent/RAG/大模型/Prompt工程/向量检索/工具调用/Embedding/LangChain
- 前端选岗页通过 `/api/roles` 动态读取，**无需改前端代码**自动显示新岗位
- `test_api_entrypoints.py` 岗位数断言改为动态读 `config.ROLES`（8 → 9 后不再硬编码）

### 7.2 题库重建：llm_app 岗位 9 方面 47 题

| 方面 | 题数 | ID 范围 |
|---|---|---|
| RAG（含文本分块专项） | 14 | `llm_rag_001` ~ `llm_rag_014` |
| Transformer | 8 | `llm_transformer_001` ~ `llm_transformer_008` |
| 微调（Prompting/PEFT/LoRA 系列） | 7 | `llm_ft_001` ~ `llm_ft_007` |
| 提示词工程 | 4 | `llm_prompt_001` ~ `llm_prompt_004` |
| 部署（Docker 部署 Coze） | 4 | `llm_deploy_001` ~ `llm_deploy_004` |
| Skills | 3 | `llm_skills_001` ~ `llm_skills_003` |
| Memory | 3 | `llm_memory_001` ~ `llm_memory_003` |
| MCP | 2 | `llm_mcp_001` ~ `llm_mcp_002` |
| 工具调用 | 2 | `llm_tool_001` ~ `llm_tool_002` |

难度分布：初级 2 / 中级 26 / 高级 19。全部为 `type:scenario` 场景题（含 SCENARIO 场景 + FOLLOWUP 预设追问 + GOOD/BAD 好差答案）。`main.py rebuild` 后向量库共 133 题（原 86 + 47）。

### 7.3 题库格式扩展（支持场景题 + 好差答案）

`data/*.md` 新格式（向后兼容旧题，`type` 缺省 `knowledge`）：

```markdown
---
<!-- id:llm_rag_001 | category:RAG | difficulty:2 | difficulty_label:中级 | type:scenario -->
### Q: ...
### SCENARIO: ...     # 场景背景（场景题必写）
### A: ...
### S:               # 知识题=得分点, 场景题=评分要点(≥3条)
- ...
### GOOD:            # 好答案特征（报告"好答案 vs 差答案"对比用）
- ...
### BAD:             # 差答案特征
- ...
### FOLLOWUP:        # 预设追问方向（场景题≥2条）
- ...
```

### 7.4 代码改造：GOOD/BAD 全链路 + 开放题评分

| 文件 | 改动 |
|---|---|
| `retrieval/kb_builder.py` | 解析 `type` 元信息 + `SCENARIO/GOOD/BAD/FOLLOWUP` 字段；检索文本拼入场景/分类/题型提高命中率；metadata 存 good_points/bad_points |
| `retrieval/retriever.py` | `get_answer()` 返回 `type/scenario/good_points/bad_points/followup_directions` |
| `agent/graph.py` | ① `score_candidate()` 按题型分支：场景题把 S 当"评分要点"并注入开放题评分指令（方案合理即可，不因未提及扣分）；② 追问优先用题库 `followup_directions`；③ 出题传 `scenario` 自然引入；④ record/雷达 JSON 记录 good/bad；⑤ 报告正文增加"好答案 vs 差答案"对比段 |
| `agent/prompts.py` | SCORER 支持 `scoring_instruction`（开放题规则）；QUESTION 支持场景铺垫（规则10） |
| `frontend/src/views/SummaryView.vue` | 新增"🆚 好答案 vs 差答案"对比卡片（绿=高分特征 / 红=踩坑特征） |
| `tests/test_data_integrity.py` | 新增 2 个场景题校验（SCENARIO+FOLLOWUP≥2 / S≥3） |

### 7.5 验证结果

| 验证项 | 结果 |
|---|---|
| 向量库重建 | ✅ 133 题（llm_app 47 题全部入库，9 个分类齐全） |
| 检索"RAG 幻觉" | ✅ 精准命中 llm_rag_008/007/003 |
| get_answer 新字段 | ✅ type/scenario/good/bad/followup 全部返回 |
| pytest | ✅ 23/23 通过（含 2 个新场景题校验） |
| npm build | ✅ 通过（SummaryView 新增对比卡片） |

---

*本文件为交接文档，不替代 README/START_GUIDE；内容基于 2026-08-25 工作区代码审阅与验证。*
