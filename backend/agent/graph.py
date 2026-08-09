"""LangGraph 面试流程。

稳定版将“准备/流式输出”和“等待人类输入”拆成独立节点。LangGraph 在
``Command(resume=...)`` 时会从包含 ``interrupt()`` 的节点开头重跑，因此
等待节点在 interrupt 之前不能执行随机选题、LLM 调用或文件写入。

主流程::

    configure -> opening -> prepare_question -> emit_question -> wait_answer
      -> score_initial -> [prepare_followup -> emit_followup -> wait_followup
      -> score_combined] -> finalize_question -> ... -> closing -> wait_report
      -> summary -> END
"""
import json
import logging
import os
import random
import re
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

import config
from agent.chains import (
    build_closing_chain,
    build_followup_chain,
    build_opening_chain,
    build_question_chain,
    build_scoring_chain,
    build_summary_chain,
    get_format_instructions,
)
from agent.llm import get_fast_llm, get_strong_llm
from agent.models import ScoreResult
from agent.state import InterviewState
if TYPE_CHECKING:
    from retrieval.retriever import HybridRetriever

logger = logging.getLogger(__name__)


async def _stream_chain(
    writer,
    chain,
    chain_input: dict,
    stream_type: str,
    metadata: Optional[dict] = None,
) -> str:
    """流式调用 LCEL chain，并发送统一的 start/chunk/end 事件。"""
    metadata = metadata or {}
    writer({"type": "stream_start", "stream_type": stream_type, **metadata})
    full_text = ""
    try:
        async for chunk in chain.astream(chain_input):
            full_text += chunk
            writer({"type": "stream_chunk", "content": chunk, **metadata})
    except Exception as exc:
        logger.warning("%s 流式生成失败: %s", stream_type, exc)
        writer({"type": "error", "content": f"{stream_type}生成失败: {exc}"})
    writer({
        "type": "stream_end",
        "stream_type": stream_type,
        "full_text": full_text,
        **metadata,
    })
    return full_text


def _band(score: int) -> str:
    if score >= 8:
        return "优秀"
    if score >= 5:
        return "合格"
    return "待加强"


def _get_filtered_resume_skills(state: InterviewState) -> List[str]:
    skills = state.get("resume_skills", [])
    if not skills:
        return []
    role_tags = [tag.lower() for tag in state["role_info"].get("tags", [])]
    if not role_tags:
        return skills
    return [
        skill for skill in skills
        if any(skill.lower() in tag or tag in skill.lower() for tag in role_tags)
    ]


def _select_topic_for_search(state: InterviewState) -> str:
    if state.get("main_question_count", 0) == 0 and state.get("first_topic_hint"):
        return state["first_topic_hint"]
    relevant = _get_filtered_resume_skills(state)
    if relevant:
        return " ".join(random.sample(relevant, min(len(relevant), random.randint(2, 3))))
    tags = state["role_info"].get("tags", [])
    if tags:
        return " ".join(random.sample(tags, min(len(tags), random.randint(2, 3))))
    return state["role_info"].get("title", "")


def _select_preferred_category(
    state: InterviewState,
    retriever: Any,
) -> Optional[str]:
    all_categories = retriever.get_categories(role=state["role_key"])
    if not all_categories:
        return None
    asked = state.get("asked_categories", [])
    unasked = [category for category in all_categories if category not in asked]
    if unasked:
        return random.choice(unasked)
    for category in reversed(asked):
        if category in all_categories:
            return category
    return random.choice(all_categories)


def _build_prev_context(state: InterviewState) -> str:
    records = state.get("records", [])
    if not records:
        return "（这是第一题，无需衔接上一题）"
    last = records[-1]
    hit_points = last.get("hit_points", [])
    missed_points = last.get("missed_points", [])
    answer_summary = (
        "、".join(hit_points[:3])
        if hit_points else last.get("user_answer", "")[:80]
    )
    direction = missed_points[0] if missed_points else last.get("question", "")[:40]
    return (
        "## 上一题回顾（用于生成承上启下）\n"
        f"上一题: {last.get('question', '')[:120]}\n"
        f"候选人回答要点: {answer_summary}\n"
        f"表现档位: {_band(last.get('score', 0))}\n"
        f"可衔接方向: {direction}"
    )


def _append_to_md(state: InterviewState, record: Dict) -> None:
    """主问题完成后写一次记录；追问作为同一题的补充内容保存。"""
    md_path = state.get("md_path")
    if not md_path:
        return
    try:
        with open(md_path, "a", encoding="utf-8") as handle:
            index = len(state.get("records", []))
            breakdown = record.get("score_breakdown", {})
            followup = ""
            if record.get("followup_question"):
                followup = (
                    f"\n**追问**: {record['followup_question']}\n\n"
                    f"**补充回答**: {record.get('followup_answer', '')}\n\n"
                    f"**初始得分**: {record.get('initial_score', 0)}/10\n\n"
                )
            handle.write(
                f"## 第{index}题\n\n"
                f"**题目 ID**: {record.get('question_id', '')}\n\n"
                f"**题目**: {record.get('question', '')}\n\n"
                f"**你的回答**:\n\n{record.get('user_answer', '')}\n\n"
                f"{followup}"
                f"**标准答案**: {record.get('standard_answer', '暂无')[:500]}\n\n"
                f"**最终得分**: {record.get('score', 0)}/{record.get('max_score', 10)}\n\n"
                f"**评分维度**: 准确性={breakdown.get('accuracy', '?')} "
                f"完整性={breakdown.get('completeness', '?')} "
                f"深度={breakdown.get('depth', '?')} "
                f"清晰度={breakdown.get('clarity', '?')}\n\n---\n\n"
            )
    except Exception as exc:
        logger.warning("追加面试记录失败: %s", exc)


def _normalise_resume(value, default_action: str) -> dict:
    """兼容旧字符串 resume 值，同时优先使用结构化 action/content。"""
    if isinstance(value, dict):
        return {
            "action": str(value.get("action") or default_action),
            "content": str(value.get("content") or "").strip(),
        }
    return {"action": default_action, "content": str(value or "").strip()}


def build_interview_graph(
    retriever: Any,
    fast_llm: BaseChatModel = None,
    strong_llm: BaseChatModel = None,
) -> StateGraph:
    """构建未编译的、恢复安全的面试 StateGraph。"""
    fast_llm = fast_llm or get_fast_llm()
    strong_llm = strong_llm or get_strong_llm()
    question_chain = build_question_chain(fast_llm)
    scoring_chain = build_scoring_chain(fast_llm)
    followup_chain = build_followup_chain(fast_llm)
    opening_chain = build_opening_chain(fast_llm)
    closing_chain = build_closing_chain(fast_llm)
    summary_chain = build_summary_chain(strong_llm)

    def score_candidate(state: InterviewState, candidate_answer: str) -> Dict:
        question = state.get("current_question") or {}
        answer_data = state.get("current_answer_data")
        if answer_data is None and question:
            answer_data = retriever.get_answer(question.get("id", ""))

        if not answer_data:
            return {
                "score": 0,
                "max_score": 10,
                "score_breakdown": {
                    "accuracy": 0,
                    "completeness": 0,
                    "depth": 0,
                    "clarity": 0,
                },
                "hit_points": [],
                "missed_points": [],
                "feedback": "未找到标准答案，无法评分",
                "is_correct": False,
            }

        scoring_points = answer_data.get("scoring_points", [])
        scoring_points_text = (
            "\n".join(f"  - {point}" for point in scoring_points)
            if scoring_points else "无明确得分点"
        )
        try:
            score_result: ScoreResult = scoring_chain.invoke({
                "question": answer_data["question"],
                "standard_answer": answer_data["standard_answer"],
                "scoring_points": scoring_points_text,
                "candidate_answer": candidate_answer,
                "format_instructions": get_format_instructions(),
            })
            return score_result.to_record()
        except Exception as exc:
            logger.warning("题目 %s 评分失败: %s", question.get("id", ""), exc)
            return {
                "score": 0,
                "max_score": 10,
                "score_breakdown": {
                    "accuracy": 0,
                    "completeness": 0,
                    "depth": 0,
                    "clarity": 0,
                },
                "hit_points": [],
                "missed_points": scoring_points,
                "feedback": f"评分失败: {exc}",
                "is_correct": False,
            }

    def configure_node(state: InterviewState) -> dict:
        role_key = state.get("role_key", "general_hr")
        if role_key not in config.ROLES:
            role_key = "general_hr"
        role_info = config.ROLES[role_key]
        difficulty = state.get("difficulty", 2)
        if difficulty not in config.DIFFICULTY_LABELS:
            difficulty = 2
        total_count = max(1, min(int(state.get("total_count", 5)), 20))
        resume_context = state.get("resume_context", "")
        name_match = re.search(
            r"姓名[:：]\s*([^\s,，。;；\n、]{2,8})",
            resume_context,
        )
        candidate_name = name_match.group(1).strip() if name_match else ""

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        record_dir = config.INTERVIEW_RECORDS_DIR
        os.makedirs(record_dir, exist_ok=True)
        md_path = os.path.join(
            record_dir,
            f"interview_records_{timestamp}_{uuid.uuid4().hex[:6]}.md",
        )
        try:
            with open(md_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "# AI 模拟面试记录\n\n"
                    f"- **岗位**: {role_info['title']}\n"
                    f"- **难度**: {config.DIFFICULTY_LABELS[difficulty]}\n"
                    f"- **题量**: {total_count}\n"
                    f"- **简历**: {'是' if resume_context else '否'}\n"
                    f"- **时间**: {timestamp}\n"
                    "- **引擎**: LangGraph stable\n\n---\n\n"
                )
        except OSError as exc:
            logger.warning("初始化记录文件失败: %s", exc)

        return {
            "role_key": role_key,
            "role_info": role_info,
            "difficulty": difficulty,
            "difficulty_label": config.DIFFICULTY_LABELS[difficulty],
            "total_count": total_count,
            "candidate_name": candidate_name,
            "md_path": md_path,
            "asked_ids": [],
            "asked_categories": [],
            "records": [],
            "main_question_count": 0,
            "question_id": "",
            "first_topic_hint": "",
            "phase": "configured",
            "force_end": False,
            "report_id": "",
        }

    async def opening_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        relevant = _get_filtered_resume_skills(state)
        if relevant:
            first_hint = random.choice(relevant)
        else:
            tags = state["role_info"].get("tags", [])
            first_hint = random.choice(tags) if tags else state["role_info"]["title"]
        await _stream_chain(
            writer,
            opening_chain,
            {
                "role_title": state["role_info"]["title"],
                "difficulty_label": state["difficulty_label"],
                "total_count": state["total_count"],
                "candidate_name": state.get("candidate_name") or "你",
                "first_direction": first_hint,
            },
            "opening",
        )
        return {"first_topic_hint": first_hint, "phase": "preparing_question"}

    def prepare_question_node(state: InterviewState) -> dict:
        topic = _select_topic_for_search(state)
        preferred_category = _select_preferred_category(state, retriever)
        asked_ids = state.get("asked_ids", [])
        candidates = retriever.get_question(
            topic=topic,
            role=state["role_key"],
            difficulty=state.get("difficulty"),
            exclude_ids=asked_ids,
            top_k=5,
        )
        if not candidates:
            candidates = retriever.get_question(
                topic=topic,
                role=state["role_key"],
                exclude_ids=asked_ids,
                top_k=5,
            )
        if not candidates:
            random_question = retriever.get_random_question(
                role=state["role_key"],
                exclude_ids=asked_ids,
            )
            candidates = [random_question] if random_question else []
        if not candidates:
            return {
                "current_question": {},
                "decision": {"action": "end", "reason": "题库已无可用题目"},
                "phase": "question_unavailable",
                "force_end": True,
            }

        chosen = candidates[0]
        if preferred_category:
            chosen = next(
                (
                    candidate for candidate in candidates
                    if candidate.get("category") == preferred_category
                ),
                chosen,
            )
        new_categories = list(state.get("asked_categories", []))
        if chosen.get("category"):
            new_categories.append(chosen["category"])
        answer_data = retriever.get_answer(chosen["id"])
        return {
            "question_id": chosen["id"],
            "current_question": chosen,
            "current_answer_data": answer_data or {},
            "question_index": state.get("main_question_count", 0) + 1,
            "asked_ids": asked_ids + [chosen["id"]],
            "asked_categories": new_categories,
            "rendered_question": "",
            "main_answer": "",
            "followup_question": "",
            "followup_answer": "",
            "followup_context": {},
            "initial_result": {},
            "final_result": {},
            "initial_score": 0,
            "final_score": 0,
            "input_action": "",
            "force_end": False,
            "phase": "question_prepared",
        }

    def prepare_question_router(state: InterviewState) -> str:
        return "emit_question" if state.get("current_question") else "closing"

    async def emit_question_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        question = state["current_question"]
        resume_context = state.get("resume_context", "")
        if resume_context:
            relevant = _get_filtered_resume_skills(state)
            skill_hint = relevant[0] if relevant else "相关经验"
            resume_section = (
                f"## 候选人简历摘要\n{resume_context[:500]}\n"
                "## 提问要求\n"
                f"可以自然结合候选人简历中提到的“{skill_hint}”引出题目，"
                "但核心技术内容必须来自下面的题库题目。"
            )
        else:
            resume_section = "（无简历信息，直接出题）"
        metadata = {
            "question_id": question["id"],
            "question_index": state["question_index"],
            "total_count": state["total_count"],
        }
        rendered = await _stream_chain(
            writer,
            question_chain,
            {
                "role_title": state["role_info"]["title"],
                "difficulty_label": state["difficulty_label"],
                "question_index": state["question_index"],
                "total_count": state["total_count"],
                "question_text": question["question"],
                "resume_section": resume_section,
                "prev_context": _build_prev_context(state),
                "history": [],
            },
            "question",
            metadata,
        )
        return {"rendered_question": rendered, "phase": "await_answer"}

    def wait_answer_node(state: InterviewState) -> dict:
        value = interrupt({
            "type": "await_answer",
            "question_id": state.get("current_question", {}).get("id", ""),
            "question_index": state.get("question_index", 0),
        })
        payload = _normalise_resume(value, "answer")
        return {
            "input_action": payload["action"],
            "main_answer": payload["content"],
            "human_answer": payload["content"],
            "phase": "answer_received",
            "force_end": payload["action"] == "end",
        }

    def wait_answer_router(state: InterviewState) -> str:
        return "closing" if state.get("input_action") == "end" else "score_initial"

    def score_initial_node(state: InterviewState) -> dict:
        result = score_candidate(state, state.get("main_answer", ""))
        score = result.get("score", 0)
        return {
            "initial_result": result,
            "final_result": result,
            "initial_score": score,
            "final_score": score,
            "phase": "initial_scored",
        }

    def initial_score_router(state: InterviewState) -> str:
        if state.get("initial_result", {}).get("score", 0) < 5:
            return "prepare_followup"
        return "finalize_question"

    def prepare_followup_node(state: InterviewState) -> dict:
        initial = state.get("initial_result", {})
        missed_points = initial.get("missed_points", [])
        question = state.get("current_question", {})
        missed_topic = (
            missed_points[0]
            if missed_points else question.get("question", "")[:80]
        )
        related = retriever.get_question(
            topic=missed_topic,
            role=state["role_key"],
            exclude_ids=state.get("asked_ids", []),
            top_k=3,
        )
        knowledge = []
        for candidate in related[:3]:
            answer_data = retriever.get_answer(candidate["id"])
            if answer_data:
                knowledge.append(
                    f"[{candidate.get('category', '')}] "
                    f"{answer_data['standard_answer'][:200]}"
                )
        context = {
            "current_question": question.get("question", "")[:120],
            "candidate_answer": state.get("main_answer", "")[:600],
            "band": _band(initial.get("score", 0)),
            "hit_points": "、".join(initial.get("hit_points", [])) or "无",
            "missed_topic": missed_topic,
            "reference_knowledge": "\n---\n".join(knowledge) or "无参考知识",
            "history": [],
        }
        return {"followup_context": context, "phase": "followup_prepared"}

    async def emit_followup_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        metadata = {
            "question_id": state.get("current_question", {}).get("id", ""),
            "question_index": state.get("question_index", 0),
            "total_count": state.get("total_count", 0),
        }
        followup_text = await _stream_chain(
            writer,
            followup_chain,
            state["followup_context"],
            "followup",
            metadata,
        )
        writer({
            "type": "decision",
            "action": "followup",
            "reason": "初始得分低于 5 分，进行一次针对性追问",
            **metadata,
        })
        return {"followup_question": followup_text, "phase": "await_followup"}

    def wait_followup_node(state: InterviewState) -> dict:
        value = interrupt({
            "type": "await_followup",
            "question_id": state.get("current_question", {}).get("id", ""),
            "question_index": state.get("question_index", 0),
        })
        payload = _normalise_resume(value, "answer")
        return {
            "input_action": payload["action"],
            "followup_answer": payload["content"],
            "human_answer": payload["content"],
            "phase": "followup_received",
            "force_end": payload["action"] == "end",
        }

    def wait_followup_router(state: InterviewState) -> str:
        if state.get("input_action") == "end":
            return "finalize_question"
        return "score_combined"

    def score_combined_node(state: InterviewState) -> dict:
        combined_answer = (
            f"原始回答：{state.get('main_answer', '')}\n\n"
            f"针对追问“{state.get('followup_question', '')}”的补充回答："
            f"{state.get('followup_answer', '')}"
        )
        result = score_candidate(state, combined_answer)
        return {
            "final_result": result,
            "final_score": result.get("score", 0),
            "combined_answer": combined_answer,
            "phase": "combined_scored",
        }

    def finalize_question_node(state: InterviewState) -> dict:
        question = state.get("current_question", {})
        answer_data = state.get("current_answer_data") or {}
        result = state.get("final_result") or state.get("initial_result") or {}
        initial = state.get("initial_result") or result
        completed = state.get("main_question_count", 0) + 1
        record = {
            "question_id": question.get("id", ""),
            "question": answer_data.get("question") or question.get("question", ""),
            "rendered_question": state.get("rendered_question", ""),
            "user_answer": state.get("main_answer", ""),
            "followup_question": state.get("followup_question", ""),
            "followup_answer": state.get("followup_answer", ""),
            "combined_answer": state.get("combined_answer", ""),
            "initial_score": initial.get("score", 0),
            "standard_answer": answer_data.get("standard_answer", ""),
            **result,
            "category": answer_data.get("category") or question.get("category", ""),
            "difficulty": answer_data.get("difficulty") or question.get("difficulty", 2),
            "is_followup": False,
            "round": completed,
        }
        records = list(state.get("records", [])) + [record]
        next_state = {**state, "records": records}
        _append_to_md(next_state, record)
        should_end = state.get("force_end", False) or completed >= state.get("total_count", 5)
        decision = {
            "action": "end" if should_end else "next",
            "reason": (
                "用户提前结束"
                if state.get("force_end", False)
                else (
                    f"已完成 {completed} 道题"
                    if should_end else "继续下一题"
                )
            ),
        }
        return {
            "records": records,
            "main_question_count": completed,
            "decision": decision,
            "phase": "question_finalized",
        }

    def finalize_router(state: InterviewState) -> str:
        if state.get("decision", {}).get("action") == "end":
            return "closing"
        return "prepare_question"

    async def closing_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        records = state.get("records", [])
        topics = [
            f"- {record.get('question', '')[:40]}"
            for record in records if record.get("question")
        ]
        last = records[-1] if records else {}
        await _stream_chain(
            writer,
            closing_chain,
            {
                "role_title": state["role_info"]["title"],
                "total_count": state.get("main_question_count", 0),
                "covered_topics": "\n".join(topics) or "（无已完成题目）",
                "last_question": last.get("question", "")[:120],
                "last_band": _band(last.get("score", 0)),
                "last_hit": "、".join(last.get("hit_points", [])) or "无",
                "last_missed": "、".join(last.get("missed_points", [])) or "无",
            },
            "closing",
        )
        writer({
            "type": "interview_ended",
            "content": "面试已完成",
            "can_report": True,
            "answered_count": state.get("main_question_count", 0),
            "total_count": state.get("total_count", 0),
        })
        return {"phase": "await_report"}

    def wait_report_node(state: InterviewState) -> dict:
        value = interrupt({"type": "await_report"})
        payload = _normalise_resume(value, "report")
        return {"input_action": payload["action"], "phase": "report_requested"}

    async def summary_node(state: InterviewState) -> dict:
        writer = get_stream_writer()
        records = list(state.get("records", []))
        average = (
            sum(record.get("score", 0) for record in records) / len(records)
            if records else 0.0
        )
        lines = [
            "# AI 面试综合评价报告",
            "",
            f"- **岗位**: {state['role_info']['title']}",
            f"- **难度**: {state['difficulty_label']}",
            f"- **主题数量**: {len(records)}",
            f"- **平均分**: {average:.1f} / 10",
            f"- **简历**: {'是' if state.get('resume_context') else '否'}",
            f"- **面试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "- **引擎**: LangGraph stable",
            "",
            "---",
            "",
        ]
        if records:
            lines.extend([
                "## 逐题详情",
                "",
                "| 轮次 | 题目 ID | 题目 | 初始分 | 最终分 | 准确性 | 完整性 | 深度 | 清晰度 |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|",
            ])
            for index, record in enumerate(records, 1):
                breakdown = record.get("score_breakdown", {})
                lines.append(
                    f"| {index} | {record.get('question_id', '')} | "
                    f"{record.get('question', '')[:45]} | "
                    f"{record.get('initial_score', record.get('score', 0))} | "
                    f"{record.get('score', 0)} | "
                    f"{breakdown.get('accuracy', '-')} | "
                    f"{breakdown.get('completeness', '-')} | "
                    f"{breakdown.get('depth', '-')} | "
                    f"{breakdown.get('clarity', '-')} |"
                )
        else:
            lines.extend(["## 面试记录", "", "本次面试在完成题目之前结束，暂无可评分记录。"])
        structured = "\n".join(lines)

        strengths = [record for record in records if record.get("score", 0) >= 7]
        weaknesses = [record for record in records if record.get("score", 0) < 5]
        ai_text = ""
        ai_header = "## AI 综合评价 (LangGraph)\n\n"
        writer({"type": "stream_start", "stream_type": "report"})
        writer({"type": "stream_chunk", "content": structured + "\n\n"})
        if records:
            writer({"type": "stream_chunk", "content": ai_header})
            score_details = []
            for index, record in enumerate(records, 1):
                breakdown = record.get("score_breakdown", {})
                score_details.append(
                    f"第{index}题 ({record.get('question_id', '')}): "
                    f"{record.get('question', '')[:80]}\n"
                    f"  初始/最终得分: {record.get('initial_score', record.get('score', 0))}/"
                    f"{record.get('score', 0)}\n"
                    f"  四维: 准确性={breakdown.get('accuracy', '?')} "
                    f"完整性={breakdown.get('completeness', '?')} "
                    f"深度={breakdown.get('depth', '?')} "
                    f"清晰度={breakdown.get('clarity', '?')}\n"
                    f"  点评: {record.get('feedback', '')[:120]}"
                )
            try:
                async for chunk in summary_chain.astream({
                    "role_title": state["role_info"]["title"],
                    "difficulty_label": state["difficulty_label"],
                    "avg_score": average,
                    "total_questions": len(records),
                    "high_score_count": len(strengths),
                    "low_score_count": len(weaknesses),
                    "score_details": "\n\n".join(score_details),
                }):
                    ai_text += chunk
                    writer({"type": "stream_chunk", "content": chunk})
            except Exception as exc:
                level = "通过" if average >= 7 else ("待定" if average >= 5 else "不通过")
                ai_text = (
                    f"**总体评价**: 候选人平均得分 {average:.1f}/10。\n\n"
                    f"**面试结论**: {level}\n\n"
                    f"（AI 分析生成失败: {exc}）"
                )
                writer({"type": "stream_chunk", "content": ai_text})

        footer = (
            "\n\n---\n\n## 每道题完整记录\n"
            f"详见: {os.path.basename(state.get('md_path', '')) or 'interview_records.md'}"
        )
        writer({"type": "stream_chunk", "content": footer})
        full_report = structured + ("\n\n" + ai_header + ai_text if records else "") + footer

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        thread_tag = re.sub(r"[^a-zA-Z0-9_-]", "", state.get("thread_id", ""))[-8:]
        unique_tag = thread_tag or uuid.uuid4().hex[:8]
        report_id = (
            f"interview_report_{timestamp}_{unique_tag}_"
            f"{state.get('role_key', 'interview')}"
        )
        report_path = os.path.join(config.REPORTS_DIR, f"{report_id}.md")
        radar_path = os.path.join(config.REPORTS_DIR, f"{report_id}.json")
        try:
            os.makedirs(config.REPORTS_DIR, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(full_report)

            dimension_sums = {
                "accuracy": 0,
                "completeness": 0,
                "depth": 0,
                "clarity": 0,
            }
            for record in records:
                breakdown = record.get("score_breakdown", {})
                for key in dimension_sums:
                    dimension_sums[key] += breakdown.get(key, 0)
            count = len(records) or 1
            dimensions = {
                key: round(value / count, 1)
                for key, value in dimension_sums.items()
            }
            category_scores: Dict[str, List[int]] = {}
            for record in records:
                category_scores.setdefault(
                    record.get("category") or "未分类",
                    [],
                ).append(record.get("score", 0))
            radar = {
                "report_id": report_id,
                "thread_id": state.get("thread_id", ""),
                "role_key": state.get("role_key", ""),
                "role_title": state["role_info"]["title"],
                "difficulty_label": state["difficulty_label"],
                "avg_score": round(average, 1),
                "total_questions": len(records),
                "timestamp": timestamp,
                "dimensions": dimensions,
                "categories": [
                    {
                        "category": category,
                        "avg_score": round(sum(scores) / len(scores), 1),
                        "count": len(scores),
                    }
                    for category, scores in category_scores.items()
                ],
                "questions": [
                    {
                        "round": index,
                        "question_id": record.get("question_id", ""),
                        "question": record.get("question", "")[:60],
                        "initial_score": record.get("initial_score", record.get("score", 0)),
                        "score": record.get("score", 0),
                        "max_score": record.get("max_score", 10),
                        "category": record.get("category", ""),
                        "had_followup": bool(record.get("followup_question")),
                    }
                    for index, record in enumerate(records, 1)
                ],
                "strengths": [record.get("question", "")[:40] for record in strengths],
                "weaknesses": [record.get("question", "")[:40] for record in weaknesses],
            }
            with open(radar_path, "w", encoding="utf-8") as handle:
                json.dump(radar, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.exception("保存面试报告失败: %s", exc)
            writer({"type": "error", "content": "报告保存失败，请稍后重试"})
            writer({"type": "stream_end", "stream_type": "report", "full_text": full_report})
            return {"phase": "report_failed", "report_path": "", "report_id": ""}

        writer({
            "type": "stream_end",
            "stream_type": "report",
            "full_text": full_report,
            "report_id": report_id,
        })
        writer({
            "type": "report_ready",
            "report_id": report_id,
            "content": full_report,
        })
        return {
            "phase": "completed",
            "report_path": report_path,
            "report_id": report_id,
        }

    graph = StateGraph(InterviewState)
    graph.add_node("configure", configure_node)
    graph.add_node("opening", opening_node)
    graph.add_node("prepare_question", prepare_question_node)
    graph.add_node("emit_question", emit_question_node)
    graph.add_node("wait_answer", wait_answer_node)
    graph.add_node("score_initial", score_initial_node)
    graph.add_node("prepare_followup", prepare_followup_node)
    graph.add_node("emit_followup", emit_followup_node)
    graph.add_node("wait_followup", wait_followup_node)
    graph.add_node("score_combined", score_combined_node)
    graph.add_node("finalize_question", finalize_question_node)
    graph.add_node("closing", closing_node)
    graph.add_node("wait_report", wait_report_node)
    graph.add_node("summary", summary_node)

    graph.add_edge(START, "configure")
    graph.add_edge("configure", "opening")
    graph.add_edge("opening", "prepare_question")
    graph.add_conditional_edges(
        "prepare_question",
        prepare_question_router,
        {"emit_question": "emit_question", "closing": "closing"},
    )
    graph.add_edge("emit_question", "wait_answer")
    graph.add_conditional_edges(
        "wait_answer",
        wait_answer_router,
        {"score_initial": "score_initial", "closing": "closing"},
    )
    graph.add_conditional_edges(
        "score_initial",
        initial_score_router,
        {
            "prepare_followup": "prepare_followup",
            "finalize_question": "finalize_question",
        },
    )
    graph.add_edge("prepare_followup", "emit_followup")
    graph.add_edge("emit_followup", "wait_followup")
    graph.add_conditional_edges(
        "wait_followup",
        wait_followup_router,
        {
            "score_combined": "score_combined",
            "finalize_question": "finalize_question",
        },
    )
    graph.add_edge("score_combined", "finalize_question")
    graph.add_conditional_edges(
        "finalize_question",
        finalize_router,
        {"prepare_question": "prepare_question", "closing": "closing"},
    )
    graph.add_edge("closing", "wait_report")
    graph.add_edge("wait_report", "summary")
    graph.add_edge("summary", END)
    return graph
