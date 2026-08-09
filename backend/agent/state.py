"""
agent/state.py — LangGraph 面试流程共享状态

集中原 InterviewEngine 散落在实例变量上的全部状态,
作为 StateGraph 各节点之间传递的单一数据载体。
断线后可由 checkpointer 按 thread_id 恢复 (替代"状态全靠实例变量, 断线即丢")。
"""
from typing import TypedDict, List, Dict, Optional


class InterviewState(TypedDict, total=False):
    # ---- 配置 (configure 节点写入) ----
    thread_id: str
    role_key: str
    role_info: Dict
    difficulty: int
    difficulty_label: str
    total_count: int
    resume_context: str
    resume_skills: List[str]
    candidate_name: str

    # ---- 面试进度 ----
    asked_ids: List[str]
    asked_categories: List[str]
    main_question_count: int
    followup_count: int
    is_followup_phase: bool
    first_topic_hint: str

    # ---- 当前轮 ----
    current_question: Dict
    current_answer_data: Dict
    last_user_answer: str
    human_answer: Optional[str]      # interrupt() 恢复通道, 承载用户回答

    # ---- 评分记录 ----
    records: List[Dict]

    # ---- 决策 ----
    decision: Dict

    # ---- 文件 ----
    md_path: str
    report_path: str

    # ---- 调试 ----
    phase: str
