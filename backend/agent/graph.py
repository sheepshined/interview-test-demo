"""
agent/graph.py — LangGraph 面试流程状态图 (阶段1 核心)

将原 InterviewEngine 的"手动状态机 + 7 个 LCEL Chain + server.py if/elif 编排",
重构为 LangGraph StateGraph:

  - 状态集中:   InterviewState (state.py) 替代散落的实例变量
  - 流程声明式: 图的节点+边定义, 替代 server.py ws_chat 的 if/elif 调用
  - 人在回路:   ask/followup 节点末尾 interrupt() 暂停, 等用户回答后 Command(resume=...) 恢复
  - 持久化:     compile(checkpointer=...) 后, 暂停点可按 thread_id 恢复 (断线续接基础)

图结构:
  START -> configure -> opening -> ask -(interrupt)->
  receive_answer -> score -> decide
  decide --followup--> followup -(interrupt)-> receive_answer
  decide --next--> ask
  decide --end--> closing -> summary -> END

流式输出: 节点内用 get_stream_writer() 推 custom event (stream_start/chunk/end/decision/...),
          server.py 用 graph.astream(stream_mode="custom") 接收并转发 WebSocket。
"""
import os
import re
import time
import random
from typing import Dict, List, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.config import get_stream_writer
from langchain_core.language_models import BaseChatModel

import config
from agent.llm import get_fast_llm, get_strong_llm
from agent.chains import (
    build_question_chain,
    build_scoring_chain,
    build_followup_chain,
    build_summary_chain,
    build_opening_chain,
    build_closing_chain,
    get_format_instructions,
)
from agent.models import ScoreResult
from agent.state import InterviewState
from retrieval.retriever import HybridRetriever

import logging

logger = logging.getLogger(__name__)


# ============================================================
# 流式输出 helper
# ============================================================

async def _stream_chain(writer, chain, chain_input: dict, stream_type: str) -> str:
    """流式调用 LCEL chain, 通过 custom event 推送 stream_start/chunk/end 三段式协议

    Returns: 完整文本 (供节点累积/记录用)
    """
    writer({"type": "stream_start", "stream_type": stream_type})
    full_text = ""
    try:
        async for chunk in chain.astream(chain_input):
            full_text += chunk
            writer({"type": "stream_chunk", "content": chunk})
    except Exception as e:
        logger.warning("%s 流式生成失败: %s", stream_type, e)
        writer({"type": "error", "content": f"{stream_type}生成失败: {e}"})
    writer({"type": "stream_end", "stream_type": stream_type, "full_text": full_text})
    return full_text


# ============================================================
# 辅助逻辑 (从 engine.py 迁移为纯函数, 操作 state 而非实例变量)
# ============================================================

def _band(score: int) -> str:
    """分数 → 表现档位 (调节语气)"""
    if score >= 8:
        return "优秀"
    if score >= 5:
        return "合格"
    return "待加强"


def _get_filtered_resume_skills(state: InterviewState) -> List[str]:
    """过滤简历技能: 只保留与当前岗位 tag 相关的 (防止跨岗位出题)"""
    skills = state.get("resume_skills", [])
    if not skills:
        return []
    role_tags = [t.lower() for t in state["role_info"].get("tags", [])]
    if not role_tags:
        return skills
    return [s for s in skills if any(s.lower() in t or t in s.lower() for t in role_tags)]


def _select_topic_for_search(state: InterviewState) -> str:
    """选择搜索话题, 第一题优先 first_topic_hint, 后续按简历技能/岗位 tag 随机采样"""
    if state.get("main_question_count", 0) == 0 and state.get("first_topic_hint"):
        return state["first_topic_hint"]
    relevant = _get_filtered_resume_skills(state)
    if relevant:
        return " ".join(random.sample(relevant, min(len(relevant), random.randint(2, 3))))
    tags = state["role_info"].get("tags", [])
    if tags:
        return " ".join(random.sample(tags, min(len(tags), random.randint(2, 3))))
    return state["role_info"].get("title", "")


def _select_preferred_category(state: InterviewState, retriever: HybridRetriever) -> Optional[str]:
    """选择下一个优先分类 (分类轮换)"""
    all_cats = retriever.get_categories(role=state["role_key"])
    if not all_cats:
        return None
    asked = state.get("asked_categories", [])
    unasked = [c for c in all_cats if c not in asked]
    if unasked:
        return random.choice(unasked)
    for c in reversed(asked):
        if c in all_cats:
            return c
    return random.choice(all_cats)


def _build_prev_context(state: InterviewState) -> str:
    """构建上一题回顾 (注入出题 prompt 生成承上启下)"""
    records = state.get("records", [])
    if not records:
        return "（这是第一题, 无需衔接上一题）"
    last = records[-1]
    prev_q = last.get("question", "")[:120]
    prev_band = _band(last.get("score", 0))
    hit = last.get("hit_points", [])
    prev_summary = "、".join(hit[:3]) if hit else last.get("user_answer", "")[:80]
    missed = last.get("missed_points", [])
    direction = missed[0] if missed else prev_q[:40]
    return (
        f"## 上一题回顾（用于生成承上启下）\n"
        f"上一题: {prev_q}\n候选人回答要点: {prev_summary}\n"
        f"表现档位: {prev_band}\n可衔接方向: {direction}"
    )


def _append_to_md(state: InterviewState, record: Dict):
    """每条回答立即追加到 .md 记录文件"""
    md_path = state.get("md_path")
    if not md_path:
        return
    try:
        with open(md_path, "a", encoding="utf-8") as f:
            i = len(state.get("records", []))
            tag = " [追问]" if record.get("is_followup") else ""
            bd = record.get("score_breakdown", {})
            f.write(
                f"## 第{i}题{tag}\n\n**题目**: {record['question']}\n\n"
                f"**你的回答**:\n\n{record['user_answer']}\n\n"
                f"**标准答案**: {record.get('standard_answer', '暂无')[:500]}\n\n"
                f"**得分**: {record['score']}/{record['max_score']}\n\n"
                f"**评分维度**: 准确性={bd.get('accuracy', '?')} "
                f"完整性={bd.get('completeness', '?')} 深度={bd.get('depth', '?')} "
                f"清晰度={bd.get('clarity', '?')}\n\n---\n\n"
            )
    except Exception as e:
        logger.warning("追加面试记录失败: %s", e)


# ============================================================
# 图构建器 (闭包捕获 retriever/llm/chains)
# ============================================================

def build_interview_graph(
    retriever: HybridRetriever,
    fast_llm: BaseChatModel = None,
    strong_llm: BaseChatModel = None,
) -> StateGraph:
    """构建面试流程 StateGraph (未 compile, 由调用方加 checkpointer 后 compile)

    模型分层 (阶段3): 出题/评分/追问/开场/收尾用 fast_llm (求速度),
    总结报告用 strong_llm (求质量, 低温)。
    """
    fast_llm = fast_llm or get_fast_llm()
    strong_llm = strong_llm or get_strong_llm()
    question_chain = build_question_chain(fast_llm)
    scoring_chain = build_scoring_chain(fast_llm)
    followup_chain = build_followup_chain(fast_llm)
    opening_chain = build_opening_chain(fast_llm)
    closing_chain = build_closing_chain(fast_llm)
    summary_chain = build_summary_chain(strong_llm)

    # --------------------------------------------------------
    # 节点: configure
    # --------------------------------------------------------
    def configure_node(state: InterviewState) -> dict:
        role_key = state["role_key"] if state.get("role_key") in config.ROLES else "general_hr"
        role_info = config.ROLES[role_key]
        difficulty = state.get("difficulty", 2)
        difficulty_label = config.DIFFICULTY_LABELS.get(difficulty, "Intermediate")
        resume_context = state.get("resume_context", "")
        resume_skills = state.get("resume_skills", [])

        name_match = re.search(r"姓名[:：]\s*([^\s,，。;；\n、]{2,8})", resume_context)
        candidate_name = name_match.group(1).strip() if name_match else ""

        d = os.path.dirname(os.path.abspath(__file__))
        ts = time.strftime("%Y%m%d_%H%M%S")
        md_path = os.path.join(d, f"interview_records_{ts}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# AI 模拟面试记录\n\n- **岗位**: {role_info['title']}\n"
                    f"- **难度**: {difficulty_label}\n- **题量**: {state.get('total_count', 5)}\n"
                    f"- **简历**: {'是' if resume_context else '否'}\n- **时间**: {ts}\n"
                    f"- **引擎**: LangGraph\n\n---\n\n"
                )
        except Exception as e:
            logger.warning("初始化记录文件失败: %s", e)

        return {
            "role_key": role_key, "role_info": role_info, "difficulty": difficulty,
            "difficulty_label": difficulty_label, "candidate_name": candidate_name,
            "md_path": md_path, "asked_ids": [], "asked_categories": [], "records": [],
            "main_question_count": 0, "followup_count": 0, "is_followup_phase": False,
            "first_topic_hint": "",
        }

    # --------------------------------------------------------
    # 节点: opening
    # --------------------------------------------------------
    async def opening_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        relevant = _get_filtered_resume_skills(state)
        if relevant:
            first_hint = random.choice(relevant)
        else:
            tags = state["role_info"].get("tags", [])
            first_hint = random.choice(tags) if tags else state["role_info"].get("title", "")

        chain_input = {
            "role_title": state["role_info"]["title"],
            "difficulty_label": state["difficulty_label"],
            "total_count": state.get("total_count", 5),
            "candidate_name": state.get("candidate_name") or "你",
            "first_direction": first_hint,
        }
        await _stream_chain(writer, opening_chain, chain_input, "opening")
        return {"first_topic_hint": first_hint}

    # --------------------------------------------------------
    # 节点: ask (出题 + interrupt 等回答)
    # --------------------------------------------------------
    async def ask_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        # 兜底推送 decision (resume 后首个 custom event 偶发丢失, 此处补发给前端)
        _decision = state.get("decision")
        if _decision:
            writer({"type": "decision", "action": _decision.get("action", "next"),
                    "reason": _decision.get("reason", "")})
        topic = _select_topic_for_search(state)
        preferred_cat = _select_preferred_category(state, retriever)
        asked_ids = state.get("asked_ids", [])

        candidates = retriever.get_question(
            topic=topic, role=state["role_key"], difficulty=state.get("difficulty"),
            exclude_ids=asked_ids, top_k=5,
        )
        if not candidates:
            candidates = retriever.get_question(
                topic=topic, role=state["role_key"], exclude_ids=asked_ids, top_k=5,
            )
        if not candidates:
            q = retriever.get_random_question(role=state["role_key"], exclude_ids=asked_ids)
            if not q:
                # 题库耗尽: 提示后走空回答 (后续 score 兜底)
                writer({"type": "stream_start", "stream_type": "question"})
                msg = "[System] 题库已无更多题目。"
                writer({"type": "stream_chunk", "content": msg})
                writer({"type": "stream_end", "stream_type": "question", "full_text": msg})
                human_answer = interrupt({"type": "await_answer"})
                return {"human_answer": human_answer}
            candidates = [q]

        chosen = candidates[0]
        if preferred_cat:
            for c in candidates:
                if c.get("category") == preferred_cat:
                    chosen = c
                    break

        new_asked_ids = asked_ids + [chosen["id"]]
        new_asked_cats = list(state.get("asked_categories", []))
        if chosen.get("category"):
            new_asked_cats.append(chosen["category"])
        main_count = state.get("main_question_count", 0) + 1

        # 简历上下文
        resume_ctx = state.get("resume_context", "")
        if resume_ctx:
            relevant = _get_filtered_resume_skills(state)
            skill_hint = relevant[0] if relevant else "相关经验"
            resume_section = (
                f"## 候选人简历摘要\n{resume_ctx[:500]}\n## 提问要求\n"
                f"可以自然地结合候选人简历中提到的'{skill_hint}'来引出题目,"
                f"但不要每次都用相同的句式开头。题目的核心技术内容必须来自下面的题库题目。"
            )
        else:
            resume_section = "(无简历信息, 直接出题)"

        chain_input = {
            "role_title": state["role_info"]["title"],
            "difficulty_label": state["difficulty_label"],
            "question_index": main_count,
            "total_count": state.get("total_count", 5),
            "question_text": chosen["question"],
            "resume_section": resume_section,
            "prev_context": _build_prev_context(state),
            "history": [],
        }
        await _stream_chain(writer, question_chain, chain_input, "question")

        # 人在回路: 暂停等待用户回答
        human_answer = interrupt({"type": "await_answer"})
        return {
            "human_answer": human_answer,
            "current_question": chosen,
            "asked_ids": new_asked_ids,
            "asked_categories": new_asked_cats,
            "main_question_count": main_count,
            "is_followup_phase": False,
            "followup_count": 0,
        }

    # --------------------------------------------------------
    # 节点: receive_answer (从 human_answer 取回答 + 检索标准答案)
    # --------------------------------------------------------
    def receive_answer_node(state: InterviewState) -> dict:
        human_answer = state.get("human_answer", "")
        current_q = state.get("current_question") or {}
        answer_data = None
        if current_q:
            answer_data = retriever.get_answer(current_q["id"])
        return {"last_user_answer": human_answer, "current_answer_data": answer_data}

    # --------------------------------------------------------
    # 节点: score (评分 + 追加记录)
    # --------------------------------------------------------
    def score_node(state: InterviewState) -> dict:
        current_q = state.get("current_question") or {}
        ad = state.get("current_answer_data")
        last_answer = state.get("last_user_answer", "")
        is_followup = state.get("is_followup_phase", False)

        if not ad:
            record = {
                "question_id": current_q.get("id", ""),
                "question": current_q.get("question", ""),
                "user_answer": last_answer, "standard_answer": "", "score": 0,
                "max_score": 10,
                "score_breakdown": {"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0},
                "hit_points": [], "missed_points": [],
                "feedback": "未找到标准答案, 无法评分", "is_correct": False,
                "category": current_q.get("category", ""),
                "difficulty": current_q.get("difficulty", 2),
                "is_followup": is_followup,
                "round": len(state.get("records", [])) + 1,
            }
        else:
            scoring_points_str = (
                "\n".join(f"  - {p}" for p in ad["scoring_points"])
                if ad["scoring_points"] else "无明确得分点"
            )
            try:
                score_result: ScoreResult = scoring_chain.invoke({
                    "question": ad["question"], "standard_answer": ad["standard_answer"],
                    "scoring_points": scoring_points_str, "candidate_answer": last_answer,
                    "format_instructions": get_format_instructions(),
                })
                record = {
                    "question_id": current_q.get("id", ""), "question": ad["question"],
                    "user_answer": last_answer, "standard_answer": ad["standard_answer"],
                    **score_result.to_record(), "category": ad.get("category", ""),
                    "difficulty": ad.get("difficulty", 2), "is_followup": is_followup,
                    "round": len(state.get("records", [])) + 1,
                }
            except Exception as e:
                record = {
                    "question_id": current_q.get("id", ""), "question": ad["question"],
                    "user_answer": last_answer, "standard_answer": ad["standard_answer"],
                    "score": 0, "max_score": 10,
                    "score_breakdown": {"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0},
                    "hit_points": [], "missed_points": ad.get("scoring_points", []),
                    "feedback": f"评分失败: {e}", "is_correct": False,
                    "category": ad.get("category", ""), "difficulty": ad.get("difficulty", 2),
                    "is_followup": is_followup, "round": len(state.get("records", [])) + 1,
                }

        new_records = list(state.get("records", [])) + [record]
        _append_to_md({**state, "records": new_records}, record)
        return {"records": new_records}

    # --------------------------------------------------------
    # 节点: decide (决策 + 推 decision event)
    # --------------------------------------------------------
    async def decide_node(state: InterviewState) -> dict:
        records = state.get("records", [])
        updates: Dict = {}

        if not records:
            decision = {"action": "next", "reason": "无记录"}
        else:
            last_score = records[-1]["score"]
            if state.get("main_question_count", 0) >= state.get("total_count", 5):
                decision = {"action": "end", "reason": f"已完成 {state.get('total_count', 5)} 道题"}
            elif state.get("followup_count", 0) == 0 and last_score < 5:
                missed = records[-1].get("missed_points", [])
                topic = missed[0] if missed else records[-1].get("question", "")[:50]
                decision = {"action": "followup", "reason": f"得分 {last_score}/10, 需要追问",
                            "followup_topic": topic}
                updates["followup_count"] = state.get("followup_count", 0) + 1
            else:
                decision = {"action": "next", "reason": "继续面试"}
                updates["followup_count"] = 0

        updates["decision"] = decision
        # 注: decision event 改由 ask/followup/closing 节点开头兜底推送
        # (resume 后首个 custom event 偶发丢失, 流式节点推送时 astream 已就绪)
        return updates

    # --------------------------------------------------------
    # 节点: followup (追问 + interrupt 等回答)
    # --------------------------------------------------------
    async def followup_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        decision = state.get("decision", {})
        # 兜底推送 decision 给前端
        if decision:
            writer({"type": "decision", "action": decision.get("action", "followup"),
                    "reason": decision.get("reason", "")})
        missed_topic = decision.get("followup_topic", "")

        related = retriever.get_question(
            topic=missed_topic, role=state["role_key"],
            exclude_ids=state.get("asked_ids", []), top_k=3,
        )
        klist = []
        for c in related[:3]:
            a = retriever.get_answer(c["id"])
            if a:
                klist.append(f"[{c.get('category', '')}] {a['standard_answer'][:200]}")
        knowledge_text = "\n---\n".join(klist) if klist else "无参考知识"

        ad = state.get("current_answer_data") or {}
        current_q_text = ad.get("question", "")[:100]
        records = state.get("records", [])
        last = records[-1] if records else {}

        chain_input = {
            "current_question": current_q_text,
            "candidate_answer": last.get("user_answer", "")[:600],
            "band": _band(last.get("score", 0)),
            "hit_points": "、".join(last.get("hit_points", [])) if last.get("hit_points") else "无",
            "missed_topic": missed_topic,
            "reference_knowledge": knowledge_text,
            "history": [],
        }
        await _stream_chain(writer, followup_chain, chain_input, "followup")

        human_answer = interrupt({"type": "await_answer"})
        return {"human_answer": human_answer, "is_followup_phase": True}

    # --------------------------------------------------------
    # 节点: closing (收尾 + interview_ended)
    # --------------------------------------------------------
    async def closing_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        # 兜底推送 decision (end) 给前端
        _decision = state.get("decision")
        if _decision:
            writer({"type": "decision", "action": "end", "reason": _decision.get("reason", "")})
        records = state.get("records", [])
        topics = [f"- {r.get('question', '')[:40]}" for r in records
                  if not r.get("is_followup") and r.get("question")]
        covered = "\n".join(topics) if topics else "（无话题记录）"
        last = records[-1] if records else {}

        chain_input = {
            "role_title": state["role_info"]["title"],
            "total_count": state.get("total_count", 5),
            "covered_topics": covered,
            "last_question": last.get("question", "")[:120],
            "last_band": _band(last.get("score", 0)),
            "last_hit": "、".join(last.get("hit_points", [])) if last.get("hit_points") else "无",
            "last_missed": "、".join(last.get("missed_points", [])) if last.get("missed_points") else "无",
        }
        await _stream_chain(writer, closing_chain, chain_input, "closing")
        writer({"type": "interview_ended", "content": "面试已完成", "can_report": True})
        # 暂停等待用户点击"生成报告" (兼容前端 report 消息), resume 后走 summary
        interrupt({"type": "await_report"})
        return {}

    # --------------------------------------------------------
    # 节点: summary (结构化统计 + AI 分析流式 + 保存报告)
    # --------------------------------------------------------
    async def summary_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        all_records = state.get("records", [])
        main_records = [r for r in all_records if not r.get("is_followup")] or all_records
        if not main_records:
            writer({"type": "stream_start", "stream_type": "report"})
            writer({"type": "stream_chunk", "content": "无面试记录。"})
            writer({"type": "stream_end", "stream_type": "report", "full_text": "无面试记录。"})
            return {}

        avg = sum(r["score"] for r in main_records) / len(main_records)
        lines = [
            "# AI 面试综合评价报告", "",
            f"- **岗位**: {state['role_info']['title']}",
            f"- **难度**: {state['difficulty_label']}",
            f"- **主题数量**: {len(main_records)}",
            f"- **平均分**: {avg:.1f} / 10",
            f"- **简历**: {'是' if state.get('resume_context') else '否'}",
            f"- **面试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "- **引擎**: LangGraph", "", "---", "", "## 逐题详情", "",
            "| 轮次 | 题目 | 得分 | 准确性 | 完整性 | 深度 | 清晰度 | 反馈 |",
            "|------|------|------|--------|--------|------|--------|------|",
        ]
        for i, r in enumerate(main_records):
            bd = r.get("score_breakdown", {})
            lines.append(
                f"| {i+1} | {r['question'][:50]}... | {r['score']}/{r['max_score']} "
                f"| {bd.get('accuracy', '-')} | {bd.get('completeness', '-')} | {bd.get('depth', '-')} "
                f"| {bd.get('clarity', '-')} | {r.get('feedback', '')[:50]}... |"
            )
        structured = "\n".join(lines)

        strengths = [r for r in main_records if r["score"] >= 7]
        weaknesses = [r for r in main_records if r["score"] < 5]
        score_details = []
        for i, r in enumerate(main_records):
            bd = r.get("score_breakdown", {})
            score_details.append(
                f"第{i+1}题: {r['question'][:80]}\n  得分: {r['score']}/{r['max_score']}"
                f" (准确性={bd.get('accuracy', '?')} 完整性={bd.get('completeness', '?')}"
                f" 深度={bd.get('depth', '?')} 清晰度={bd.get('clarity', '?')})\n"
                f"  命中: {', '.join(r['hit_points'][:3]) if r['hit_points'] else '无'}\n"
                f"  遗漏: {', '.join(r['missed_points'][:3]) if r['missed_points'] else '无'}\n"
                f"  点评: {r.get('feedback', '')[:100]}"
            )
        ai_input = {
            "role_title": state["role_info"]["title"],
            "difficulty_label": state["difficulty_label"],
            "avg_score": avg, "total_questions": len(main_records),
            "high_score_count": len(strengths), "low_score_count": len(weaknesses),
            "score_details": "\n\n".join(score_details),
        }

        ai_header = "## AI 综合评价 (LangGraph)\n\n"
        writer({"type": "stream_start", "stream_type": "report"})
        writer({"type": "stream_chunk", "content": structured + "\n\n" + ai_header})
        ai_text = ""
        try:
            async for chunk in summary_chain.astream(ai_input):
                ai_text += chunk
                writer({"type": "stream_chunk", "content": chunk})
        except Exception as e:
            level = "通过" if avg >= 7 else ("待定" if avg >= 5 else "不通过")
            ai_text = (
                f"**总体评价**: 候选人平均得分 {avg:.1f}/10, "
                f"{'表现优秀' if avg >= 7 else '表现一般' if avg >= 5 else '需要加强'}。\n\n"
                f"**面试结论**: {level}\n\n(AI 分析生成失败: {e})"
            )
            writer({"type": "stream_chunk", "content": ai_text})
        footer = (
            "\n\n---\n\n## 每道题完整记录\n"
            f"详见: {os.path.basename(state.get('md_path', '')) or 'interview_records.md'}"
        )
        writer({"type": "stream_chunk", "content": footer})
        full_report = structured + "\n\n" + ai_header + ai_text + footer
        writer({"type": "stream_end", "stream_type": "report", "full_text": full_report})

        # 保存报告 (时间戳命名 md + 雷达数据 json, 避免并发覆盖)
        ts = time.strftime("%Y%m%d_%H%M%S")
        role_tag = state.get("role_key", "interview")
        report_id = f"interview_report_{ts}_{role_tag}"
        report_path = ""
        try:
            rp = os.path.join(config.REPORTS_DIR, f"{report_id}.md")
            with open(rp, "w", encoding="utf-8") as f:
                f.write(full_report)
            report_path = rp
            logger.info("面试报告已保存: %s", rp)
        except Exception as e:
            logger.warning("保存面试报告失败: %s", e)

        # 保存雷达/维度数据 json (供 GET /api/reports/{id}/radar, 阶段2 报告维度)
        try:
            import json as _json
            # 四维均值
            dim_sum = {"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0}
            for r in main_records:
                bd = r.get("score_breakdown", {})
                for k in dim_sum:
                    dim_sum[k] += bd.get(k, 0)
            n = len(main_records) or 1
            dimensions = {k: round(v / n, 1) for k, v in dim_sum.items()}
            # 分类均值
            cat_map = {}
            for r in main_records:
                c = r.get("category", "未分类")
                cat_map.setdefault(c, []).append(r["score"])
            categories = [{"category": c, "avg_score": round(sum(s) / len(s), 1),
                            "count": len(s)} for c, s in cat_map.items()]
            # 逐题
            questions = [{"round": i + 1, "question": r["question"][:60],
                          "score": r["score"], "max_score": r.get("max_score", 10),
                          "category": r.get("category", "")} for i, r in enumerate(main_records)]
            radar = {
                "report_id": report_id, "role_key": state.get("role_key", ""),
                "role_title": state["role_info"]["title"],
                "difficulty_label": state["difficulty_label"],
                "avg_score": round(avg, 1), "total_questions": len(main_records),
                "timestamp": ts, "dimensions": dimensions, "categories": categories,
                "questions": questions,
                "strengths": [r["question"][:40] for r in strengths],
                "weaknesses": [r["question"][:40] for r in weaknesses],
            }
            jp = os.path.join(config.REPORTS_DIR, f"{report_id}.json")
            with open(jp, "w", encoding="utf-8") as f:
                _json.dump(radar, f, ensure_ascii=False, indent=2)
            logger.info("雷达数据已保存: %s", jp)
        except Exception as e:
            logger.warning("保存雷达数据失败: %s", e)
        return {"report_path": report_path}

    # --------------------------------------------------------
    # 条件边路由
    # --------------------------------------------------------
    def decide_router(state: InterviewState) -> str:
        action = state.get("decision", {}).get("action", "next")
        if action == "followup":
            return "followup"
        if action == "end":
            return "closing"
        return "ask"

    # --------------------------------------------------------
    # 构图
    # --------------------------------------------------------
    g = StateGraph(InterviewState)
    g.add_node("configure", configure_node)
    g.add_node("opening", opening_node)
    g.add_node("ask", ask_node)
    g.add_node("receive_answer", receive_answer_node)
    g.add_node("score", score_node)
    g.add_node("decide", decide_node)
    g.add_node("followup", followup_node)
    g.add_node("closing", closing_node)
    g.add_node("summary", summary_node)

    g.add_edge(START, "configure")
    g.add_edge("configure", "opening")
    g.add_edge("opening", "ask")
    g.add_edge("ask", "receive_answer")
    g.add_edge("receive_answer", "score")
    g.add_edge("score", "decide")
    g.add_conditional_edges(
        "decide", decide_router,
        {"followup": "followup", "ask": "ask", "closing": "closing"},
    )
    g.add_edge("followup", "receive_answer")
    g.add_edge("closing", "summary")
    g.add_edge("summary", END)

    return g
