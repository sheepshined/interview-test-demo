# SmartSteer — AI 模拟面试官 · 交接状态文档

> **生成日期**: 2026-08-27 (v0.10, 知识库 AI 对话: 会话持久化 + RAG 上下文修复 + 面试记录删除 + 开场白优化)
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
- **测试**：pytest **45/45 通过**（v0.6 后: 认证 14 + 协议 4 + 评分解析 5 + API 入口 5 + 数据完整性 7 + LangGraph 全流程 6 + memory 5 等）。真实 LLM 冒烟脚本 3 个：`real_smoke.py`（2题流程）、`real_smoke_antihall.py`（反幻觉）、`real_smoke_history.py`（连续心智）；鉴权冒烟 1 个：`real_smoke_auth.py`（登录/401/注册/WS 握手，无需 LLM Key）
- **清理**：删除 `engine.py`、`tools.py`、Docker 相关文件、`cleanup_html.py`/`fix_encoding.py`（工作区已删，未提交）；`common.py` 去重；`get_embeddings` 下沉 `retrieval/embeddings.py` 破循环依赖
- **文档**：README.md、START_GUIDE.md 已更新为本机双服务启动方式

### 1.5 生产级鉴权（v0.6，2026-08-25 本轮核心）

替换"固定账号 + MD5 token + 后端不校验"的演示级登录为完整用户体系（§8 详表）：

- **用户存储**：SQLite `backend/users.db`（gitignored），首次启动自动建表并预置演示账号 `admin/123123`（答辩兼容）；密码 bcrypt 哈希（盐随机）
- **认证**：JWT (pyjwt, HS256, 默认 24h 过期)；签名密钥优先 `.env` 的 `JWT_SECRET_KEY`，未配置自动生成并落盘 `backend/.jwt_secret`（gitignored）
- **全接口校验**：除 `POST /api/login`、`POST /api/register` 外所有 REST 接口经 `Depends(get_current_user)` 校验 `Authorization: Bearer`；`/ws/chat` 握手校验 query 参数 `?token=<jwt>`，无效拒绝握手（HTTP 403）
- **开放注册**：`POST /api/register`（用户名 3-20 位字母/数字/下划线，密码 ≥6 位 ≤72 字节）；前端登录页支持注册模式，注册即登录
- **数据按用户隔离**：
  - 报告 JSON 新增 `username` 字段（`graph.py` summary_node 从 state 写入，WS config 时由 server 注入）；`/api/reports` 列表与详情/雷达仅返回归属用户的报告；**旧报告（无 username 字段）归 admin**
  - `/api/interviews` 会话列表按 username 过滤；WS 恢复他人 thread_id 会被拒绝
- **前端**：`api/index.js` 自动携带 Bearer + 401 自动清登录态跳登录页；`auth.js` 本地解析 JWT 过期时间（不再硬编码校验 admin）；`useWebSocket.js` 握手带 token
- **验证**：pytest 45/45；真实服务冒烟 7/7（登录签发/无 token 401/伪造 token 401/有效 token 200/注册/新用户隔离/WS 握手拒绝与放行）

### 1.6 个人知识库（v0.7，2026-08-25 本轮核心）

Obsidian 式个人知识库 + 全局侧边栏布局（§9 详表）：

- **全局侧边栏**：登录后所有页面统一 AppLayout（分组导航：面试流程/个人知识库 + 用户区，可收起）；TopNav 精简为返回条
- **双链笔记**：`[[标题]]` wiki 语法；链接是**解析出来的衍生视图**（单一数据源），笔记表不存边
- **知识图谱**：Cytoscape.js 力导向布局（cose）；节点大小=连接数；hover 高亮邻居（Obsidian 式聚焦）；**虚节点**=链接到不存在的标题（灰色虚线圆），点击即创建
- **编辑器**：vditor（即时渲染模式，中文界面）；编辑页侧栏实时显示"链接到/反向链接"
- **报告联动**：SummaryView 学习建议区「📥 存入知识库」按钮，薄弱点批量建笔记（source=interview_report，自动打"面试薄弱点"标签，同名跳过）
- **数据**：SQLite `backend/knowledge.db`（gitignored），按 username 隔离，走 v0.6 JWT
- **验证**：pytest 58/58（+13 知识库用例）；真实冒烟 7/7；npm build 通过

### 1.7 知识库增强（v0.8，2026-08-25 本轮核心）

按用户拍板的三原则实施：**题库与知识库完全隔离**、**文件解析全走模型**、**效果优先不计开销**（§10 详表）：

- **文件入库**：`.md/.txt/.pptx/.docx/.pdf` 多文件批量上传（≤10个/次、50MB/个，v0.9 放宽）；原文提取后过 **STRONG 模型**输出结构化 Markdown 笔记+分类+标签；扫描 PDF 走千问视觉转写（20页）；LLM 失败降级原文直入（上传永不中断）
- **网址收藏**：`{url, title, description必填}`——不抓网页（用户拍板），描述是检索主体；检索命中返回 `source_url` 可直接打开
- **语义检索**：独立 Chroma 集合 `kb_notes`（与题库 `interview_questions` 互不干扰），BGE 嵌入，笔记增删改同步向量；`/api/kb/search` 返回 top-5 + 相关度
- **缺失提示**：top1 相关度 < 0.35 → `sparse` 标记 → 前端黄条「建议导入对应资料」
- **报告覆盖检测**：薄弱点入库后逐条检索（**排除本轮新建笔记自身**，防"自我覆盖"误判）；报告页显示「✓ 已有 N 条相关（可点击跳转）/ ⚠ 无覆盖建议导入」
- **分类体系**：自定义分类（datalist 下拉+自由输入）+ 🤖 AI 分类建议（优先归入已有分类；手动分类永远优先）
- **编辑页增强**：✨ AI 整理（内容重排结构化）、🔍 语义检索面板（打开即默认检索当前标题；结果一键**插入 [[链接]]** 固化为显式双链）
- **图谱升级**（用户点名要配色）：**节点按类型着色**（笔记蓝#2563eb/文件绿#16a34a/网址橙#ea580c/虚节点灰）、分类多选过滤、「显示语义边」开关、**语义边=淡紫虚线**（vs 手写双链实线，hover 高亮）、🔄 重建索引按钮（向量+语义关联全量重建）
- **验证**：pytest 72/72（+14 v0.8 用例）；真实冒烟 9/9（含 BGE 真实检索、语义关联重建、覆盖检测）；npm build 通过

### 1.8 知识库 AI 对话 + 面试体验优化（v0.10，2026-08-27 本轮核心）

参考 FastGPT/Dify 等优秀开源案例实现的 RAG 对话模块（§12 详表）：

- **RAG AI 对话**：左侧会话列表 + 右侧聊天区双栏布局；后端 SQLite 持久化（`kb_chat_sessions`/`kb_chat_messages` 表），刷新/跳转后对话不丢；每条 AI 回答下方展示参考来源卡片（笔记标题+相关度%，点击跳转笔记）
- **RAG 上下文修复**：检索时回查 SQLite 拉取笔记全文（每条 4000 字）替代原来 120 字摘要——解决"解读文档只输出开篇"问题；提示词改为要求详尽解读、覆盖全部核心要点
- **面试记录删除**：`DELETE /api/interview-records/{filename}`（文件名正则校验+用户隔离）；独立记录页与面试页侧栏均支持悬停删除+确认
- **开场白优化**：`prompts.py` OPENING_SYSTEM/QUESTION_SYSTEM 强制开场白与首题分离、禁止内部元数据（题号）
- **验证**：后端重启实测；对话持久化/参考来源跳转/记录删除均手工验证通过

---

## 2. 当前代码结构

```text
E:\hiagent\DEMO3\                  ← 顶层（旧根仓库，含 _archive 归档，非主线）
└── TOtal\                         ← ★ 当前主线（独立 git 仓库, HEAD=dc97774）
    ├── generate-ppt.mjs           项目演示 PPT 生成脚本（PptxGenJS, 12页, v0.10）
    ├── README.md / START_GUIDE.md / SmartSteer_Status.md ← 本文件
    ├── SmartSteer_Status-v-0.1-v-.md  ← v0.1 交接（历史参考）
    ├── OPTIMIZATION_PLAN.md / PROJECT_EVALUATION_AND_OPTIMIZATION.md
    ├── backend/
    │   │   ├── server.py              FastAPI 入口：REST + WebSocket /ws/chat（graph 驱动, v0.6 全接口鉴权, v0.7 /api/kb/*, v0.9 /kb_files 静态目录, v0.10 /api/kb/qa+chat会话 + 面试记录删除）
    │   ├── auth.py                认证模块：SQLite 用户表 + bcrypt + JWT + FastAPI 依赖/WS 握手校验 (v0.6)
    │   ├── knowledge.py           个人知识库：notes 表 + [[链接]]解析 + 图谱/反链构建 + 报告入库 (v0.7) + 表迁移/文件路径迁移 (v0.9) + chat 会话/消息持久化 (v0.10)
    │   ├── kb_extract.py          文件原文提取：md/txt/pptx/docx/pdf + 扫描件千问视觉转写 (v0.8)
    │   ├── kb_llm.py              LLM 结构化/AI 分类/AI 整理（STRONG 模型, 失败降级）(v0.8)
    │   ├── kb_vectors.py          知识库向量库：kb_notes 集合 + 语义检索 + sem_links 重建 (v0.8)
    │   ├── main.py                题库 build/rebuild 入口
    │   ├── config.py              全局配置（路径/检索/模型/角色/难度/评分维度/MEMORY_*/认证/知识库）
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
    │   │   ├── vision_parser.py   千问视觉扫描件解析（PyMuPDF 渲染 + qwen-vl, v0.3.2; v0.9 复用于知识库）
    │   │   ├── llm_parser.py      LLM 简历信息提取（ResumeInfo）
    │   │   └── models.py          ResumeInfo Pydantic
    │   ├── data/                  9 岗位题库 .md（133 题，`### Q/A/S` + `<!-- id|category|difficulty -->`，v0.5 场景题扩展）
    │   ├── reports/               生成的报告（.md + .json 雷达对）
    │   ├── kb_files/              上传原始文件静态目录（v0.9, gitignored, /kb_files 免认证直访）
    │   ├── kb_chroma/             知识库向量集合 kb_notes（v0.8, 与题库隔离）
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
            ├── views/knowledge/   KnowledgeView(列表+文件/网址导入) / GraphView(图谱, v0.9 美化+hover聚焦) / NoteEditorView(编辑+反链+语义检索+原始文件, v0.9) / KbChatView(AI对话双栏+会话持久化, v0.10) / InterviewRecordsView(记录列表+删除, v0.10)
            └── components/        TopNav / AppLayout(侧边栏, v0.7) / RadarChart / DSIcon
```

### 2.1 测试文件

| 文件 | 用途 | 用例数 |
|---|---|---|
| `conftest.py` | 测试环境隔离（临时用户库 + 固定测试密钥, 不碰开发库） | — |
| `test_auth.py` | 认证：用户表/bcrypt/JWT/接口 401/注册/报告隔离（v0.6） | 14 |
| `test_protocol.py` | WS 阶段协议校验 | 4 |
| `test_score_parser.py` | 评分解析 + ④总分校准 | 5 |
| `test_api_entrypoints.py` | REST API 入口（v0.6 起带 Bearer） | 5 |
| `test_data_integrity.py` | 题库数据完整性 | 5 |
| `test_interview_graph.py` | LangGraph 全流程（FakeLLM）+ 反幻觉 prev_context | 6 |
| `test_memory.py` | InterviewMemory 接线（①） | 5 |
| `real_smoke.py` | 真实 LLM 冒烟（2题流程, 需登录取 token） | 手动 |
| `real_smoke_antihall.py` | 真实 LLM 反幻觉（全垃圾回答, 需登录取 token） | 手动 |
| `real_smoke_history.py` | 真实 LLM 连续心智（正常回答, 需登录取 token） | 手动 |
| `real_smoke_auth.py` | 鉴权端到端冒烟（登录/401/注册/隔离/WS 握手, 无需 LLM Key） | 手动 |
| `test_knowledge.py` | 知识库：CRUD/[[链接]]解析/图谱/反链/隔离/报告入库（v0.7） | 13 |
| `real_smoke_kb.py` | 知识库端到端冒烟（无需 LLM Key） | 手动 |
| `real_smoke_kb2.py` | 知识库增强冒烟（上传/网址/BGE 检索/rebuild/覆盖检测, v0.8） | 手动 |

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

### 3.1 认证（v0.6, backend/.env 可配, 均可省略）
| 参数 | 默认值 | 说明 |
|---|---|---|
| `JWT_SECRET_KEY` | 空 → 自动生成落盘 `backend/.jwt_secret` | JWT HS256 签名密钥（≥32 字节为宜） |
| `TOKEN_EXPIRE_HOURS` | 24 | 令牌有效期（小时） |
| `AUTH_DB_PATH` | `backend/users.db` | 用户库路径（测试用 conftest 覆盖到临时目录） |

- 依赖：`pyjwt>=2.8.0`、`bcrypt>=4.0.0`（requirements.txt 已加, `.venv` 与 anaconda interview 环境均已安装）
- 公开接口：`POST /api/login`、`POST /api/register`；其余 REST 全部 `Depends(get_current_user)`；WS 握手 `?token=`
- 前端协议变化：REST 带 `Authorization: Bearer`；WS URL `ws://.../ws/chat?token=<jwt>`

### 3.2 模型与 API（backend/.env）
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

### 3.3 检索（config.py）
- `TOP_K=5`、`CHUNK_SIZE=500`、`OVERLAP=50`
- RRF：`BM25_WEIGHT=0.4`、`VECTOR_WEIGHT=0.6`、`RRF_K=60`
- Chroma：`collection_name=interview_questions`、cosine 空间、答案/得分点存 metadata（检索不泄漏答案）
- jieba 分词做 BM25 中文检索

### 3.4 记忆（config.py，① 接线后生效）
| 参数 | 值 | 说明 |
|---|---|---|
| `MEMORY_WINDOW_SIZE` | 10 | 保留最近 N 条消息（压缩时） |
| `MEMORY_COMPRESS_THRESHOLD` | 6000 | 对话超过此字符数触发摘要压缩 |

- 压缩策略：超阈值 → 保留最近 window_size 条 → 旧消息过 `compress_prompt` 压成话题级摘要 → 以 `[之前对话摘要]` SystemMessage 前置
- 压缩失败 fallback：硬截断保留最近消息（不崩）
- memory 按 thread_id 闭包字典管理，**进程内**（不随 checkpointer 持久化，见 §4.1）

### 3.5 面试业务参数
- 8 岗位（`config.ROLES`）：python/java/frontend_dev/product_manager/general_hr/algorithm/devops/data_analyst；题库 86 题
- 难度 1–3（Junior/Intermediate/Senior），默认 2；题量 1–20，默认 5
- **低分追问阈值**：初始分 `3 ≤ score < 7` → 一次针对性追问，合并回答后重评；`<3`（完全不会/跑题）与 `≥7`（已答好）直接下一题
- **评分总分校准**（④）：顶层 score 与四维均值偏差>2 或方向性矛盾时，以四维均值为准
- 结束条件：答满题量、或回答内容为 `quit/exit/q`、或前端发 `end`
- 单次回答 ≤ 5000 字；`resume_context` ≤ 6000 字；`resume_skills` ≤ 30 个
- 评分四维：accuracy/completeness/depth/clarity（各 1–10，总分=均值，经校准）
- 报告命名：`interview_report_{时间戳}_{thread_tag}_{role_key}.md/.json`

### 3.6 环境与版本（实测）
| 项 | 值 |
|---|---|
| 后端 | FastAPI + uvicorn `127.0.0.1:8000`（`python server.py` 或 uvicorn） |
| 前端 | Vite `127.0.0.1:3000`（proxy `/api`、`/ws` → 8000） |
| Python | 项目 `.venv` 为 3.12.13（有 pytest+pytest-asyncio）；用户日常用 `D:\anaconda\envs\interview` 环境（无 pytest，跑服务用） |
| 关键包 | langgraph 1.2.10 · langchain 1.3.14 · langchain-chroma 1.1.0 · langchain-openai 1.4.2 · langchain-community 0.4.2 · fastapi 0.141.1 · chromadb 1.5.9 · pydantic 2.13.4 · sentence-transformers 5.7.0 · pdfplumber 0.11.10 · pyjwt 2.10.x · bcrypt 4.x（v0.6 新增, 两环境均已装）· pymupdf 1.28.2（仅 .venv, v0.9 扫描件必需） |
| 前端依赖 | vue 3.4 · vue-router 4 · echarts 6.1 + vue-echarts 8.1 · vite 5.4 |
| 登录 | v0.6 生产级：SQLite 用户表 + bcrypt + JWT（默认 24h）；预置演示账号 `admin / 123123`；支持注册 |

### 3.7 测试现状
- `pytest` 全量：**45 通过 / 0 失败**（v0.6: +认证 14 用例；用 `.venv` 跑；`D:\anaconda\envs\interview` 无 pytest）
- ⚠️ Windows 环境：`test_interview_graph.py` 的 `tmp_path` 清理会报 `.pytest_tmp PermissionError [WinError 5]`（文件被占用），测试本身通过；建议 `pytest --basetemp=<外部临时目录>` 规避
- 真实冒烟：LLM 类 3 个脚本（需后端已启动 + .env 配好 Key，现均自动登录取 token）；鉴权冒烟 `real_smoke_auth.py`（无需 LLM Key）

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
- ~~打字机逐字效果未做~~ → **v0.3.1 已实现**（`useWebSocket.js` 24ms 逐字释放, 见 §5.5）
- **报告可靠性依赖外部 LLM**：DeepSeek 偶发中断时 AI 评价段降级为模板文字（已兜底，但报告不完整）
- ~~扫描图片型 PDF 不支持 OCR~~ → **v0.9 已解决**：千问视觉转写（`kb_extract.py` 复用 `resume/vision_parser.py` 渲染管线，20 页上限）；前提 `.env` 配 `ALIYUN_API_KEY` 或 `DASHSCOPE_API_KEY` 且后端用 `.venv` 启动（含 pymupdf，见 §11.4）
- ~~登录非生产级~~ → **v0.6 已解决**（SQLite 用户表 + bcrypt + JWT + 全接口校验 + 数据隔离, 见 §1.5/§8）；遗留小项：① 无"改密码/找回密码"与登出黑名单（JWT 无状态, 过期前无法吊销）；② WS 用 query 传 token, 代理日志可能记录（本地演示可接受, 生产建议子协议头或短期 ticket）；③ 无管理员角色/权限分级, 所有注册用户平权
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
5. ~~前端体验：实现打字机逐字效果~~ → **v0.3.1 已完成**（见 §5.5）
6. **补齐 EMBEDDING_ONLINE** 实现，或删除该配置避免误导

### 5.3 中期（生产化）
7. ~~生产鉴权~~ → **v0.6 已完成**（JWT + bcrypt + SQLite 用户表 + 接口校验 + 报告/会话隔离）；可续做：改密码接口、登出吊销（短期 token + Redis 黑名单或转 opaque session）、管理员角色分级
8. ~~PDF OCR 兜底（如 PaddleOCR/RapidOCR）支持扫描件~~ → **v0.9 已解决**（千问视觉转写, 见 §11.4）
9. `langchain-community` → 独立集成包迁移；CI（GitHub Actions：pytest + npm build）

### 5.4 继续开发速查
```powershell
# 后端（窗口1）—— v0.9 起**必须用 .venv**（含 pymupdf, 扫描件视觉转写必需; anaconda interview 环境缺 pymupdf）
cd E:\hiagent\DEMO3\TOtal\backend
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
#   （旧命令 D:\anaconda\envs\interview\python.exe 仍可跑非扫描件功能, 但扫描件会报"视觉模型未配置"）

# 前端（窗口2）
cd E:\hiagent\DEMO3\TOtal\frontend
npm run dev -- --host 127.0.0.1    # http://127.0.0.1:3000，账号 admin/123123

# 题库变更后重建向量库
cd E:\hiagent\DEMO3\TOtal\backend && python main.py rebuild

# 测试（用 .venv，Windows 下建议外部临时目录）
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp="$TEMP\pytest_demo3"

# 真实 LLM 冒烟（需后端已启动 + .env 配好 Key；脚本自动登录取 token）
.\.venv\Scripts\python.exe tests/real_smoke_antihall.py   # 反幻觉(全垃圾回答)
.\.venv\Scripts\python.exe tests/real_smoke_history.py    # 连续心智(正常回答)
.\.venv\Scripts\python.exe tests/real_smoke.py            # 2题完整流程

# 鉴权冒烟（无需 LLM Key；端口非 8000 时设 $env:SMOKE_PORT='xxxx'）
.\.venv\Scripts\python.exe tests/real_smoke_auth.py
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

## 8. v0.6 变更记录 (2026-08-25, 生产级鉴权)

**目标**：替换演示级登录（固定账号 + MD5 token + 后端不校验）为完整用户体系。四项决策均由用户拍板：引入 pyjwt+bcrypt（而非零依赖标准库方案）、SQLite 用户表（而非内存预置）、开放注册、报告/会话按用户隔离。

### 8.1 新增文件

| 文件 | 说明 |
|---|---|
| `backend/auth.py` | 认证模块：SQLite 用户表（建表/预置 admin）+ bcrypt 哈希 + JWT 签发/校验 + `get_current_user`（REST 依赖）+ `ws_authenticate`（WS 握手）；密钥 `.env JWT_SECRET_KEY` → 自动生成 `.jwt_secret` 落盘复用 |
| `tests/conftest.py` | 测试环境隔离：临时用户库 + 固定 ≥32 字节测试密钥（conftest 先于测试模块加载, 在 import config 前生效） |
| `tests/test_auth.py` | 14 用例：建表预置/密码校验/盐随机/凭据格式/JWT 往返/过期/伪造签名/接口 401/注册冲突/报告隔离/旧报告归 admin |
| `tests/real_smoke_auth.py` | 鉴权端到端冒烟（真实服务, 无需 LLM Key） |

### 8.2 后端改动

| 文件 | 改动 |
|---|---|
| `server.py` | ① `POST /api/login` 重写：SQLite + bcrypt 校验, 签发 JWT（删除 MD5）；② 新增 `POST /api/register`；③ 除 login/register 外**所有** REST 接口加 `Depends(get_current_user)`（roles/config/parse-text/upload/reports×3/interviews）；④ `/ws/chat` 握手 `ws_authenticate`（`?token=`, 失败在 accept 前 close → 握手 403）；⑤ 报告三接口按 `_report_owner()` 过滤（json 的 `username`, 缺省归 admin, 他人访问 404 不泄露存在性）；⑥ `/api/interviews` 与 WS 会话登记带 `username`, 恢复他人 thread_id 被拒；⑦ `initial_state` 注入 `username` |
| `agent/state.py` | `InterviewState` 新增 `username` 字段（配置段） |
| `agent/graph.py` | `summary_node` 雷达 JSON 写入 `username`（报告归属的唯一落点） |
| `config.py` | 新增 `AUTH_DB_PATH` / `JWT_SECRET_KEY` / `TOKEN_EXPIRE_HOURS`（均可 .env 覆盖） |
| `requirements.txt` | 新增 `pyjwt>=2.8.0`、`bcrypt>=4.0.0`（`.venv` 与 anaconda interview 两环境均已安装） |
| `.gitignore` | 新增 `backend/users.db`、`backend/.jwt_secret` |
| 3 个 real_smoke*.py | WS 连接 URL 自动登录取 token（`get_token()` via httpx） |

### 8.3 前端改动

| 文件 | 改动 |
|---|---|
| `auth.js` | `isAuthenticated()` 改为本地解析 JWT payload（base64url）校验 `exp` 与 username 一致, 不再硬编码 admin + 32位hex；新增 `getToken()` |
| `api/index.js` | `request()` 自动携带 `Authorization: Bearer`（login/register `skipAuth`）；**401 自动 `clearAuth()` + 跳 `/login?redirect=`**；新增 `register()` |
| `composables/useWebSocket.js` | `connect()` 拼 `?token=`（encodeURIComponent） |
| `views/LoginView.vue` | 登录/注册双模式切换（确认密码前端校验）；注册成功即签发 token 免二次登录 |

### 8.4 设计要点与兼容性

- **演示兼容**：首次启动空库自动预置 `admin/123123`（bcrypt 哈希入库）, 答辩流程零变化
- **旧报告兼容**：v0.6 前的报告 JSON 无 `username` 字段 → 归 admin（`_report_owner` 缺省 admin）；非 admin 用户访问旧报告得 404
- **JWT 无状态**：用户删除后 token 仍在有效期内会被 `get_current_user` 的"用户不存在"分支拦截；无登出吊销（见 §4.2 遗留项）
- **WS token 走 query**：浏览器 WS API 不能自定义 header, query 是标准做法；本地演示可接受, 生产建议子协议或短期 ticket（见 §4.2）
- **测试隔离**：conftest 在 import config 前设 `AUTH_DB_PATH`/`JWT_SECRET_KEY` 环境变量, pytest 全程不触碰开发库 `backend/users.db` 与 `.jwt_secret`

### 8.5 验证结果

| 验证项 | 结果 |
|---|---|
| pytest 全量 | ✅ 45/45 通过（v0.5 后为 31, +14 认证用例; 用 .venv + 外部 basetemp） |
| 鉴权端到端冒烟（真实 uvicorn, anaconda 环境） | ✅ 7/7：登录签发 JWT / 无 token 401 / 伪造 token 401 / 有效 token 200(9 岗位) / 注册成功 / 新用户 `/api/interviews` 空（隔离生效）/ WS 无 token 握手 403 + 有效 token 放行 |
| npm run build | ✅ 通过 |
| 依赖安装 | ✅ pyjwt 2.10.x + bcrypt 4.x 装入 `.venv` 与 `D:\anaconda\envs\interview` |
| 开发库清理 | ✅ 冒烟注册的 smoke_user 已从 `backend/users.db` 删除, 仅剩预置 admin |

---

## 9. v0.7 变更记录 (2026-08-25, 个人知识库)

**目标**：登录后新增侧边栏 + Obsidian 式个人知识库（双链笔记 + 图谱可视化），并与面试报告联动。四项技术选型均由用户拍板：Cytoscape.js（而非复用 ECharts）、集成成熟编辑器（vditor）、报告薄弱点一键入库、完整 MVP。

### 9.1 数据模型（Obsidian 哲学：链接是解析出来的，不是存的）

```sql
-- backend/knowledge.db (gitignored)
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,          -- 按用户隔离 (v0.6 JWT)
    title TEXT NOT NULL,             -- 同用户唯一 (UNIQUE约束) — [[链接]]按标题解析的前提
    content TEXT DEFAULT '',         -- Markdown; [[标题]] = 出链
    tags TEXT DEFAULT '',            -- 逗号分隔
    source TEXT DEFAULT 'manual',    -- manual / interview_report
    created_at TEXT, updated_at TEXT,
    UNIQUE(username, title)
);
```

- **边不落库**：`/api/kb/graph` 时用正则 `\[\[([^\[\]\n]{1,120})\]\]` 解析全部笔记动态构建 → 单一数据源，永不不一致
- **虚节点**：链接指向不存在的标题 → 图谱灰色虚线圆，前端点击即创建（Obsidian 核心体验）
- **自链不建边**；度 = 出链数 + 入链数（决定节点大小）

### 9.2 新增文件

| 文件 | 说明 |
|---|---|
| `backend/knowledge.py` | notes CRUD + `parse_links()` + `build_graph()`（nodes/edges/virtual/degree）+ `get_backlinks()`；`KB_DB_PATH` 环境变量可覆盖（测试隔离用） |
| `backend/tests/test_knowledge.py` | 13 用例：解析/CRUD/同名冲突/用户隔离/搜索标签过滤/图谱节点边虚节点/度计算/反链/自环/报告入库/同名跳过 |
| `backend/tests/real_smoke_kb.py` | 知识库端到端冒烟（真实服务, 无需 LLM Key） |
| `frontend/src/components/AppLayout.vue` | 全局侧边栏：分组导航（面试流程/个人知识库）+ 用户区 + 退出；可收起（图标模式） |
| `frontend/src/views/knowledge/KnowledgeView.vue` | 笔记列表：卡片网格 + 搜索防抖 + 标签筛选 + 出链数/来源徽标 |
| `frontend/src/views/knowledge/GraphView.vue` | Cytoscape 图谱：cose 力导向；节点大小∝√degree；hover 邻居高亮（其余淡化）；点击已有笔记→编辑、虚节点→创建 |
| `frontend/src/views/knowledge/NoteEditorView.vue` | vditor 编辑器（ir 即时渲染模式, 中文）+ 标题/标签输入 + 侧栏（链接到/反向链接, 实时解析, 未创建目标标注"未创建"可点建） |

### 9.3 后端改动

| 文件 | 改动 |
|---|---|
| `server.py` | 挂 7 个路由：`GET/POST /api/kb/notes`、`GET/PUT/DELETE /api/kb/notes/{id}`、`GET /api/kb/graph`、`POST /api/kb/notes/from-report`（全部 `Depends(get_current_user)`；from-report 批量建笔记, 同名跳过不覆盖, 单次上限 50 条） |
| `config.py` | 新增 `KB_DB_PATH`（默认 `backend/knowledge.db`） |
| `.gitignore` | 新增 `backend/knowledge.db` |
| `tests/conftest.py` | 新增 `KB_DB_PATH` 指向临时目录（与 users.db 同一套隔离机制） |

### 9.4 前端改动

| 文件 | 改动 |
|---|---|
| `App.vue` | 条件布局：Login 直接渲染, 其余页面套 AppLayout（内含 router-view） |
| `router/index.js` | +4 路由：`/knowledge`、`/knowledge/graph`、`/knowledge/note/:id`、`/knowledge/new` |
| `components/TopNav.vue` | 移除中间导航链接（职责移交侧边栏）, 保留返回按钮/用户名/退出 |
| `api/index.js` | +8 个知识库 API 封装（自动带 Bearer, 401 跳登录） |
| `views/SummaryView.vue` | 学习建议卡片头部加「📥 存入知识库」按钮：调 from-report 批量入库, 显示已入库条数与同名跳过提示, 按钮置灰防重复 |
| `package.json` | 新增 `cytoscape`、`vditor`（均为路由懒加载, 不增首屏体积：GraphView 447KB / NoteEditorView 308KB gzip 后约 145KB/77KB） |

### 9.5 设计要点

- **为何链接不落库**：Obsidian 同款哲学——笔记内容是唯一真相源；图谱/反链/侧栏链接列表全部由 `parse_links()` 现算。个人库量级（几百笔记）下每次全量解析开销可忽略（正则 + 内存遍历），换来永不一致的边表问题消失
- **标题唯一约束**是按标题解析链接的前提，UNIQUE(username, title) 数据库层强制
- **Cytoscape hover 聚焦**：`closedNeighborhood()` 取邻居子图, 其余 `opacity: 0.15`——大图下快速看清局部结构
- **测试隔离**：`KB_DB_PATH` 与 `AUTH_DB_PATH` 同机制在 conftest 指向临时目录; test_knowledge 每用例独立注册新用户（autouse fixture）避免用例间串扰

### 9.6 验证结果

| 验证项 | 结果 |
|---|---|
| pytest 全量 | ✅ 58/58 通过（v0.6 后 45, +13 知识库用例） |
| 知识库端到端冒烟（真实 uvicorn, anaconda 环境） | ✅ 7/7：登录 / 无 token 401 / 建双链笔记 / 图谱（3 节点含 1 虚节点, 3 边）/ 反链 / 报告入库 / 清理 |
| npm run build | ✅ 通过（知识库页面全部懒加载） |
| 开发库清理 | ✅ 冒烟数据已清（users.db 仅剩 admin, knowledge.db 空） |

### 9.7 后续可扩展方向（未做）

- 笔记内 [[链接]] 点击跳转（编辑器内 inline 渲染, 需 vditor 自定义渲染钩子）；当前从编辑页侧栏点击跳转
- 图谱按标签着色/过滤、孤立节点过滤、fcose 更优布局（需加 cytoscape-fcose 扩展）
- 知识库 → 面试方向：从笔记内容生成面试题/复习卡片（调 LLM, 用户讨论中提到的"深度联动"）
- 笔记全文搜索升级（SQLite FTS5）；导出 Markdown 包

---

## 10. v0.8 变更记录 (2026-08-25, 知识库增强)

**三原则（用户拍板）**：① 题库与知识库完全隔离（题库向量集合不动）；② 文件解析全走模型（PPT/Word/PDF 过 LLM 结构化，扫描件走千问视觉）；③ 效果优先不计开销（STRONG 模型、视觉可用就用）。

### 10.1 数据模型变更

notes 表新增列（`ALTER TABLE` 启动自动迁移，旧数据兼容）：

```sql
+ note_type   TEXT DEFAULT 'note'   -- 'note'手写 | 'file'文件 | 'url'网址
+ category    TEXT DEFAULT ''       -- 自定义分类 (单选)
+ source_url  TEXT DEFAULT ''       -- url 类型存原网址
+ file_name   TEXT DEFAULT ''       -- file 类型存原始文件名
```

新表 `sem_links(username, title_a, title_b, score, created_at)`：语义关联预计算表（rebuild 时两两余弦相似度 ≥0.55 写入，图谱虚线边数据源）。存表原因：O(n²) 现算慢，预计算后图谱接口直接读。

新向量集合：Chroma `kb_notes`（`backend/kb_chroma/`，与题库 `interview_questions` **完全隔离**）；嵌入文本=标题+分类+内容前800字；metadata 带 username 检索时 where 过滤。

### 10.2 新增后端文件

| 文件 | 说明 |
|---|---|
| `kb_extract.py` | 文件原文提取：md/txt 直读（UTF-8/GBK 回退）；pptx 逐页（python-pptx，标题+正文+表格）；docx（python-docx，保留标题层级）；pdf 文本层 <50 字判定扫描件 → 千问视觉转写（复用 vision_parser 渲染管线，20页上限）。产出 `{raw_text, pages, extract_mode}`，临时文件用完即删 |
| `kb_llm.py` | 三个 LLM 能力（全 STRONG 模型）：`structure_file_note` 文件→{title,markdown,category,tags}（**prompt 中 JSON 花括号必须 `{{}}` 转义**，否则被 ChatPromptTemplate 当模板变量——已踩坑修复）；`suggest_category` 分类建议（优先归入已有分类）；`tidy_markdown` AI 整理。全部失败降级不阻塞 |
| `kb_vectors.py` | 向量库封装：`upsert_note/delete_note`（写入同步，失败只 log）；`search`（top-k + score）；`is_sparse`（top1<0.35）；`rebuild`（全量向量重建 + 语义关联两两计算写 sem_links）。阈值：SEM_LINK_THRESHOLD=0.55 / SPARSE_THRESHOLD=0.35 |

### 10.3 后端改动

| 文件 | 改动 |
|---|---|
| `server.py` | 新端点：`POST /api/kb/notes/upload`（多文件，逐文件独立成败返回明细）、`POST /api/kb/notes/url`（描述必填双层校验）、`GET /api/kb/categories`、`GET /api/kb/search`、`POST /api/kb/tidy`、`POST /api/kb/auto-category`、`POST /api/kb/rebuild`；`/api/kb/graph` 支持 `semantic`/`category` 参数；notes CRUD 全链路带新字段+向量同步；**from-report 增加覆盖检测（排除本轮新建笔记自身，防自我覆盖误判——真实冒烟抓出的 bug）** |
| `knowledge.py` | 表迁移；CRUD 新字段；`list_categories` 聚合；`build_graph` 升级（节点带 note_type/category/source_url；边分 kind=wiki/semantic；分类过滤）；网址笔记描述必填校验 |
| `config.py` | `KB_CHROMA_PATH`（默认 backend/kb_chroma） |
| `requirements.txt` | + `python-pptx`、`python-docx`（两环境已装） |
| `tests/conftest.py` | + `KB_CHROMA_PATH` 临时目录隔离 |

### 10.4 前端改动

| 文件 | 改动 |
|---|---|
| `api/index.js` | +9 个封装（upload 5min 超时、tidy 3min） |
| `KnowledgeView.vue` | 「📁 导入文件」（multiple，进度+逐文件结果明细）、「🔗 添加网址」弹窗（描述必填）、分类 chips 筛选（紫色系）、卡片类型徽标（✎蓝/📄绿/🔗橙）+ 网址 ↗ 直开 + 分类标签 |
| `NoteEditorView.vue` | 分类输入（datalist）+ 🤖 AI 分类 + ✨ AI 整理；**🔍 语义检索面板**（默认检索当前标题、结果带相关度%/摘要/类型、网址「打开链接」、「插入[[链接]]」一键固化双链、sparse 黄条提示导入）；网址笔记「↗ 打开来源」按钮 |
| `GraphView.vue` | **节点类型着色**+图例；分类多选过滤；「显示语义边」开关；语义边淡紫虚线+hover 高亮；🔄 重建索引；统计栏分 双链/语义 计数 |
| `SummaryView.vue` | 入库后「🎯 知识库覆盖情况」面板：✓ 已覆盖（匹配笔记可点击跳转）/ ⚠ 无覆盖（建议导入链接） |

### 10.5 验证结果

| 验证项 | 结果 |
|---|---|
| pytest 全量 | ✅ 72/72（v0.7 后 58，+14 v0.8 用例：提取/上传降级/网址校验/分类聚合/图谱类型与语义边/检索 sparse/FakeEmbeddings 16维统一 mock） |
| 真实冒烟 `real_smoke_kb2.py` | ✅ 9/9：登录/上传 pptx+md/网址/BGE 真实检索(0.631)/sparse 正确标记/rebuild(3笔记+1语义边)/图谱类型/覆盖检测(Transformer 匹配3条、红烧肉 sparse)/清理 |
| npm build | ✅ 通过 |
| 开发库清理 | ✅ 冒烟数据已清 |

### 10.6 已知问题与说明

- **DeepSeek 账户余额不足（402）**：冒烟期间 LLM 结构化全程走降级路径（原文直入、上传不中断）——降级机制经真实验证可靠；**充值后 LLM 功能自动恢复**，无需改代码。千问视觉依赖 DASHSCOPE_API_KEY（用户已配）不受影响
- LLM 不可用时：文件照常入库（无分类）、AI 整理/分类返回 502 提示重试、检索/图谱/语义边（本地 BGE）完全不受影响
- 语义边/检索依赖向量同步；大量修改后建议点图谱页「🔄 重建索引」兜底
- 上传逐文件独立成败：同名自动跳过（status=skipped）、格式不支持/损坏 failed，其余照常

## 11. v0.9 变更记录 (2026-08-26, 原始文件查看 + 编辑器修复)

### 11.1 原始文件查看

- **存储**：上传文件改存 `backend/kb_files/`（静态目录），`notes.file_path` 存 `/kb_files/<文件名>` 相对链接
- **后端**：`server.py` 挂载 `app.mount("/kb_files", StaticFiles(...))`，无需认证直接访问；启动时 `knowledge.migrate_file_paths()` 自动把旧版绝对路径链接迁移（旧文件复制到 kb_files 并改写 DB）
- **前端**：`vite.config.js` 增加 `/kb_files` 代理；`NoteEditorView.vue` 右侧栏「原始文件」卡片，点击新标签页打开（PDF 浏览器直接预览，PPT/DOCX 触发下载——浏览器限制）
- **移除**：旧版 `GET /api/kb/notes/{id}/file` 下载接口（需认证、浏览器直开无 token 导致失败）

### 11.2 编辑器修复

- 工具栏悬停被裁切：`.editor-main` overflow 改 `visible`
- 宽表格撑破整页横向滚动：`.editor-body` 列宽改 `minmax(0, 1fr) 280px`

### 11.3 验证

- 旧笔记 2 条迁移成功；`/kb_files/<pdf>` 经 3000 代理与 8000 直连均 200 `application/pdf`

### 11.4 扫描件 PDF 视觉兜底修复 + 上传限制放宽

- **Key 兼容**：`config.py` 的 `DASHSCOPE_API_KEY` 增加 `ALIYUN_API_KEY` 回退（百炼/DashScope 同为阿里云平台, key 通用; .env 原配的 ALIYUN_API_KEY 一直未被代码读取, 导致扫描件 PDF 报"视觉模型未配置"）
- **运行环境**：后端须用 `backend\.venv\Scripts\python.exe` 启动（含 pymupdf 1.28.2）; 误用 anaconda base 会因缺 pymupdf 使 `vision_available()=False`
- **上传限制**：单文件 15MB → 50MB（`server.py`）
- 扫描件转写上限 20 页（`kb_extract._VISION_MAX_PAGES`），超长文档仅转写前 20 页

### 11.5 图谱美化 + cytoscape 选择器陷阱修复

- **根因**：cytoscape 选择器**不支持布尔字面量**（`node[virtual = true]` 被判 invalid），且该无效选择器导致整个样式表失效 → 所有节点回退默认灰色、虚线描边。已用 headless 实测确认
- **修复**：`GraphView.vue` 节点/边 data 中 `virtual` 改为字符串 `'yes'/'no'`，选择器改 `node[virtual = "yes"]`；hover 清除改用 `removeStyle()`（原 `style({'border-width': ''})` 会残留内联样式）
- **美化**：节点高饱和配色（笔记蓝 #3b82f6 / 文件绿 #10b981 / 网址橙 #f59e0b / 虚节点灰）+ 白色描边；标签白底圆角背景防重叠；cose 布局参数调优（nodeRepulsion 12000 / idealEdgeLength 160 / 2000 迭代）节点自然散开

## 12. v0.10 变更记录 (2026-08-27, AI 对话 + RAG 质量 + 面试体验)

### 12.1 RAG AI 对话（参考 FastGPT/Dify 交互范式）

**数据模型**（`knowledge.py`，ALTER TABLE 启动自动迁移，旧库兼容）：

```sql
CREATE TABLE kb_chat_sessions (   -- 会话
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,        -- 按用户隔离 (JWT)
    title TEXT DEFAULT '新对话',   -- 首问前20字自动命名
    created_at TEXT, updated_at TEXT
);
CREATE TABLE kb_chat_messages (    -- 消息 (role: user/assistant)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,   -- FK → kb_chat_sessions
    role TEXT NOT NULL, content TEXT,
    sources TEXT DEFAULT '[]',    -- JSON: [{title, score, note_id}] 参考来源
    sparse INTEGER DEFAULT 0,      -- 稀疏标记 (top1 < 0.35)
    created_at TEXT
);
```

**后端**（`server.py` + `knowledge.py` + `kb_llm.py`）：

| 端点 | 说明 |
|---|---|
| `POST /api/kb/qa` | 问答主链路：无 session_id 自动建会话（首问截 20 字做标题）→ 存用户问题 → 向量检索 → LLM 回答 → 存 AI 回答（含 sources/sparse）→ 返回 `{session_id, answer, sources, sparse}` |
| `GET /api/kb/chat/sessions` | 会话列表（updated_at 降序） |
| `POST /api/kb/chat/sessions` | 手动新建空会话 |
| `GET /api/kb/chat/sessions/{id}` | 会话详情 + 全部消息（恢复历史用） |
| `PATCH /api/kb/chat/sessions/{id}` | 重命名 |
| `DELETE /api/kb/chat/sessions/{id}` | 删除会话（级联删消息） |

全部走 `Depends(get_current_user)`，会话按 username 隔离（他人会话 404）。

**前端**：新建 `KbChatView.vue`（路由 `/knowledge/chat`）——左栏会话列表（新建/切换/重命名/删除）+ 右栏聊天区（Markdown 渲染、参考来源卡片点击跳笔记、sparse 黄条提示、思考动画）；`api/index.js` 新增对应封装。

**侧边栏双亮修复**：`AppLayout.vue`「我的笔记」active 条件排除 `/knowledge/chat` 路由。

### 12.2 RAG 回答质量修复（本轮关键 bug）

- **问题**：让 AI 解读某文档（如"RAG 十种优化技巧"）只输出开篇部分。
- **根因**（两处叠加）：① `kb_vectors.search()` 返回的 `excerpt` 只截 120 字（向量库本身只存前 800 字摘要），LLM 只能看到文档开篇；② `kb_llm.py` 提示词要求"回答简洁清晰"，进一步压缩输出。
- **修复**：
  - `kb_vectors.search()`：检索命中后按 `note_id` 回查 SQLite 拉取**笔记全文**（每条截 4000 字，5 条最多 2 万字）作 `excerpt`；拉取失败回退 120 字摘要
  - `kb_llm._KBA_QA_SYSTEM`：改为"解读/分析文档时必须覆盖全部核心要点并逐条展开（是什么/为什么/怎么用）"+ Markdown 层级结构化输出；上下文块标签从"内容片段"改"笔记内容"
- **遗留**：若导入时走了 LLM 结构化（`structure_file_note` 输入截断 12000 字），长文档入库内容本身可能不全——需在笔记编辑器确认全文，不完整则重新导入。

### 12.3 面试记录删除

- `server.py`：`DELETE /api/interview-records/{filename}`——文件名正则校验（防路径穿越）+ 记录头 `用户: {username}` 判归属（非本人 404）
- `InterviewRecordsView.vue` + `InterviewView.vue`：悬停显示 🗑 按钮 + 确认弹窗；删除后自动刷新列表；若正被查看的记录被删则关闭抽屉

### 12.4 其他

- **开场白优化**（`prompts.py`）：OPENING_SYSTEM/QUESTION_SYSTEM 强制开场白与首题分离为两条独立消息；禁止开场白出现题号等内部元数据与技术术语
- **图谱 hover 聚焦增强**（`GraphView.vue`）：悬停节点→当前+关联节点紫色 4px 描边、关联边全亮、其余元素 opacity ≤0.1；坑：cytoscape `.diff()` 返回对象不能链式 `.style()`，改用 `.difference()`；调试句柄 `window.__cy`
- **演示 PPT**：根目录 `generate-ppt.mjs`（PptxGenJS，12 页：架构/功能/RAG 优化等）；`node generate-ppt.mjs` 生成
- **语音体验（无代码改动）**：建议用 Edge 浏览器（Microsoft Huihui/Yunxi 音色更佳，STT 识别更准）

### 12.5 验证

- 后端重启实测：AI 对话持久化（刷新/跳转回来不丢）、参考来源跳转、会话管理、记录删除、开场白分离、图谱 hover 聚焦全部手工验证通过
- ⚠️ 本轮新增功能未写 pytest 用例（kb chat CRUD / qa 持久化 / 记录删除均可补测试）

---

*本文件为交接文档，不替代 README/START_GUIDE；内容基于 2026-08-27 工作区代码审阅与验证。*
