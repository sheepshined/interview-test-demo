import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

import config
from agent.graph import build_interview_graph


def score_json(score: int) -> str:
    return json.dumps({
        "score": score,
        "max_score": 10,
        "score_breakdown": {
            "accuracy": score,
            "completeness": score,
            "depth": score,
            "clarity": score,
        },
        "hit_points": ["正确要点"] if score >= 5 else [],
        "missed_points": [] if score >= 5 else ["关键遗漏点"],
        "feedback": f"测试评分 {score}",
        "is_correct": score >= 5,
    }, ensure_ascii=False)


class FakeRetriever:
    def __init__(self):
        self.questions = [
            {
                "id": "q_001",
                "question": "请解释 Python 事件循环。",
                "category": "基础",
                "difficulty": 2,
            },
            {
                "id": "q_002",
                "question": "请说明数据库索引的作用。",
                "category": "基础",
                "difficulty": 2,
            },
        ]

    def get_categories(self, role=None):
        return ["基础"]

    def get_question(
        self,
        topic,
        role=None,
        category=None,
        difficulty=None,
        exclude_ids=None,
        top_k=5,
    ):
        excluded = set(exclude_ids or [])
        return [q.copy() for q in self.questions if q["id"] not in excluded][:top_k]

    def get_random_question(self, role=None, difficulty=None, exclude_ids=None):
        candidates = self.get_question("", role, exclude_ids=exclude_ids, top_k=1)
        return candidates[0] if candidates else None

    def get_answer(self, question_id):
        question = next((q for q in self.questions if q["id"] == question_id), None)
        if not question:
            return None
        return {
            "id": question_id,
            "question": question["question"],
            "standard_answer": f"{question['question']}的标准答案",
            "scoring_points": ["关键遗漏点", "正确要点"],
            "category": question["category"],
            "difficulty": question["difficulty"],
            "max_score": 10,
        }


async def collect_events(graph, graph_input, cfg):
    custom = []
    async for mode, payload in graph.astream(
        graph_input,
        cfg,
        stream_mode=["custom", "values"],
    ):
        if mode == "custom":
            custom.append(payload)
    return custom


def stream_ends(events, stream_type):
    return [
        event for event in events
        if event.get("type") == "stream_end"
        and event.get("stream_type") == stream_type
    ]


@pytest.fixture
def output_dirs(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    records = tmp_path / "records"
    monkeypatch.setattr(config, "REPORTS_DIR", str(reports))
    monkeypatch.setattr(config, "INTERVIEW_RECORDS_DIR", str(records))
    return reports, records


@pytest.mark.asyncio
async def test_low_score_followup_is_combined_and_question_is_not_reemitted(output_dirs):
    fast_llm = FakeListChatModel(responses=[
        "欢迎参加面试。",
        "第一题：请解释 Python 事件循环。",
        score_json(2),
        "你遗漏了关键点，请补充事件循环如何调度任务？",
        score_json(8),
        "第二题：请说明数据库索引的作用。",
        score_json(7),
        "本次面试结束，感谢参加。",
    ])
    strong_llm = FakeListChatModel(responses=["## 总体评价\n表现稳定。"])
    graph = build_interview_graph(FakeRetriever(), fast_llm, strong_llm).compile(
        checkpointer=MemorySaver()
    )
    cfg = {"configurable": {"thread_id": "test-followup"}}

    first_events = await collect_events(graph, {
        "thread_id": "test-followup",
        "role_key": "python_dev",
        "difficulty": 2,
        "total_count": 2,
        "resume_context": "",
        "resume_skills": [],
    }, cfg)
    assert [e["question_id"] for e in stream_ends(first_events, "question")] == ["q_001"]
    assert graph.get_state(cfg).values["phase"] == "await_answer"

    followup_events = await collect_events(
        graph,
        Command(resume={"action": "answer", "content": "不知道"}),
        cfg,
    )
    assert stream_ends(followup_events, "question") == []
    assert len(stream_ends(followup_events, "followup")) == 1
    assert graph.get_state(cfg).values["phase"] == "await_followup"

    second_question_events = await collect_events(
        graph,
        Command(resume={"action": "answer", "content": "任务由事件循环调度"}),
        cfg,
    )
    assert [e["question_id"] for e in stream_ends(second_question_events, "question")] == ["q_002"]
    state = graph.get_state(cfg).values
    assert state["main_question_count"] == 1
    assert state["question_id"] == "q_002"
    assert state["initial_score"] == 0
    assert len(state["records"]) == 1
    assert state["records"][0]["question_id"] == "q_001"
    assert state["records"][0]["initial_score"] == 2
    assert state["records"][0]["score"] == 8
    assert state["records"][0]["followup_answer"] == "任务由事件循环调度"

    closing_events = await collect_events(
        graph,
        Command(resume={"action": "answer", "content": "索引加速数据查询"}),
        cfg,
    )
    assert stream_ends(closing_events, "question") == []
    assert len(stream_ends(closing_events, "closing")) == 1
    ended = [e for e in closing_events if e.get("type") == "interview_ended"]
    assert ended[0]["answered_count"] == 2
    assert graph.get_state(cfg).values["phase"] == "await_report"

    report_events = await collect_events(
        graph,
        Command(resume={"action": "report", "content": ""}),
        cfg,
    )
    ready = [e for e in report_events if e.get("type") == "report_ready"]
    assert len(ready) == 1
    report_id = ready[0]["report_id"]
    reports_dir, _ = output_dirs
    assert (reports_dir / f"{report_id}.md").is_file()
    radar = json.loads((reports_dir / f"{report_id}.json").read_text(encoding="utf-8"))
    assert [q["question_id"] for q in radar["questions"]] == ["q_001", "q_002"]
    assert radar["questions"][0]["initial_score"] == 2
    assert radar["questions"][0]["score"] == 8
    assert radar["questions"][0]["had_followup"] is True
    assert graph.get_state(cfg).values["phase"] == "completed"


@pytest.mark.asyncio
async def test_early_end_does_not_create_fake_answer_or_score(output_dirs):
    fast_llm = FakeListChatModel(responses=[
        "欢迎参加面试。",
        "第一题：请解释 Python 事件循环。",
        "面试已提前结束。",
    ])
    strong_llm = FakeListChatModel(responses=["不会被调用"])
    graph = build_interview_graph(FakeRetriever(), fast_llm, strong_llm).compile(
        checkpointer=MemorySaver()
    )
    cfg = {"configurable": {"thread_id": "test-early-end"}}
    await collect_events(graph, {
        "thread_id": "test-early-end",
        "role_key": "python_dev",
        "difficulty": 2,
        "total_count": 3,
        "resume_context": "",
        "resume_skills": [],
    }, cfg)

    end_events = await collect_events(
        graph,
        Command(resume={"action": "end", "content": ""}),
        cfg,
    )
    assert stream_ends(end_events, "question") == []
    assert len(stream_ends(end_events, "closing")) == 1
    state = graph.get_state(cfg).values
    assert state["phase"] == "await_report"
    assert state["main_question_count"] == 0
    assert state["records"] == []

    report_events = await collect_events(
        graph,
        Command(resume={"action": "report", "content": ""}),
        cfg,
    )
    assert len([e for e in report_events if e.get("type") == "report_ready"]) == 1
