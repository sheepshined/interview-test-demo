"""
server.py — AI 面试系统 FastAPI 后端 (LangGraph 版, 流式输出)

架构 (答辩稳定版): 面试流程由 LangGraph StateGraph 驱动 (agent/graph.py),
  WebSocket /ws/chat 仅作"人在回路驱动器": 接收 config/answer/end/report 消息,
  转为 graph 的 astream / Command(resume=...) 调用, 并把图推送的 custom event
  转发给前端。替代原 server.py 的 if/elif 手动编排。

接口:
  POST /api/login              登录认证 (admin / 123123)
  POST /api/config             配置面试参数
  GET  /api/roles              获取所有岗位列表
  POST /api/resume/parse-text  解析粘贴的文本简历
  POST /api/upload/resume      上传简历 PDF
  WebSocket /ws/chat           实时面试对话 (graph 驱动, 流式推送)
  GET  /                       静态前端页面
"""
import json
import logging
import os
import sys
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 将项目根目录加入 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from retrieval.retriever import HybridRetriever
from resume.parser import parse_resume, build_resume_context
import config
from common import match_role, get_difficulty_label, extract_skills
from agent.graph import build_interview_graph
from agent.protocol import command_allowed, phase_error
from agent.chains import build_hint_chain
from agent.llm import get_fast_llm
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

logger = logging.getLogger(__name__)

# --- FastAPI 应用 ---
app = FastAPI(title="AI Interview System (LangGraph)", version="3.0.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 全局状态 (懒加载检索器) ---
_retriever: Optional[HybridRetriever] = None
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


def get_retriever() -> HybridRetriever:
    """懒加载混合检索器 (BM25 + 向量 + RRF)"""
    global _retriever
    if _retriever is None:
        print("[SERVER] 正在初始化混合检索器 (BM25 + 向量)...")
        _retriever = HybridRetriever()
    return _retriever


# --- LangGraph 引擎 (懒加载) ---
_graph = None
_checkpointer: Optional[MemorySaver] = None


def get_graph():
    """获取 (懒加载) 编译后的 LangGraph 面试图, 带 MemorySaver checkpointer

    首次调用时构建图 (需 retriever 就绪), 之后复用。
    checkpointer 按 thread_id 保存当前进程内的暂停点；服务重启续接不在本轮范围。
    """
    global _graph, _checkpointer
    if _graph is None:
        r = get_retriever()
        _checkpointer = MemorySaver()
        _graph = build_interview_graph(r).compile(checkpointer=_checkpointer)
    return _graph


async def run_graph_stream(ws: WebSocket, graph, input_or_command, thread_id: str):
    """运行 graph、转发 custom event，并同步会话 phase。"""
    cfg = {"configurable": {"thread_id": thread_id}}
    final_values = {}
    try:
        snapshot = graph.get_state(cfg)
        previous = snapshot.values or {}
        last_decision = previous.get("decision")
    except Exception:
        last_decision = None
    try:
        async for mode, payload in graph.astream(
            input_or_command, cfg, stream_mode=["custom", "values"]
        ):
            if mode == "custom" and isinstance(payload, dict):
                await ws.send_json(payload)
            elif mode == "values" and isinstance(payload, dict):
                final_values = payload
                if thread_id in _sessions:
                    _sessions[thread_id]["phase"] = payload.get("phase", "")
                    _sessions[thread_id]["answered_count"] = payload.get(
                        "main_question_count", 0
                    )
                    if payload.get("report_id"):
                        _sessions[thread_id]["report_id"] = payload["report_id"]
                decision = payload.get("decision")
                if decision and decision != last_decision:
                    last_decision = decision
                    await ws.send_json({
                        "type": "decision",
                        "action": decision.get("action", "next"),
                        "reason": decision.get("reason", ""),
                    })
    except WebSocketDisconnect:
        logger.info("WebSocket 在图执行期间断开 (thread=%s)", thread_id)
        raise
    except Exception as e:
        logger.exception("LangGraph 流程错误 (thread=%s): %s", thread_id, e)
        if thread_id in _sessions:
            _sessions[thread_id]["status"] = "error"
        try:
            await ws.send_json({"type": "error", "content": "面试流程执行失败，请重试"})
        except (WebSocketDisconnect, RuntimeError):
            logger.info("错误事件未发送：连接已关闭 (thread=%s)", thread_id)
    return final_values


def get_graph_values(graph, thread_id: str) -> dict:
    """读取线程当前已提交状态，用于校验 WebSocket 命令阶段。"""
    try:
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        return dict(snapshot.values or {})
    except Exception as exc:
        logger.warning("读取图状态失败 (thread=%s): %s", thread_id, exc)
        return {}


# --- 进行中面试会话登记（仅当前进程）---
_sessions: dict = {}

# --- 提示系统追踪 (每 thread 每题的提示使用次数) ---
# 结构: {thread_id: {question_id: hint_count}}
_hints: dict = {}


# ============================================================
# Pydantic 模型
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class InterviewConfig(BaseModel):
    role: str = "python_dev"
    question_count: int = Field(default=5, ge=1, le=20)
    difficulty: int = Field(default=2, ge=1, le=3)
    resume_context: str = ""
    resume_skills: List[str] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    success: bool
    message: str
    role_key: str = ""
    role_title: str = ""
    question_count: int = 0
    difficulty: int = 0
    difficulty_label: str = ""
    categories: List[str] = Field(default_factory=list)


class TextResumeRequest(BaseModel):
    content: str


# ============================================================
# REST API
# ============================================================

@app.post("/api/login")
async def api_login(req: LoginRequest):
    """登录认证 (演示用固定账号 admin/123123)"""
    if req.username == "admin" and req.password == "123123":
        token = hashlib.md5(f"{req.username}{req.password}interview".encode()).hexdigest()
        return {"success": True, "token": token, "username": req.username}
    return JSONResponse(status_code=401, content={"success": False, "message": "用户名或密码错误"})


@app.post("/api/config", response_model=ConfigResponse)
def api_config(cfg: InterviewConfig):
    """配置面试参数, 返回岗位信息与题目分类"""
    role_key = cfg.role if cfg.role in config.ROLES else "general_hr"
    role_info = config.ROLES[role_key]
    categories = get_retriever().get_categories(role=role_key)
    difficulty_label = get_difficulty_label(cfg.difficulty)
    return ConfigResponse(
        success=True,
        message=f"配置成功: {role_info['title']}, {cfg.question_count}题, {difficulty_label}",
        role_key=role_key, role_title=role_info["title"],
        question_count=cfg.question_count, difficulty=cfg.difficulty,
        difficulty_label=difficulty_label, categories=categories,
    )


@app.get("/api/roles")
def api_get_roles():
    """获取所有可选岗位列表"""
    roles = [{"key": k, "title": info["title"], "tags": info["tags"]}
             for k, info in config.ROLES.items()]
    return {"success": True, "roles": roles}


@app.post("/api/resume/parse-text")
def api_parse_text_resume(req: TextResumeRequest):
    """解析粘贴的文本简历: 提取技能 + 推荐岗位"""
    if not req.content.strip():
        return {"success": False, "message": "简历内容不能为空"}
    text = req.content
    skills = extract_skills(text)
    best_role, best_score = match_role(skills)
    return {
        "success": True, "skills": skills, "resume_context": text[:2000],
        "suggested_role": best_role if best_score > 0 else None,
        "suggested_role_title": config.ROLES[best_role]["title"] if (best_role and best_score > 0) else None,
        "match_score": best_score,
    }


@app.post("/api/upload/resume")
def api_upload_resume(file: UploadFile = File(...)):
    """上传并解析 PDF 简历 (parse_resume 内部调 LLM, 耗时较长, 用 def 不阻塞事件循环)"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"success": False, "message": "仅支持 PDF 文件"}

    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    contents = file.file.read()
    if len(contents) == 0:
        return {"success": False, "message": "文件为空，请重新选择"}
    if len(contents) > MAX_SIZE:
        return {"success": False, "message": f"文件过大 ({len(contents)//1024//1024}MB)，最大支持 10MB"}

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"resume_{ts}.pdf"
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        with open(save_path, "wb") as f:
            f.write(contents)
    except OSError as e:
        print(f"[ERROR] 保存文件失败: {e}")
        return {"success": False, "message": "文件保存失败，请重试"}

    try:
        data = parse_resume(save_path)
    except Exception as e:
        print(f"[ERROR] parse_resume 抛出异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"简历解析异常: {type(e).__name__}", "detail": str(e)}
    if not data:
        return {"success": False, "message": "简历解析失败，请检查文件内容（可能为扫描件或加密PDF）"}

    context = build_resume_context(data)
    skills = data.get("skills", [])
    best_role, best_score = match_role(skills)
    return {
        "success": True, "filename": file.filename, "char_count": data.get("char_count", 0),
        "skills": skills[:15], "name": data.get("name", ""), "resume_context": context,
        "suggested_role": best_role if best_score > 0 else None,
        "suggested_role_title": config.ROLES[best_role]["title"] if (best_role and best_score > 0) else None,
        "match_score": best_score,
    }


# ============================================================
# 报告管理 + 会话管理 API (阶段2)
# ============================================================

def _safe_report_id(report_id: str) -> bool:
    """校验 report_id 防路径穿越"""
    return bool(report_id) and "/" not in report_id and "\\" not in report_id and ".." not in report_id


@app.get("/api/reports")
def api_list_reports():
    """列出历史面试报告 (读 reports/*.json 元信息)"""
    reports = []
    if os.path.isdir(config.REPORTS_DIR):
        for fn in sorted(os.listdir(config.REPORTS_DIR), reverse=True):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(config.REPORTS_DIR, fn), encoding="utf-8") as f:
                    data = json.load(f)
                reports.append({
                    "report_id": data.get("report_id", fn[:-5]),
                    "role_title": data.get("role_title", ""),
                    "role_key": data.get("role_key", ""),
                    "difficulty_label": data.get("difficulty_label", ""),
                    "avg_score": data.get("avg_score", 0),
                    "total_questions": data.get("total_questions", 0),
                    "timestamp": data.get("timestamp", ""),
                })
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("跳过无效报告元数据 %s: %s", fn, exc)
    return {"success": True, "reports": reports}


@app.get("/api/reports/{report_id}")
def api_get_report(report_id: str):
    """获取某场面试报告全文 (markdown)"""
    if not _safe_report_id(report_id):
        return JSONResponse(status_code=400, content={"success": False, "message": "非法 report_id"})
    rp = os.path.join(config.REPORTS_DIR, f"{report_id}.md")
    if not os.path.isfile(rp):
        return JSONResponse(status_code=404, content={"success": False, "message": "报告不存在"})
    with open(rp, encoding="utf-8") as f:
        content = f.read()
    return {"success": True, "report_id": report_id, "content": content}


@app.get("/api/reports/{report_id}/radar")
def api_get_report_radar(report_id: str):
    """获取某场面试的雷达/维度数据 (四维均值 + 分类均值 + 逐题), 供前端 ECharts 渲染"""
    if not _safe_report_id(report_id):
        return JSONResponse(status_code=400, content={"success": False, "message": "非法 report_id"})
    jp = os.path.join(config.REPORTS_DIR, f"{report_id}.json")
    if not os.path.isfile(jp):
        return JSONResponse(status_code=404, content={"success": False, "message": "雷达数据不存在"})
    with open(jp, encoding="utf-8") as f:
        data = json.load(f)
    return {"success": True, "radar": data}


@app.get("/api/interviews")
def api_list_interviews():
    """列出当前进程内登记的面试会话。"""
    return {"success": True, "interviews": list(_sessions.values())}


# ============================================================
# WebSocket /ws/chat (LangGraph 驱动)
# ============================================================

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """实时面试对话；所有 resume 命令都先按 graph phase 校验。"""
    await ws.accept()
    thread_id = None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "无效的 JSON 格式"})
                continue
            if not isinstance(msg, dict):
                await ws.send_json({"type": "error", "content": "消息必须是 JSON 对象"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "config":
                thread_id = msg.get("thread_id") or f"iv_{uuid.uuid4().hex[:12]}"
                role = msg.get("role", "python_dev")
                if role not in config.ROLES:
                    role = "general_hr"
                try:
                    count = max(1, min(int(msg.get("question_count", 5)), 20))
                    diff = int(msg.get("difficulty", 2))
                except (TypeError, ValueError):
                    await ws.send_json({"type": "error", "content": "题量或难度格式错误"})
                    continue
                if diff not in config.DIFFICULTY_LABELS:
                    await ws.send_json({"type": "error", "content": "难度必须为 1、2 或 3"})
                    continue

                try:
                    graph = get_graph()
                except Exception as exc:
                    logger.exception("引擎初始化失败: %s", exc)
                    await ws.send_json({"type": "error", "content": "引擎初始化失败，请检查服务配置"})
                    continue

                retriever = get_retriever()
                role_info = config.ROLES[role]
                existing = _sessions.get(thread_id)
                if existing and existing.get("status") == "ongoing" and msg.get("thread_id"):
                    await ws.send_json({
                        "type": "config_ok", "content": "会话已恢复, 请继续作答",
                        "thread_id": thread_id,
                        "role_key": existing["role_key"], "role_title": existing["role_title"],
                        "question_count": existing["question_count"],
                        "difficulty": existing["difficulty"],
                        "difficulty_label": existing.get("difficulty_label", ""),
                        "categories": retriever.get_categories(role=existing["role_key"]),
                        "phase": existing.get("phase", ""),
                        "resumed": True,
                    })
                    await ws.send_json({
                        "type": "status",
                        "content": "已恢复内存中的会话状态",
                    })
                    continue

                await ws.send_json({
                    "type": "config_ok", "content": "配置完成",
                    "thread_id": thread_id,
                    "role_key": role, "role_title": role_info["title"],
                    "question_count": count, "difficulty": diff,
                    "difficulty_label": get_difficulty_label(diff),
                    "categories": retriever.get_categories(role=role),
                    "resumed": False,
                })
                _sessions[thread_id] = {
                    "thread_id": thread_id, "role_key": role, "role_title": role_info["title"],
                    "question_count": count, "difficulty": diff,
                    "difficulty_label": get_difficulty_label(diff),
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "ongoing",
                    "phase": "starting",
                    "answered_count": 0,
                }

                initial_state = {
                    "thread_id": thread_id, "role_key": role, "difficulty": diff,
                    "total_count": count,
                    "resume_context": str(msg.get("resume_context", ""))[:6000],
                    "resume_skills": (
                        msg.get("resume_skills", [])[:30]
                        if isinstance(msg.get("resume_skills", []), list) else []
                    ),
                }
                await run_graph_stream(ws, graph, initial_state, thread_id)

            elif msg_type == "answer":
                if not thread_id:
                    await ws.send_json({"type": "error", "content": "请先发送 config 配置面试"})
                    continue
                answer = str(msg.get("content", "")).strip()
                if not answer:
                    await ws.send_json({"type": "error", "content": "回答不能为空"})
                    continue
                if len(answer) > 5000:
                    await ws.send_json({"type": "error", "content": "单次回答不能超过 5000 字"})
                    continue
                graph = get_graph()
                values = get_graph_values(graph, thread_id)
                phase = values.get("phase", "")
                if not command_allowed("answer", phase):
                    await ws.send_json({
                        "type": "error",
                        "content": phase_error("answer", phase),
                    })
                    continue
                
                # 获取当前题目的提示使用次数
                current_question = values.get("current_question", {})
                question_id = current_question.get("id", "")
                hint_count = 0
                if thread_id in _hints and question_id in _hints[thread_id]:
                    hint_count = _hints[thread_id][question_id]
                
                action = "end" if answer.lower() in {"quit", "exit", "q"} else "answer"
                await run_graph_stream(
                    ws,
                    graph,
                    Command(resume={"action": action, "content": answer, "hint_count": hint_count}),
                    thread_id,
                )

            elif msg_type == "end":
                if not thread_id:
                    await ws.send_json({"type": "error", "content": "面试尚未开始"})
                    continue
                graph = get_graph()
                phase = get_graph_values(graph, thread_id).get("phase", "")
                if not command_allowed("end", phase):
                    await ws.send_json({
                        "type": "error",
                        "content": phase_error("end", phase),
                    })
                    continue
                await run_graph_stream(
                    ws,
                    graph,
                    Command(resume={"action": "end", "content": ""}),
                    thread_id,
                )

            elif msg_type == "report":
                if not thread_id:
                    await ws.send_json({"type": "error", "content": "面试尚未开始"})
                    continue
                graph = get_graph()
                values = get_graph_values(graph, thread_id)
                phase = values.get("phase", "")
                if not command_allowed("report", phase):
                    await ws.send_json({
                        "type": "error",
                        "content": phase_error("report", phase),
                    })
                    continue
                await run_graph_stream(
                    ws,
                    graph,
                    Command(resume={"action": "report", "content": ""}),
                    thread_id,
                )
                final_values = get_graph_values(graph, thread_id)
                if thread_id in _sessions and final_values.get("phase") == "completed":
                    _sessions[thread_id]["status"] = "ended"
                    _sessions[thread_id]["report_id"] = final_values.get("report_id", "")

            elif msg_type == "hint":
                if not thread_id:
                    await ws.send_json({"type": "error", "content": "面试尚未开始"})
                    continue
                graph = get_graph()
                values = get_graph_values(graph, thread_id)
                phase = values.get("phase", "")
                if not command_allowed("hint", phase):
                    await ws.send_json({
                        "type": "error",
                        "content": phase_error("hint", phase),
                    })
                    continue
                
                # 获取当前题目和候选人已回答内容
                current_question = values.get("current_question", {})
                question_id = current_question.get("id", "")
                question_text = current_question.get("question", "")
                candidate_answer = values.get("main_answer", "") or ""
                
                # 获取标准答案
                retriever = get_retriever()
                answer_data = retriever.get_answer(question_id)
                if not answer_data:
                    await ws.send_json({"type": "error", "content": "无法获取题目信息"})
                    continue
                standard_answer = answer_data.get("standard_answer", "")
                
                # 追踪提示使用次数
                if thread_id not in _hints:
                    _hints[thread_id] = {}
                if question_id not in _hints[thread_id]:
                    _hints[thread_id][question_id] = 0
                
                hint_count = _hints[thread_id][question_id]
                if hint_count >= 2:
                    await ws.send_json({"type": "error", "content": "每题最多使用 2 次提示"})
                    continue
                
                # 生成提示 (hint_level 从 1 开始)
                hint_level = hint_count + 1
                try:
                    hint_chain = build_hint_chain(get_fast_llm())
                    hint_text = hint_chain.invoke({
                        "question": question_text,
                        "standard_answer": standard_answer,
                        "hint_level": hint_level,
                        "candidate_answer": candidate_answer or "（尚未回答）",
                    })
                    _hints[thread_id][question_id] = hint_count + 1
                    
                    await ws.send_json({
                        "type": "hint",
                        "content": hint_text,
                        "hint_level": hint_level,
                        "question_id": question_id,
                    })
                except Exception as e:
                    logger.exception("生成提示失败: %s", e)
                    await ws.send_json({"type": "error", "content": "生成提示失败，请重试"})

            else:
                await ws.send_json({"type": "error", "content": f"未知消息类型: {msg_type}"})

    except WebSocketDisconnect:
        print("[WS] 客户端断开连接")
    except Exception as e:
        logger.exception("WebSocket 错误: %s", e)
        try:
            await ws.send_json({"type": "error", "content": "服务器内部错误"})
        except Exception:
            pass


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
