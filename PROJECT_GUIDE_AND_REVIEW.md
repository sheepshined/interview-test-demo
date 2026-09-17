# AI 模拟面试官 — 项目全景理解、多维度评估与优化建议

> 生成日期：2026-09-17
> 评估方式：基于对后端/前端核心源码的静态阅读，所有结论尽量标注代码位置，未运行压测与渗透测试。
> 阅读顺序建议：第一次读只看「一~五」；要改代码时看「六~八」；要做毕设/答辩拔高时看「九~十一」。

---

## 一、一句话定位

基于 **FastAPI + LangGraph + Vue 3** 的本地 AI 模拟面试系统：用户上传简历（或粘贴文本）→ 混合检索题库出题 → LangGraph 人在回路驱动「出题→作答→评分→低分追问→合并重评」→ 生成 Markdown 报告与四维雷达数据；另带一套与题库完全隔离的个人知识库（双链笔记 + RAG 问答 + 知识图谱）。

当前专注「大模型应用开发工程师」单岗位专场，历史 8 岗位题库保留在 `backend/data_disabled/`。

## 二、技术栈与运行形态

| 层 | 技术选型 |
|---|---|
| 后端框架 | FastAPI + uvicorn，REST + WebSocket 双通道 |
| 流程编排 | LangGraph StateGraph + `interrupt()` 人在回路 + AsyncSqliteSaver 持久化 |
| LLM 编排 | LangChain LCEL（9 条链），ChatOpenAI 兼容 DeepSeek / 智谱 |
| 嵌入/检索 | BAAI/bge-base-zh-v1.5 + Chroma（向量）+ BM25/jieba（关键词）+ RRF 融合 |
| 数据存储 | SQLite × 3（users.db / knowledge.db / checkpoints.db）+ Chroma × 2 + 文件（MD/JSON/PDF） |
| 认证 | bcrypt 密码哈希 + JWT(HS256) + 登出吊销黑名单 |
| 简历解析 | pdfplumber / pymupdf，扫描件走千问 qwen-vl 视觉兜底 |
| 前端 | Vue 3 + Vite + Vue Router，原生 WebSocket，浏览器 SpeechSynthesis 做 TTS |
| 服务形态 | 后端 127.0.0.1:8000（接口 + /docs），前端 127.0.0.1:3000（Vite 代理 /api、/ws、/kb_files） |

## 三、目录与文件职责

```text
TOtal/
├── backend/
│   ├── server.py            # 后端中枢：FastAPI、全部 REST、/ws/chat 图驱动器（约 1200 行）
│   ├── main.py              # 题库 CLI：python main.py build | rebuild | variants
│   ├── config.py            # 全局配置：路径/检索权重/模型分层/角色/人设/难度/评分维度
│   ├── auth.py              # 注册登录、bcrypt、JWT 签发校验、REST/WS 鉴权依赖、吊销名单
│   ├── common.py            # 通用工具：岗位匹配、技能抽取、难度标签、JSON 提取
│   ├── knowledge.py         # 知识库 SQLite：笔记 CRUD、双链 backlink、聊天会话、图谱数据
│   ├── kb_vectors.py        # 知识库纯向量检索（Chroma 集合 kb_notes），SPARSE_THRESHOLD=0.35
│   ├── kb_extract.py        # 上传文件原文提取（PDF/MD 等）
│   ├── kb_llm.py            # 知识库 LLM：结构化整理、自动分类、RAG 回答
│   ├── agent/
│   │   ├── graph.py         # 【核心】14 节点面试 StateGraph，全部业务规则所在地
│   │   ├── state.py         # InterviewState(TypedDict)：图内唯一共享状态
│   │   ├── chains.py        # 9 条 LCEL 链的工厂函数
│   │   ├── prompts.py       # 全部提示词模板
│   │   ├── llm.py           # get_fast_llm() / get_strong_llm() 工厂
│   │   ├── models.py        # Pydantic：ScoreResult、ScoreBreakdown、ProjectQuestion
│   │   ├── memory.py        # InterviewMemory：滑窗 + 超阈值摘要压缩
│   │   ├── protocol.py      # WS 命令 ↔ graph phase 合法性表（纯函数）
│   │   └── variants.py      # 防背题：LLM 生成同考点变体题
│   ├── retrieval/
│   │   ├── retriever.py     # HybridRetriever：BM25 + 向量 + RRF，出题/评分分离
│   │   ├── embeddings.py    # BGE 嵌入单例（带缓存）
│   │   └── kb_builder.py    # 从 data/*.md 构建题库向量库
│   ├── resume/              # parser.py(规则) / llm_parser.py(LLM) / vision_parser.py(千问视觉)
│   ├── data/llm_app.md      # 当前唯一启用的题库
│   ├── data_disabled/       # 8 个历史岗位题库（可恢复）
│   ├── reports/             # 面试报告输出：*.md（全文）+ *.json（雷达/元数据）
│   ├── agent/interview_records_*.md  # 逐题面试记录（与代码同目录，含用户归属头）
│   ├── kb_files/ kb_uploads/         # 知识库原始上传文件（/kb_files 静态挂载）
│   └── tests/               # pytest 单测 + real_smoke*.py 真实 LLM 烟雾脚本
├── frontend/src/
│   ├── api/index.js         # fetch 封装：自动 Bearer、30s/90s 超时、401 跳登录
│   ├── auth.js              # localStorage 令牌 + JWT 本地过期检查
│   ├── composables/useWebSocket.js   # WS 连接、打字机缓冲、TTS 朗读
│   ├── router/index.js      # 路由表 + 登录守卫
│   ├── views/               # 登录/首页/简历/选岗/面试/总结/记录 + knowledge/* 知识库四页
│   └── components/          # AppLayout、TopNav、RadarChart、DSIcon
└── README.md / START_GUIDE.md / OPTIMIZATION_PLAN.md   # 现有文档
```

## 四、核心架构：LangGraph 面试状态机

### 4.1 节点与边（`backend/agent/graph.py` 末尾的图定义）

```text
START
 → configure            归一化配置、建逐题 MD、随机抽面试官人设
 → opening              LLM 流式开场白（注入人设、首题方向）
 → prepare_question     项目模式则 LLM 按简历出题；否则混合检索题库；首题可固定
   ├─ 无题 → closing
 → emit_question        LLM 把题库原题润色为自然提问（可结合简历），流式输出
 → wait_answer          ① interrupt()：等待候选人作答（action=answer/end）
   ├─ end → closing
 → score_initial        自一致性评分 N 次取中位数；按提示次数封顶
   ├─ 初始分 3~6 → prepare_followup → emit_followup → wait_followup（② interrupt）
   │                                                → score_combined（两段回答合并重评）
   └─ 其他 → finalize_question
 → finalize_question    落记录、算自适应难度(streak)、决定 next/end
   ├─ 未满题 → 回到 prepare_question
   └─ 满题/提前结束 → closing
 → closing              LLM 流式收尾语，推 interview_ended
 → wait_report          ③ interrupt()：等待前端点「生成报告」
 → summary              强模型生成 AI 评价（三级降级），写报告 MD + 雷达 JSON
 → END
```

**为什么等待节点必须"干净"**：LangGraph 在 `Command(resume=...)` 时会从含 `interrupt()` 的节点开头重跑，所以 `wait_answer / wait_followup / wait_report` 在 interrupt 之前严禁做随机选题、LLM 调用、文件写入，否则恢复时会重复出题、重复扣额度、重复写文件。这是全项目最关键的工程约束（见 graph.py 文件头注释）。

### 4.2 共享状态 InterviewState（`agent/state.py`）

| 分组 | 关键字段 |
|---|---|
| 配置 | thread_id、role_key、role_info、difficulty(_label)、total_count、interview_mode、username、resume_context/skills |
| 人设 | persona_key、persona_info |
| 进度 | asked_ids、asked_categories、main_question_count、question_index、first_topic_hint |
| 当前轮 | current_question、current_answer_data、rendered_question、main_answer、followup_question/answer、combined_answer、input_action、force_end |
| 评分 | records（逐题）、initial_result/final_result、initial_score/final_score |
| 自适应 | streak、difficulty_changes |
| 其他 | hint_count、decision、md_path、report_id、phase |

注意：`InterviewMemory` 不可序列化，**不进 state**，而是作为 `build_interview_graph()` 闭包内的 `_memories = {thread_id: memory}` 管理——后端重启后图状态能从 SQLite 恢复，但对话记忆会丢失。

### 4.3 已落地的业务规则（项目精华）

| 规则 | 参数/逻辑 | 位置 |
|---|---|---|
| 追问分档 | 初始分 3~6 才追问；<3（不会/跑题）与 ≥7（已答好）直接下一题 | graph.py `initial_score_router` |
| 评分自一致性 | 同一回答独立评分 3 次（SCORING_SAMPLES），总分/四维取中位数，得分点过半投票 | graph.py `_merge_score_samples` |
| 提示封顶 | 用 1 次提示最高 8 分，2 次最高 6 分（四维按比例缩放） | graph.py `_apply_hint_cap` |
| 自适应难度 | 连续 2 次 ≥7 升一级；单次 <4 立即降级；4~6 重置；锁定 1~3 | graph.py `finalize_question_node` |
| 防幻觉契约 | 跨题出题只读候选人**原文+档位**，不读评分链 hit/missed；低分回答额外强禁虚构 | graph.py `_build_prev_context` |
| 合并重评 | 只拼候选人两段回答，**不混入追问文本**，避免把提示算成候选人的话 | graph.py `score_combined_node` |
| 双面试模式 | standard=题库检索；project=按简历 LLM 生成追问链，失败回退题库 | graph.py `prepare_question_node` |
| 人设系统 | strict_cto / warm_hr / deep_tech，随机抽取注入全部对话 prompt | config.py `INTERVIEWER_PERSONAS` |
| 演示首题固定 | llm_app 首题固定 `llm_rag_012`，之后恢复随机（DEMO_* 常量可关） | graph.py L52-53 |
| 报告三级降级 | 强模型 → 快速模型重试 → 纯模板；JSON 中 ai_summary_mode 标识 | graph.py `summary_node` |

### 4.4 WebSocket 协议（`/ws/chat`，握手需 ?token=<jwt>）

前端 → 后端：`config` / `answer` / `end` / `report` / `hint`
后端 → 前端：`config_ok` / `stream_start` / `stream_chunk` / `stream_end` / `decision` / `interview_ended` / `report_ready` / `hint` / `status` / `error`

阶段合法性（`agent/protocol.py`）：

| 命令 | 允许的 phase |
|---|---|
| answer / end / hint | await_answer、await_followup |
| report | await_report |

服务端 WS 处理器只做三件事：鉴权 → 消息转成图输入或 `Command(resume=...)` → 把图的 custom event 原样转发。进程内 `_sessions`（会话登记）与 `_hints`（每题提示次数）是两个额外的全局字典。

### 4.5 双路检索与双库隔离

| | 题库（面试出题） | 知识库（个人笔记 RAG） |
|---|---|---|
| Chroma 集合 | interview_questions | kb_notes |
| SQLite | 无（题目在 MD 文件） | knowledge.db（notes/双链/聊天会话） |
| 检索方式 | BM25(0.4) + 向量(0.6) RRF 融合，K=60，TOP_K=5 | 纯向量语义检索 |
| 嵌入文本 | 题目+场景+分类+题型拼接 | 标题+分类+正文前 800 字 |
| 取全文 | 按 question_id 精确取标准答案/得分点 | 命中后回查 SQLite 取 4000 字全文做 RAG 上下文 |
| 隔离 | 两集合物理隔离，互不可见 | 同左 |

出题检索 `get_question()` 只取题面不含答案；评分时 `get_answer()` 才按题号取标准答案与得分点，两者分离。

### 4.6 LLM 分层

- 快速模型（默认 deepseek-chat，温度 0.7）：开场/出题/评分/追问/收尾/提示/记忆压缩
- 强模型（可配 deepseek-reasoner，温度 0.3）：仅总结报告
- 视觉模型（qwen-vl-plus，可选）：扫描件 PDF 兜底，未配 Key 自动禁用
- Key 读取顺序：LLM_API_KEY → DEEPSEEK_API_KEY；DASHSCOPE_API_KEY → ALIYUN_API_KEY

## 五、REST 接口清单（除 login/register 外全部 JWT）

| 方法/路径 | 作用 | 隔离方式 |
|---|---|---|
| POST /api/login、/api/register | 登录/注册 | 公开 |
| POST /api/config | 配置面试参数，返回岗位与分类 | 用户 |
| GET /api/roles | 岗位列表 | 用户 |
| POST /api/resume/parse-text | 粘贴文本简历解析+岗位推荐 | 用户 |
| POST /api/upload/resume | PDF 简历（限 10MB） | 用户 |
| GET /api/reports、/api/reports/{id}、/radar、/weak-points | 报告列表/全文/雷达/薄弱点 | JSON 中 username，越权 404 |
| GET /api/interviews | 进程内会话列表 | username 过滤 |
| GET/DELETE /api/interview-records[/{filename}] | 逐题记录，文件名正则白名单 | MD 头「用户」字段，越权 404 |
| POST /api/logout | token 加入吊销黑名单 | 用户 |
| /api/kb/notes、/categories、/graph、/search、/qa、/chat/sessions* | 知识库笔记/图谱/检索/RAG/会话 | 全部按 username |
| POST /api/kb/notes/upload | 多文件入库（≤10 个、≤50MB） | 用户名前缀 |
| POST /api/kb/notes/url | 网址收藏（不抓网页，描述必填） | 用户 |
| POST /api/kb/tidy、/auto-category、/rebuild、/notes/from-report | AI 整理/分类/重建/薄弱点入库 | 用户 |
| 静态挂载 /kb_files | 原始上传文件直读 | **无鉴权（见风险项）** |

## 六、一次完整面试的数据流（调试时按此顺序打断点）

1. 前端登录拿 JWT 存 localStorage；上传简历 → 后端解析技能并推荐岗位。
2. InterviewView 建 WS（带 token）→ 发 `config`（role/题量/难度/简历）。
3. server.py 建/取 `_sessions[thread_id]`，构造 initial_state，`graph.astream()` 启动。
4. configure→opening→prepare_question→emit_question 推流式 chunk；前端打字机显示+TTS 朗读；图停在 wait_answer 的 interrupt。
5. 前端发 `answer` → server 查 graph 当前 phase 校验合法性 → 附带 hint_count 发 `Command(resume=...)`。
6. score_initial（3 次评分→中位数→提示封顶）→ 路由决定是否追问；循环至题满。
7. closing 推 `interview_ended`；前端按钮发 `report` → summary 流式生成 → 落 `reports/*.md + *.json`，推 `report_ready`。
8. 前端跳转 SummaryView，按 report_id 拉 MD 全文与雷达 JSON；薄弱点可一键入知识库。

排查口诀：**流程问题看 graph.py 的 phase 走向；内容问题看 prompts.py + chains.py；鉴权/404 看 auth.py 与各接口的 username 比对；检索不准看 retriever 的 RRF 与题库 MD 字段。**

---

## 七、多维度总体评价

评分口径：5 = 毕设/答辩场景下显著超出预期，4 = 完善可用，3 = 基本达标有短板。

| 维度 | 评分 | 一句话结论 |
|---|---|---|
| 功能完整度 | ★★★★☆ 4.5 | 主闭环完整且有纵深：从简历到报告、追问、知识库闭环全部打通，并附测试 |
| 功能实现质量 | ★★★★☆ 4.0 | 状态机设计成熟、防幻觉等细节考究；但有重复代码、单文件过大等工程债 |
| 安全性 | ★★★☆☆ 3.5 | 认证骨架正确（bcrypt/JWT/隔离/白名单），但存在静态文件无鉴权、无限流、文件名未净化等问题 |
| 创新性 | ★★★★☆ 4.0 | LangGraph 人在回路、自一致性评分、防幻觉数据契约、连击自适应难度均超出普通 CRUD 毕设 |
| 架构与可维护性 | ★★★☆☆ 3.5 | 分层清晰，但 server.py 约 1200 行单体、内存态与持久化态并存 |
| 工程化（测试/部署/依赖） | ★★★☆☆ 3.0 | 有单测+烟雾测试值得加分；但依赖全部不锁版本、无 CI、运行产物入库 |
| 文档与可演示性 | ★★★★☆ 4.0 | README/START_GUIDE 可照做，前端有打字机/TTS/雷达，演示完成度高 |

### 7.1 完整度（强项）

- 面试主闭环无断点：登录 → 简历（PDF/文本/视觉兜底）→ 匹配/选岗 → 配置 → 流式面试 → 追问 → 报告（MD+JSON 雷达）→ 记录回看 → 薄弱点回流知识库，形成「测评→复习」闭环。
- 知识库不是附属 demo：双链 backlink、语义图谱、文件/网址多来源、RAG 问答带会话持久化、AI 整理与自动分类、稀疏结果提示导入，功能面接近小型 Notion+RAG。
- 测试面覆盖认证、图流程、协议、分数解析、知识库、数据完整性，另有 8 个真实 LLM 烟雾脚本，在同类学生项目中少见。

### 7.2 功能实现（亮点与短板）

亮点：
- interrupt 恢复安全的设计自觉（等待节点无副作用）说明真正理解了 LangGraph 语义。
- 评分链路鲁棒：场景题与知识题区别对待（S 字段语义不同）、3 次采样中位数抑制抽风、异常时返回 0 分兜底而不崩。
- 报告生成三级降级（强模型→快模型→模板），演示时不怕模型端故障。

短板：
- `graph.py` 中 `score_candidate` 存在**两份定义**，前一份（约 L411-452）是无返回值的死代码，被第二份直接覆盖——合并代码留下的重复块。
- server.py 同时存在 `_logger` 与 `logger` 两个同义日志器。
- 持久化不彻底：checkpoint 在 SQLite，但 `_memories/_sessions/_hints` 在进程内存，重启后续接面试会丢对话记忆与提示计数。

### 7.3 安全性（骨架正确，边界需收紧）

做得对的：
- 密码 bcrypt（非 MD5）、用户名正则、密码长度与 72 字节上限（bcrypt 截断防护）。
- JWT 密钥未配置时 `secrets.token_hex(32)` 自动生成并落盘复用；登出有摘要式吊销名单并顺带清理过期项；每次鉴权回查用户是否仍存在。
- 报告、面试记录、笔记三层用户隔离，越权统一 404（不泄露存在性）；report_id 与记录文件名都有正则/字符白名单，防路径穿越；SQL 全部参数化。
- WebSocket 握手强制 token，会话续接校验归属。

需要修的（按风险排序，证据见第九节）：
1. `/kb_files` 静态目录**无鉴权**，且知识库文件名含用户名与时间戳，属于"知道/猜到 URL 即可访问他人上传原件"的水平越权面。
2. 知识库上传保存时直接拼接客户端文件名，未做 `secure_filename` 式净化，构造的 `../` 文件名存在路径穿越写文件风险（需登录，中危）。
3. 登录/注册无任何限流与锁定，可在线爆破弱密码（admin/123123 为预置账号）。
4. JWT 存 localStorage，XSS 即可窃取；CORS 允许 `null`（file://）来源。
5. 依赖未锁版本、运行库文件（checkpoints.db*、.pytest_tmp_run、kb_files 测试产物）留在仓库中。

### 7.4 创新性（答辩加分项）

1. **人在回路状态机**：把"等待人类"建成显式节点，resume 不重复出题/计费——比用 if/elif 手写 WebSocket 会话状态的写法高一个抽象层级。
2. **评分自一致性**：N 次独立评分取中位数 + 得分点过半投票，把"LLM 评分抖动"这一真实问题工程化处理。
3. **防幻觉数据契约**：明确区分"跨题出题不读评分产出"与"同题追问可读 missed_points"，并在低分场景加硬性禁令，是有 prompt 工程经验沉淀的设计。
4. **连击式自适应难度 + 提示使用封顶**：游戏化且可解释（报告里有 difficulty_changes 轨迹）。
5. **题库/知识库双库隔离 + 薄弱点一键入库带覆盖检测**：学习闭环有产品思维。
6. 周边体验：面试官人设、防背题变体题、项目深挖模式、打字机流式、TTS 朗读、雷达图。

---

## 八、已核实的问题清单（带证据）

| # | 严重度 | 问题 | 证据位置 | 建议修法 |
|---|---|---|---|---|
| 1 | 高(P0) | 知识库上传文件名未净化，`safe_name = f"{user}_{ts}_{name}"` 直接用客户端 name，含 `../` 时可能穿越写盘 | server.py `api_kb_upload` | 用 werkzeug.utils.secure_filename 或自写白名单（去路径分隔符/..），并拒绝非法名 |
| 2 | 高(P0) | `/kb_files` 静态挂载无鉴权，他人上传原件可被直链访问 | server.py L79-81 | 改为鉴权下载接口（验归属后 FileResponse），或用不可猜测 UUID 文件名+短时效签名 URL |
| 3 | 中(P1) | POST /api/config 对非法 role 兜底为 `"general_hr"`，而 ROLES 现仅含 llm_app，下一行 `config.ROLES[role_key]` 必抛 KeyError → 500 | server.py L271-272；config.py ROLES | 兜底改为 `"llm_app"`（与 WS 分支一致） |
| 4 | 中(P1) | 登录无限流/无锁定，存在弱口令爆破面；预置 admin/123123 | auth.py；server.py /api/login | 加 slowapi 限流（如 5 次/分钟/IP）、失败计数与临时锁定；演示账号仅在显式 DEMO 标志下创建 |
| 5 | 中(P1) | score_candidate 重复定义，前一份为死代码（无 return 分支） | graph.py 约 L411-452 vs L453+ | 删除前一份 |
| 6 | 低(P2) | CORS 允许 null 来源；JWT 在 localStorage（XSS 可窃取） | config.py CORS_ORIGINS；frontend auth.js | 生产环境移除 null；高安全需求改 httpOnly Cookie + CSRF 防护 |
| 7 | 低(P2) | requirements 全部 `>=` 不锁版本，langchain/chromadb 迭代快，易出现新装环境不兼容 | requirements.txt | pip-compile 生成锁定文件或至少 pin 主版本 |
| 8 | 低(P2) | 运行产物入库：checkpoints.db(-shm/-wal)、.pytest_tmp_run/、kb_files 大量重复 a.exe/dup.md 测试件 | 仓库目录 | 补 .gitignore 并清理；kb_files 文件名加 UUID |
| 9 | 低(P2) | `@app.on_event("startup")` 为已弃用 API | server.py `_migrate_kb_file_paths` | 改 lifespan 上下文管理器 |
| 10 | 低(P2) | 记忆/会话/提示计数纯进程内，重启续接后 history 与 hints 丢失 | graph.py `_memories`；server.py `_sessions/_hints` | 迁入 SQLite/Redis；或在文档明确"续接仅限图状态" |
| 11 | 信息 | 简历上传代码限 10MB，知识库限 50MB，两处限制不统一且与部分文档描述不一致 | server.py 两处 MAX_SIZE | 统一常量并写入 config.py |
| 12 | 信息 | 评分每题 3 次 LLM 调用，追问后合并再 3 次，延迟与成本偏高 | config.SCORING_SAMPLES | 采样次数可按难度/题型配置；或采样改并发调用 |

## 九、优化方向建议（按优先级路线图）

### P0 — 安全与正确性（改动小、收益大，答辩前应做）

1. 文件名净化 + 上传鉴权下载（问题 1、2）：一个 `_safe_filename()` 工具 + 一个 `/api/kb/files/{id}` 下载接口即可。
2. 修 `/api/config` 的 general_hr KeyError（问题 3），一行改动。
3. 登录限流：引入 slowapi 或自写"按 IP+用户名的失败计数表"，失败 5 次锁定 15 分钟。
4. 删除重复的 score_candidate 死代码。

### P1 — 工程质量与稳定性

5. 拆分 server.py：`routers/auth.py、reports.py、interview.py、kb.py`，main 只留 app 工厂与中间件；共用依赖下沉。
6. 依赖锁定 + 增加 `pip install` 可复现性；运行产物清出仓库，`.gitignore` 补 `*.db*`、`.pytest_tmp_run/`、`kb_files/*` 等。
7. 状态持久化收口：把 `_sessions/_hints/_memories` 迁入 SQLite（记忆可只持久化消息列表+摘要，恢复时重建 InterviewMemory），真正兑现"重启可续接"。
8. 并发评分：3 次采样用 `asyncio.gather` 并发（当前 invoke 为同步串行），可显著降低等待感；或把采样次数做成按题型配置（场景题 1 次、知识题 3 次）。
9. 统一文件大小/类型常量进 config.py；启动迁移改 lifespan。

### P2 — 产品与体验拔高（毕设创新点方向）

10. 评分可信度产品化：在报告中展示"采样分分布/中位数/离散度"，把自一致性从内部机制变成用户可见的"评分置信度"，并允许对争议评分申请复评。
11. 错题本间隔复习：基于已有 weak-points 接口加 SM-2/艾宾浩斯调度，结合知识库笔记推送复习，形成"面试→报告→薄弱点入库→间隔复习→再面试"的完整学习闭环（数据结构已基本齐备）。
12. 评测体系：构建一份带标准答案的黄金题集（30~50 题），离线跑评分链，输出 LLM 评分与人工分的相关性/偏差报告——这是把项目从"应用"提升为"有评测的 AI 系统"的最有力证据。
13. 语音面试：现有 TTS 已就绪，可补浏览器 STT（webkitSpeechRecognition）形成语音双通道；注意 STT 开始即停止 TTS（useWebSocket 中已有钩子）。
14. 可观测性：为每次 LLM 调用落结构化日志（题目 id、耗时、token、采样分、是否降级），提供一个简单的 `/admin/metrics` 或本地 JSON，答辩时展示"系统在监控自己"。
15. 多岗位恢复即"多智能体配置"：data_disabled 的 8 个岗位恢复后，把人设/难度/标签做成可配置 profile，讲述为"可扩展岗位插件"。
16. 部署现代化：补 Dockerfile（后端+前端分离构建）与一键 docker-compose，展示工程交付能力；生产关闭 /docs、收紧 CORS、管理 admin 账号。

### 答辩讲解建议（把技术选择讲成"权衡"）

- LangGraph vs 手写状态机：选择为"恢复安全 + 状态可持久化"，代价是引入 interrupt 重跑语义约束——你们已用"等待节点无副作用"的规则化解。
- 双模型分层 + 三级降级：成本/质量/可用性三角权衡。
- RRF 双路检索：BM25 保术语精确（如"BGE""RRF"缩写），向量保语义，权重 0.4/0.6 可调。
- 自一致性评分：承认 LLM 评分不稳定，用多次采样中位数对冲，而不是假装一次评分就可靠。

---

## 十、关键配置速查（改参数时看这里）

| 想改什么 | 改哪里 |
|---|---|
| 检索权重/数量 | config.py：TOP_K=5、BM25_WEIGHT=0.4、VECTOR_WEIGHT=0.6、RRF_K=60 |
| 评分采样次数 | config.py：SCORING_SAMPLES（.env 可覆盖） |
| 模型/Key/温度 | .env：LLM_MODEL_FAST、LLM_MODEL_STRONG、LLM_BASE_URL |
| 追问分档/难度规则 | agent/graph.py：initial_score_router、finalize_question_node |
| 提示封顶 | agent/graph.py：_apply_hint_cap（8/6 两档） |
| 人设/岗位/难度标签 | config.py：INTERVIEWER_PERSONAS、ROLES、DIFFICULTY_LABELS |
| 记忆窗口/压缩阈值 | config.py：MEMORY_WINDOW_SIZE=10、MEMORY_COMPRESS_THRESHOLD=6000 |
| 演示固定首题 | graph.py：DEMO_FIRST_QUESTION_ID（置空关闭） |
| 存储路径 | config.py：*_DB_PATH、REPORTS_DIR、CHROMA_DB_PATH、KB_CHROMA_PATH |

## 十一、新手上手路径建议

1. 先跑通：README + START_GUIDE，用 admin/123123 走一场 3 题面试，对照 `reports/` 新生成的 MD/JSON 看产物。
2. 读代码顺序：config.py → state.py → protocol.py → graph.py（先看末尾图定义，再回看各节点）→ server.py 的 WS 段 → retriever.py → chains.py/prompts.py。
3. 改一个小功能练手：例如把追问分档从 3~6 改为 2~7（只动 initial_score_router），跑 tests/test_interview_graph.py 验证。
4. 再动 P0 清单：文件名净化、config 兜底 bug、删死代码——都是小改动，适合建立对代码库的信心。
