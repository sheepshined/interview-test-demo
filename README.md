# AI 模拟面试官

基于 FastAPI、LangGraph 和 Vue 3 的本机模拟面试系统。答辩演示采用两个本地服务：

- FastAPI 后端：`http://127.0.0.1:8000`
- Vite 前端：`http://127.0.0.1:3000`

## 主要功能

- 用户体系：JWT 登录 + 在线注册（预置演示账号 `admin / 123123`），报告与会话按用户隔离
- PDF 简历解析或粘贴文本简历
- 9 个岗位、133 道题的混合检索题库
- LangGraph 人在回路面试、低分追问和合并重评
- Markdown 报告、雷达数据和本场报告精确跳转

## 核心流程

```text
登录 → 选择简历匹配或自主选岗 → 配置题量 → 开始面试
  → 出题 → 等待回答 → 评分 → 可选追问 → 下一题
  → 收尾 → 点击生成报告 → 本场总结页
```

LangGraph 将选题、流式输出和 `interrupt()` 等待拆成独立节点，恢复回答时不会重复选择或重复输出同一道题。

## 项目结构

```text
TOtal/
├── backend/
│   ├── server.py          FastAPI、REST、WebSocket
│   ├── main.py            题库 build/rebuild
│   ├── agent/             LangGraph、状态、提示词、评分
│   ├── retrieval/         BGE、BM25、Chroma、RRF
│   ├── resume/            PDF 与文本简历解析
│   ├── data/              8 岗位、86 道题
│   └── tests/             自动化测试和真实烟雾脚本
├── frontend/              Vue 3 SPA
├── START_GUIDE.md         本机启动手册
└── OPTIMIZATION_PLAN.md   历史优化方案
```

## 首次准备

后端：

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 并填写 `LLM_API_KEY`。首次运行或题库变更后构建向量库：

```powershell
python main.py build
```

前端：

```powershell
cd E:\hiagent\DEMO3\TOtal\frontend
npm install
```

## 日常启动

PowerShell 窗口 1：

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

PowerShell 窗口 2：

```powershell
cd E:\hiagent\DEMO3\TOtal\frontend
npm run dev -- --host 127.0.0.1
```

浏览器打开 `http://127.0.0.1:3000`。详细步骤见 [START_GUIDE.md](START_GUIDE.md)。

## 测试

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
python -m pip install -r requirements-dev.txt
python -m pytest -q

cd ..\frontend
npm run build
```

真实 LLM 烟雾测试需要先启动后端：

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
python tests\real_smoke.py
```

## 当前边界

- 登录为 JWT + SQLite 用户表（v0.6），暂无改密码/登出吊销/管理员分级。
- 会话和 LangGraph checkpointer 位于当前进程内，后端重启后不能续接。
- 扫描图片型 PDF 走千问视觉兜底（需配 DASHSCOPE_API_KEY），未配置时请用粘贴文本入口。
- 正式演示入口只有 Vite 前端 `:3000`，后端 `:8000` 只提供接口和 `/docs`。
