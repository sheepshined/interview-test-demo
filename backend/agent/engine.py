"""
agent/engine.py — AI 面试官引擎 (LangChain 版)

核心编排器: 整合 LangChain Chains + Memory + Tools + Retriever
实现完整的面试流程: 出题 → 接收回答 → 评分 → 决策 → 追问/下一题 → 总结报告

状态机:
  CONFIG → ASKING → RETRIEVED → SCORED → DECIDED → (FOLLOWUP | NEXT | SUMMARY)
"""
import os
import time
import random
from typing import List, Dict, Optional
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage

import config
from agent.llm import get_llm
from agent.memory import InterviewMemory
from agent.chains import (
    build_question_chain,
    build_scoring_chain,
    build_followup_chain,
    build_summary_chain,
    get_format_instructions,
)
from agent.models import ScoreResult
from agent.tools import create_tools
from retrieval.retriever import HybridRetriever


class Phase(Enum):
    CONFIG = "config"
    ASKING = "asking"
    RETRIEVED = "retrieved"
    SCORED = "scored"
    DECIDED = "decided"
    FOLLOWUP = "followup"
    SUMMARY = "summary"


class InterviewEngine:
    """AI 面试官引擎 — LangChain 架构版

    使用 LangChain 组件:
      - LCEL Chains:  出题/评分/追问/总结
      - Memory:       InterviewMemory (ChatMessageHistory + 摘要压缩)
      - Tools:        LangChain @tool 检索工具
      - Retriever:    HybridRetriever (BM25 + 向量 + RRF)
    """

    def __init__(self, retriever: HybridRetriever, llm: BaseChatModel = None):
        self.retriever = retriever
        self.llm = llm or get_llm()
        self.phase = Phase.CONFIG

        # LangChain 组件
        self.memory = InterviewMemory(llm=self.llm)
        self.tools = create_tools(retriever)

        # LCEL Chains
        self._question_chain = build_question_chain(self.llm)
        self._scoring_chain = build_scoring_chain(self.llm)
        self._followup_chain = build_followup_chain(self.llm)
        self._summary_chain = build_summary_chain(self.llm)

        # 面试配置
        self.role_key = ""
        self.role_info = {}
        self.difficulty = 2
        self.difficulty_label = "Intermediate"
        self.total_count = 5

        # 简历
        self.resume_context = ""
        self.has_resume = False
        self.resume_skills: List[str] = []

        # 面试状态
        self.asked_ids: List[str] = []
        self.asked_categories: List[str] = []
        self.records: List[Dict] = []
        self.main_question_count = 0
        self.current_question: Optional[Dict] = None
        self.current_answer_data: Optional[Dict] = None
        self.last_user_answer = ""
        self.followup_count = 0
        self.is_followup_phase = False

        # 记录文件
        self._md_path: Optional[str] = None

    # ============================================================
    # Phase 0: 配置
    # ============================================================

    def configure(
        self,
        role_key: str,
        total_count: int = 5,
        difficulty: int = 2,
        resume_context: str = "",
        resume_skills: List[str] = None,
    ) -> str:
        """配置面试参数"""
        self.role_key = role_key if role_key in config.ROLES else "general_hr"
        self.role_info = config.ROLES[self.role_key]
        self.total_count = total_count
        self.difficulty = difficulty
        self.difficulty_label = {1: "Junior", 2: "Intermediate", 3: "Senior"}.get(
            difficulty, "Intermediate"
        )
        self.resume_context = resume_context
        self.has_resume = bool(resume_context)
        self.resume_skills = resume_skills or []

        # 重置状态
        self.phase = Phase.ASKING
        self.asked_ids = []
        self.asked_categories = []
        self.records = []
        self.main_question_count = 0
        self.followup_count = 0
        self.is_followup_phase = False
        self.memory.clear()

        # 初始化 .md 记录文件
        d = os.path.dirname(os.path.abspath(__file__))
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._md_path = os.path.join(d, f"interview_records_{ts}.md")
        with open(self._md_path, "w", encoding="utf-8") as f:
            f.write(
                f"# AI 模拟面试记录\n\n"
                f"- **岗位**: {self.role_info['title']}\n"
                f"- **难度**: {self.difficulty_label}\n"
                f"- **题量**: {self.total_count}\n"
                f"- **简历**: {'是' if self.has_resume else '否'}\n"
                f"- **时间**: {ts}\n"
                f"- **引擎**: LangChain LCEL\n\n---\n\n"
            )

        ri = f"\n  简历: {len(resume_context)} 字" if self.has_resume else ""
        cats = self.retriever.get_categories(role=self.role_key)
        return (
            f"[OK] 配置完成{ri}\n"
            f"  岗位: {self.role_info['title']}  难度: {self.difficulty_label}  "
            f"题量: {self.total_count}\n"
            f"  知识分类: {', '.join(cats[:10])}\n"
            f"  引擎: LangChain (Chains + Memory + Tools + Hybrid Retriever)"
        )

    # ============================================================
    # 简历技能过滤 (防止跨岗位题目泄漏)
    # ============================================================

    def _get_filtered_resume_skills(self) -> List[str]:
        """过滤简历技能: 只保留与当前岗位 tag 相关的

        LLM 提取的技能已经比较精准, 这里只做轻量过滤:
        技能与岗位 tag 有子串关联即保留, 防止跨岗位出题。
        """
        if not self.resume_skills:
            return []
        role_tags_lower = [t.lower() for t in self.role_info.get("tags", [])]
        if not role_tags_lower:
            return self.resume_skills

        def _is_related(skill: str) -> bool:
            s = skill.lower()
            return any(s in tag or tag in s for tag in role_tags_lower)

        return [skill for skill in self.resume_skills if _is_related(skill)]

    def _select_topic_for_search(self) -> str:
        """选择搜索话题, 引入随机性避免重复"""
        relevant_skills = self._get_filtered_resume_skills()
        if relevant_skills:
            sample_size = min(len(relevant_skills), random.randint(2, 3))
            return " ".join(random.sample(relevant_skills, sample_size))

        tags = self.role_info.get("tags", [])
        if tags:
            sample_size = min(len(tags), random.randint(2, 3))
            return " ".join(random.sample(tags, sample_size))

        return self.role_info.get("title", "")

    def _select_preferred_category(self) -> Optional[str]:
        """选择下一个优先分类, 实现分类轮换"""
        all_cats = self.retriever.get_categories(role=self.role_key)
        if not all_cats:
            return None

        unasked = [c for c in all_cats if c not in self.asked_categories]
        if unasked:
            return random.choice(unasked)

        for cat in reversed(self.asked_categories):
            if cat in all_cats:
                return cat
        return random.choice(all_cats)

    # ============================================================
    # Phase 1: 出题 (使用 LCEL question_chain, 支持流式)
    # ============================================================

    def _prepare_question(self) -> Optional[Dict]:
        """出题前的准备工作: 检索 + 选题 + 构建prompt参数

        Returns:
            LCEL chain 输入字典, 失败返回 None
        """
        self.phase = Phase.ASKING
        self.followup_count = 0
        self.is_followup_phase = False

        # 选择搜索话题
        topic = self._select_topic_for_search()
        preferred_category = self._select_preferred_category()

        # 混合检索候选题目 (BM25 + 向量 + RRF)
        candidates = self.retriever.get_question(
            topic=topic,
            role=self.role_key,
            difficulty=self.difficulty,
            exclude_ids=self.asked_ids,
            top_k=5,
        )

        # 放宽难度限制重试
        if not candidates:
            candidates = self.retriever.get_question(
                topic=topic,
                role=self.role_key,
                exclude_ids=self.asked_ids,
                top_k=5,
            )

        # 随机抽取
        if not candidates:
            q = self.retriever.get_random_question(
                role=self.role_key, exclude_ids=self.asked_ids
            )
            if not q:
                return None
            candidates = [q]

        # 优先选择未问过的分类
        chosen = candidates[0]
        if preferred_category:
            for c in candidates:
                if c.get("category") == preferred_category:
                    chosen = c
                    break

        self.current_question = chosen
        self.asked_ids.append(chosen["id"])
        if chosen.get("category"):
            self.asked_categories.append(chosen["category"])
        self.main_question_count += 1

        # 构建简历上下文
        resume_section = ""
        if self.has_resume and self.resume_context:
            relevant_skills = self._get_filtered_resume_skills()
            skill_hint = relevant_skills[0] if relevant_skills else "相关经验"
            resume_section = (
                f"## 候选人简历摘要\n{self.resume_context[:500]}\n"
                f"## 提问要求\n"
                f"可以自然地结合候选人简历中提到的'{skill_hint}'来引出题目,"
                f"但不要每次都用相同的句式开头。"
                f"题目的核心技术内容必须来自下面的题库题目。"
            )
        else:
            resume_section = "(无简历信息, 直接出题)"

        return {
            "role_title": self.role_info["title"],
            "difficulty_label": self.difficulty_label,
            "question_index": self.main_question_count,
            "total_count": self.total_count,
            "question_text": chosen["question"],
            "resume_section": resume_section,
            "history": self.memory.get_history_for_chain(),
        }

    def generate_question_stream(self):
        """流式生成面试题 (generator, 逐块 yield 文本)

        用法:
            for chunk in engine.generate_question_stream():
                print(chunk, end="", flush=True)
        """
        input_dict = self._prepare_question()
        if input_dict is None:
            yield "[System] 题库已无更多题目。输入 quit 结束。"
            return

        full_text = ""
        try:
            for chunk in self._question_chain.stream(input_dict):
                full_text += chunk
                yield chunk
            self.memory.add_ai_message(f"[Q{self.main_question_count}] {full_text.strip()}")
        except Exception as e:
            yield f"\n[System] 出题失败: {e}"

    def generate_question(self) -> str:
        """非流式生成面试题 (内部调用流式方法并拼接)"""
        return "".join(self.generate_question_stream())

    # ============================================================
    # Phase 2-3: 接收回答 + 检索标准答案
    # ============================================================

    def receive_answer(self, user_answer: str):
        """接收候选人回答, 检索标准答案"""
        self.last_user_answer = user_answer
        self.memory.add_user_message(user_answer)

        if self.current_question:
            self.current_answer_data = self.retriever.get_answer(
                self.current_question["id"]
            )
        else:
            self.current_answer_data = None

        # 触发上下文压缩
        self.memory.maybe_compress()
        self.phase = Phase.RETRIEVED

    # ============================================================
    # Phase 4: 评分 (使用 LCEL scoring_chain + PydanticOutputParser)
    # ============================================================

    def score_answer(self) -> Dict:
        """对候选人回答进行评分"""
        self.phase = Phase.SCORED

        if not self.current_answer_data:
            record = {
                "question_id": self.current_question["id"] if self.current_question else "",
                "question": self.current_question["question"] if self.current_question else "",
                "user_answer": self.last_user_answer,
                "standard_answer": "",
                "score": 0,
                "max_score": 10,
                "score_breakdown": {"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0},
                "hit_points": [],
                "missed_points": [],
                "feedback": "未找到标准答案, 无法评分",
                "is_correct": False,
                "category": self.current_question.get("category", "") if self.current_question else "",
                "difficulty": self.current_question.get("difficulty", 2) if self.current_question else 2,
                "is_followup": self.is_followup_phase,
                "round": len(self.records) + 1,
            }
        else:
            ad = self.current_answer_data
            scoring_points_str = (
                "\n".join(f"  - {p}" for p in ad["scoring_points"])
                if ad["scoring_points"]
                else "无明确得分点"
            )

            try:
                # 调用 LCEL scoring_chain (返回 ScoreResult Pydantic 对象)
                score_result: ScoreResult = self._scoring_chain.invoke({
                    "question": ad["question"],
                    "standard_answer": ad["standard_answer"],
                    "scoring_points": scoring_points_str,
                    "candidate_answer": self.last_user_answer,
                    "format_instructions": get_format_instructions(),
                })

                record = {
                    "question_id": self.current_question["id"] if self.current_question else "",
                    "question": ad["question"],
                    "user_answer": self.last_user_answer,
                    "standard_answer": ad["standard_answer"],
                    **score_result.to_record(),
                    "category": ad.get("category", ""),
                    "difficulty": ad.get("difficulty", 2),
                    "is_followup": self.is_followup_phase,
                    "round": len(self.records) + 1,
                }

            except Exception as e:
                # Chain 调用失败时的兜底
                record = {
                    "question_id": self.current_question["id"] if self.current_question else "",
                    "question": ad["question"],
                    "user_answer": self.last_user_answer,
                    "standard_answer": ad["standard_answer"],
                    "score": 0,
                    "max_score": 10,
                    "score_breakdown": {"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0},
                    "hit_points": [],
                    "missed_points": ad["scoring_points"] if ad["scoring_points"] else [],
                    "feedback": f"评分 Chain 调用失败: {e}",
                    "is_correct": False,
                    "category": ad.get("category", ""),
                    "difficulty": ad.get("difficulty", 2),
                    "is_followup": self.is_followup_phase,
                    "round": len(self.records) + 1,
                }

        self.records.append(record)
        self._append_to_md(record)
        return record

    def _append_to_md(self, record: Dict):
        """每条回答立即追加到 .md 文件"""
        if not self._md_path:
            return
        try:
            with open(self._md_path, "a", encoding="utf-8") as f:
                i = len(self.records)
                tag = " [追问]" if record.get("is_followup") else ""
                bd = record.get("score_breakdown", {})
                f.write(
                    f"## 第{i}题{tag}\n\n"
                    f"**题目**: {record['question']}\n\n"
                    f"**你的回答**:\n\n{record['user_answer']}\n\n"
                    f"**标准答案**: {record.get('standard_answer', '暂无')[:500]}\n\n"
                    f"**得分**: {record['score']}/{record['max_score']}\n\n"
                    f"**评分维度**: 准确性={bd.get('accuracy', '?')} "
                    f"完整性={bd.get('completeness', '?')} "
                    f"深度={bd.get('depth', '?')} "
                    f"清晰度={bd.get('clarity', '?')}\n\n"
                    f"**命中得分点**: {', '.join(record['hit_points']) if record['hit_points'] else '无'}\n\n"
                    f"**遗漏得分点**: {', '.join(record['missed_points']) if record['missed_points'] else '无'}\n\n"
                    f"**AI点评**: {record.get('feedback', '')}\n\n---\n\n"
                )
        except Exception:
            pass

    # ============================================================
    # Phase 5: 决策
    # ============================================================

    def decide(self) -> Dict:
        """决定下一步: 追问 / 下一题 / 结束"""
        self.phase = Phase.DECIDED
        if not self.records:
            return {"action": "next", "reason": "无记录"}

        last_score = self.records[-1]["score"]

        if self.main_question_count >= self.total_count:
            return {"action": "end", "reason": f"已完成 {self.total_count} 道题"}

        if self.followup_count == 0 and last_score < 5:
            missed = self.records[-1].get("missed_points", [])
            topic = missed[0] if missed else self.records[-1].get("question", "")[:50]
            self.followup_count += 1
            return {
                "action": "followup",
                "reason": f"得分 {last_score}/10, 需要追问",
                "followup_topic": topic,
            }

        self.followup_count = 0
        return {"action": "next", "reason": "继续面试"}

    # ============================================================
    # Phase 5b: 追问 (使用 LCEL followup_chain, 支持流式)
    # ============================================================

    def _prepare_followup(self, missed_topic: str) -> Optional[Dict]:
        """追问前的准备工作: 检索 + 构建prompt参数"""
        self.is_followup_phase = True

        # 检索相关知识 (强制 role 过滤)
        related = self.retriever.get_question(
            topic=missed_topic,
            role=self.role_key,
            exclude_ids=self.asked_ids,
            top_k=3,
        )

        # 构建参考知识
        klist = []
        for c in related[:3]:
            a = self.retriever.get_answer(c["id"])
            if a:
                klist.append(f"[{c.get('category', '')}] {a['standard_answer'][:200]}")

        knowledge_text = "\n---\n".join(klist) if klist else "无参考知识"
        current_q = self.current_answer_data["question"] if self.current_answer_data else ""

        return {
            "current_question": current_q[:100],
            "missed_topic": missed_topic,
            "reference_knowledge": knowledge_text,
            "history": self.memory.get_history_for_chain(),
        }

    def generate_followup_stream(self, missed_topic: str):
        """流式生成追问 (generator, 逐块 yield 文本)"""
        input_dict = self._prepare_followup(missed_topic)
        if input_dict is None:
            yield "[System] 追问生成失败"
            return

        full_text = ""
        try:
            for chunk in self._followup_chain.stream(input_dict):
                full_text += chunk
                yield chunk
            self.memory.add_ai_message(f"[追问] {full_text.strip()}")
        except Exception as e:
            yield f"\n[System] 追问生成失败: {e}"

    def generate_followup(self, missed_topic: str) -> str:
        """非流式生成追问"""
        return "".join(self.generate_followup_stream(missed_topic))

    # ============================================================
    # Phase 6: 总结报告 (使用 LCEL summary_chain, 支持流式)
    # ============================================================

    def _prepare_summary(self) -> Optional[tuple]:
        """总结报告准备工作: 统计数据 + 构建结构化部分 + AI分析prompt

        Returns:
            (structured_text, ai_input_dict, main_records, avg, strengths, weaknesses)
            失败返回 None
        """
        self.phase = Phase.SUMMARY
        if not self.records:
            return None

        # 只统计主题 (不含追问)
        main_records = [r for r in self.records if not r.get("is_followup")]
        if not main_records:
            main_records = self.records

        avg = sum(r["score"] for r in main_records) / len(main_records)

        # ---- 结构化部分 ----
        lines = [
            "# AI 面试综合评价报告",
            "",
            f"- **岗位**: {self.role_info['title']}",
            f"- **难度**: {self.difficulty_label}",
            f"- **主题数量**: {len(main_records)}",
            f"- **平均分**: {avg:.1f} / 10",
            f"- **简历**: {'是' if self.has_resume else '否'}",
            f"- **面试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **引擎**: LangChain LCEL",
            "",
            "---",
            "",
            "## 逐题详情",
            "",
            "| 轮次 | 题目 | 得分 | 准确性 | 完整性 | 深度 | 清晰度 | 反馈 |",
            "|------|------|------|--------|--------|------|--------|------|",
        ]

        for i, r in enumerate(main_records):
            bd = r.get("score_breakdown", {})
            lines.append(
                f"| {i+1} | {r['question'][:50]}... | {r['score']}/{r['max_score']} "
                f"| {bd.get('accuracy', '-')} | {bd.get('completeness', '-')} "
                f"| {bd.get('depth', '-')} | {bd.get('clarity', '-')} "
                f"| {r.get('feedback', '')[:50]}... |"
            )

        lines += ["", "---", "", "## 各题完整记录", ""]

        for i, r in enumerate(main_records):
            tag = " [追问]" if r.get("is_followup") else ""
            bd = r.get("score_breakdown", {})
            lines += [
                f"### 第{i+1}题{tag}: {r['question'][:120]}",
                "",
                f"**你的回答**:",
                f"  {r['user_answer'][:400]}",
                "",
                f"**标准答案**:",
                f"  {r.get('standard_answer', '暂无')[:400]}",
                "",
                f"**得分**: {r['score']}/{r['max_score']}",
                f"  - 准确性: {bd.get('accuracy', '?')}",
                f"  - 完整性: {bd.get('completeness', '?')}",
                f"  - 深度: {bd.get('depth', '?')}",
                f"  - 清晰度: {bd.get('clarity', '?')}",
                f"**命中**: {', '.join(r['hit_points']) if r['hit_points'] else '无'}",
                f"**遗漏**: {', '.join(r['missed_points']) if r['missed_points'] else '无'}",
                f"**点评**: {r.get('feedback', '')}",
                "",
                "---",
                "",
            ]

        # ---- 统计分析 ----
        strengths = [r for r in main_records if r["score"] >= 7]
        weaknesses = [r for r in main_records if r["score"] < 5]
        all_missed = []
        all_hit = []
        for r in main_records:
            all_missed.extend(r.get("missed_points", []))
            all_hit.extend(r.get("hit_points", []))

        lines += [
            "## 数据统计",
            "",
            f"- 高分题 (>=7分): {len(strengths)}/{len(main_records)}",
            f"- 低分题 (<5分): {len(weaknesses)}/{len(main_records)}",
            f"- 总命中得分点: {len(all_hit)}",
            f"- 总遗漏得分点: {len(all_missed)}",
            f"- 平均得分率: {avg/10*100:.0f}%",
            "",
        ]

        structured_text = "\n".join(lines)

        # ---- AI 定性分析 prompt ----
        score_details = []
        for i, r in enumerate(main_records):
            bd = r.get("score_breakdown", {})
            score_details.append(
                f"第{i+1}题: {r['question'][:80]}\n"
                f"  得分: {r['score']}/{r['max_score']}"
                f" (准确性={bd.get('accuracy', '?')} 完整性={bd.get('completeness', '?')}"
                f" 深度={bd.get('depth', '?')} 清晰度={bd.get('clarity', '?')})\n"
                f"  命中: {', '.join(r['hit_points'][:3]) if r['hit_points'] else '无'}\n"
                f"  遗漏: {', '.join(r['missed_points'][:3]) if r['missed_points'] else '无'}\n"
                f"  点评: {r.get('feedback', '')[:100]}"
            )

        ai_input = {
            "role_title": self.role_info["title"],
            "difficulty_label": self.difficulty_label,
            "avg_score": avg,
            "total_questions": len(main_records),
            "high_score_count": len(strengths),
            "low_score_count": len(weaknesses),
            "score_details": "\n\n".join(score_details),
        }

        return (structured_text, ai_input, main_records, avg, strengths, weaknesses)

    def generate_summary_stream(self):
        """流式生成综合评价报告 (generator)

        先 yield 结构化数据部分 (一次性), 再逐块 yield AI 分析部分。
        最后 yield 报告尾部。
        """
        prep = self._prepare_summary()
        if prep is None:
            yield "无面试记录。"
            return

        structured_text, ai_input, main_records, avg, strengths, weaknesses = prep

        # 1. 先输出结构化部分
        yield structured_text + "\n\n"

        # 2. AI 分析部分流式输出
        ai_header = "## AI 综合评价 (LangChain LCEL)\n\n"
        yield ai_header

        ai_text = ""
        try:
            for chunk in self._summary_chain.stream(ai_input):
                ai_text += chunk
                yield chunk
        except Exception as e:
            level = "通过" if avg >= 7 else ("待定" if avg >= 5 else "不通过")
            ai_text = (
                f"**总体评价**: 候选人平均得分 {avg:.1f}/10, "
                f"{'表现优秀' if avg >= 7 else '表现一般' if avg >= 5 else '需要加强'}。\n\n"
                f"**面试结论**: {level}\n\n"
                f"(AI 分析生成失败: {e})"
            )
            yield ai_text

        # 3. 报告尾部
        footer = (
            "\n\n---\n\n"
            "## 每道题完整记录\n"
            f"详见: {os.path.basename(self._md_path) if self._md_path else 'interview_records.md'}"
        )
        yield footer

        # 4. 保存完整报告到文件
        full_report = structured_text + "\n\n" + ai_header + ai_text + footer
        try:
            rp = os.path.join(config.REPORTS_DIR, "interview_report.md")
            with open(rp, "w", encoding="utf-8") as f:
                f.write(full_report)
        except Exception:
            pass

    def generate_summary(self) -> str:
        """非流式生成总结报告"""
        return "".join(self.generate_summary_stream())
