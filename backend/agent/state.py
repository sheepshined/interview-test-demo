"""
agent/state.py — LangGraph 面试流程共享状态

集中原 InterviewEngine 散落在实例变量上的全部状态,
作为 StateGraph 各节点之间传递的单一数据载体。
运行期间由 checkpointer 按 thread_id 保存暂停点；服务重启持久化不在本轮范围。
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
    first_topic_hint: str
    question_index: int

    # ---- 当前轮 ----
    question_id: str
    current_question: Dict
    current_answer_data: Dict
    rendered_question: str
    main_answer: str
    followup_question: str
    followup_answer: str
    followup_context: Dict
    combined_answer: str
    human_answer: Optional[str]
    input_action: str
    force_end: bool

    # ---- 评分记录 ----
    records: List[Dict]
    initial_result: Dict
    final_result: Dict
    initial_score: int
    final_score: int

    # ---- 决策 ----
    decision: Dict

    # ---- 文件 ----
    md_path: str
    report_path: str
    report_id: str

    # ---- 调试 ----
    phase: str
