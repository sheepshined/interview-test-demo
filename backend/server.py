"""
server.py — AI 面试系统 FastAPI 后端 (LangChain 版, 流式输出)

接口:
  POST /api/login          登录认证 (admin / 123123)
  POST /api/config         配置面试参数
  POST /api/upload/resume  上传简历 PDF
  GET  /api/roles          获取所有岗位列表
  POST /api/resume/parse-text  解析粘贴的文本简历
  WebSocket /ws/chat       实时面试对话 (流式推送)
  GET  /                   静态前端页面

WebSocket 流式协议:
  服务端推送:
    {"type": "stream_start", "stream_type": "question|followup|report"}
    {"type": "stream_chunk", "content": "文本片段"}
    {"type": "stream_end", "stream_type": "...", "full_text": "完整文本"}
    {"type": "config_ok", ...}
    {"type": "decision", ...}
    {"type": "error", "content": "..."}
"""
import json
import os
import sys
import shutil
import hashlib
from datetime import datetime
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# 将项目根目录加入 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from retrieval.retriever import HybridRetriever
from agent.engine import InterviewEngine
from resume.parser import parse_resume, build_resume_context
import config

# --- FastAPI 应用 ---
app = FastAPI(title="AI Interview System (LangChain)", version="2.1.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 静态目录 ---
STATIC_DIR = os.path.join(BASE_DIR, "static")

# --- 全局状态 (懒加载检索器) ---
_retriever: Optional[HybridRetriever] = None
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


def get_retriever() -> HybridRetriever:
    """懒加载混合检索器"""
    global _retriever
    if _retriever is None:
        print("[SERVER] 正在初始化混合检索器 (BM25 + 向量)...")
        _retriever = HybridRetriever()
    return _retriever


# ============================================================
# Pydantic 模型
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class InterviewConfig(BaseModel):
    role: str = "python_dev"
    question_count: int = 5
    difficulty: int = 2
    resume_context: str = ""
    resume_skills: List[str] = []


class ConfigResponse(BaseModel):
    success: bool
    message: str
    role_key: str = ""
    role_title: str = ""
    question_count: int = 0
    difficulty: int = 0
    difficulty_label: str = ""
    categories: List[str] = []


class TextResumeRequest(BaseModel):
    content: str


# ============================================================
# REST API
# ============================================================

@app.post("/api/login")
async def api_login(req: LoginRequest):
    """简单登录认证 — admin / 123123"""
    if req.username == "admin" and req.password == "123123":
        token = hashlib.md5(f"{req.username}{req.password}interview".encode()).hexdigest()
        return {"success": True, "token": token, "username": req.username}
    return JSONResponse(status_code=401, content={"success": False, "message": "用户名或密码错误"})


@app.post("/api/config", response_model=ConfigResponse)
async def api_config(cfg: InterviewConfig):
    """配置面试参数"""
    r = get_retriever()

    role_key = cfg.role if cfg.role in config.ROLES else "general_hr"
    role_info = config.ROLES[role_key]

    categories = r.get_categories(role=role_key)
    difficulty_label = {1: "Junior", 2: "Intermediate", 3: "Senior"}.get(
        cfg.difficulty, "Intermediate"
    )

    return ConfigResponse(
        success=True,
        message=f"配置成功: {role_info['title']}, {cfg.question_count}题, {difficulty_label}",
        role_key=role_key,
        role_title=role_info["title"],
        question_count=cfg.question_count,
        difficulty=cfg.difficulty,
        difficulty_label=difficulty_label,
        categories=categories,
    )


@app.get("/api/roles")
async def api_get_roles():
    """获取所有可选岗位"""
    roles = []
    for key, info in config.ROLES.items():
        roles.append({"key": key, "title": info["title"], "tags": info["tags"]})
    return {"success": True, "roles": roles}


@app.post("/api/resume/parse-text")
async def api_parse_text_resume(req: TextResumeRequest):
    """解析粘贴的文本简历"""
    if not req.content.strip():
        return {"success": False, "message": "简历内容不能为空"}

    text = req.content
    skills = []
    common_skills = ["Python", "Java", "JavaScript", "Vue", "React", "TypeScript",
                     "Django", "Flask", "FastAPI", "Spring", "SQL", "MySQL",
                     "Docker", "Git", "Linux", "HTML", "CSS", "Node.js", "Go", "Rust"]
    for skill in common_skills:
        if skill.lower() in text.lower():
            skills.append(skill)

    best_role = None
    best_score = 0
    for rk, ri in config.ROLES.items():
        match = sum(1 for t in ri["tags"] if any(t.lower() in s.lower() for s in skills))
        if match > best_score:
            best_score = match
            best_role = rk

    return {
        "success": True,
        "skills": skills,
        "resume_context": text[:2000],
        "suggested_role": best_role if best_score > 0 else None,
        "suggested_role_title": config.ROLES[best_role]["title"] if (best_role and best_score > 0) else None,
        "match_score": best_score,
    }


@app.post("/api/upload/resume")
async def api_upload_resume(file: UploadFile = File(...)):
    """上传并解析 PDF 简历"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"success": False, "message": "仅支持 PDF 文件"}

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"resume_{ts}.pdf"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    data = parse_resume(save_path)
    if not data:
        return {"success": False, "message": "简历解析失败，请检查文件内容"}

    context = build_resume_context(data)

    skills = data.get("skills", [])
    best_role = None
    best_score = 0
    for rk, ri in config.ROLES.items():
        match = sum(1 for t in ri["tags"] if any(
            t.lower() in s.lower() for s in skills))
        if match > best_score:
            best_score = match
            best_role = rk

    return {
        "success": True,
        "filename": file.filename,
        "char_count": data.get("char_count", 0),
        "skills": skills[:15],
        "name": data.get("name", ""),
        "resume_context": context,
        "suggested_role": best_role if best_score > 0 else None,
        "suggested_role_title": config.ROLES[best_role]["title"] if (best_role and best_score > 0) else None,
        "match_score": best_score,
    }


# ============================================================
# WebSocket 流式推送辅助函数
# ============================================================

async def ws_stream_generator(ws: WebSocket, gen, stream_type: str) -> str:
    full_text = ""
    await ws.send_json({"type": "stream_start", "stream_type": stream_type})

    try:
        for chunk in gen:
            full_text += chunk
            await ws.send_json({"type": "stream_chunk", "content": chunk})
    except Exception as e:
        await ws.send_json({"type": "error", "content": f"生成失败: {e}"})
    finally:
        await ws.send_json({
            "type": "stream_end",
            "stream_type": stream_type,
            "full_text": full_text,
        })
    return full_text


# ============================================================
# WebSocket /ws/chat (流式版)
# ============================================================

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()

    engine: Optional[InterviewEngine] = None
    configured = False
    interview_ended = False

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "无效的 JSON 格式"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "config":
                role = msg.get("role", "python_dev")
                count = int(msg.get("question_count", 5))
                diff = int(msg.get("difficulty", 2))
                res_ctx = msg.get("resume_context", "")
                res_sk = msg.get("resume_skills", [])

                if role not in config.ROLES:
                    role = "general_hr"

                r = get_retriever()
                engine = InterviewEngine(r)
                result = engine.configure(
                    role, total_count=count, difficulty=diff,
                    resume_context=res_ctx, resume_skills=res_sk,
                )
                configured = True

                cats = r.get_categories(role=role)
                diff_label = {1: "Junior", 2: "Intermediate", 3: "Senior"}.get(
                    diff, "Intermediate"
                )

                await ws.send_json({
                    "type": "config_ok",
                    "content": result,
                    "role_key": role,
                    "role_title": engine.role_info["title"],
                    "question_count": count,
                    "difficulty": diff,
                    "difficulty_label": diff_label,
                    "categories": cats,
                })

                try:
                    await ws_stream_generator(
                        ws, engine.generate_question_stream(), "question"
                    )
                except Exception as e:
                    await ws.send_json({"type": "error", "content": f"出题失败: {e}"})

            elif msg_type == "answer":
                if not configured or engine is None:
                    await ws.send_json({"type": "error", "content": "请先发送 config 配置面试"})
                    continue

                if interview_ended:
                    await ws.send_json({"type": "error", "content": "面试已结束，请点击生成报告"})
                    continue

                answer = msg.get("content", "").strip()
                if not answer:
                    await ws.send_json({"type": "error", "content": "回答不能为空"})
                    continue

                if answer.lower() in ("quit", "exit", "q"):
                    interview_ended = True
                    await ws.send_json({"type": "interview_ended", "content": "面试已结束", "can_report": True})
                    continue

                if answer.lower() in ("下一题", "换一题", "skip"):
                    try:
                        await ws.send_json({"type": "status", "content": "换下一题..."})
                        await ws_stream_generator(
                            ws, engine.generate_question_stream(), "question"
                        )
                    except Exception as e:
                        await ws.send_json({"type": "error", "content": f"出题失败: {e}"})
                    continue

                engine.receive_answer(answer)
                engine.score_answer()

                decision = engine.decide()
                action = decision.get("action", "next")

                await ws.send_json({
                    "type": "decision",
                    "action": action,
                    "reason": decision.get("reason", ""),
                })

                if action == "followup":
                    topic = decision.get("followup_topic", "")
                    await ws_stream_generator(
                        ws, engine.generate_followup_stream(topic), "followup"
                    )

                elif action == "end":
                    interview_ended = True
                    await ws.send_json({"type": "interview_ended", "content": "面试已完成", "can_report": True})
                    continue

                else:
                    try:
                        await ws_stream_generator(
                            ws, engine.generate_question_stream(), "question"
                        )
                    except Exception as e:
                        await ws.send_json({"type": "error", "content": f"出题失败: {e}"})

            elif msg_type == "report":
                if engine is None:
                    await ws.send_json({"type": "error", "content": "面试尚未开始"})
                    continue
                await ws_stream_generator(
                    ws, engine.generate_summary_stream(), "report"
                )

            else:
                await ws.send_json({"type": "error", "content": f"未知消息类型: {msg_type}"})

    except WebSocketDisconnect:
        print("[WS] 客户端断开连接")
    except Exception as e:
        print(f"[WS] 错误: {e}")
        try:
            await ws.send_json({"type": "error", "content": f"服务器内部错误: {str(e)}"})
        except Exception:
            pass


# ============================================================
# 静态文件服务
# ============================================================

@app.get("/")
@app.get("/index.html")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"detail": "Not Found", "message": "请将前端文件放入 static/ 目录"}

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)