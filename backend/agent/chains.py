"""
agent/chains.py — LangChain LCEL Chain 定义

使用 LangChain Expression Language (LCEL) 构建 Chain:
  1. question_chain  — 出题 Chain
  2. scoring_chain   — 评分 Chain (PydanticOutputParser 结构化输出)
  3. followup_chain  — 追问 Chain
  4. summary_chain   — 总结报告 Chain (独立上下文)
  5. compress_chain  — 对话压缩 Chain

LCEL 优势:
  - 声明式组合 (prompt | llm | parser)
  - 原生支持流式输出、异步、重试
  - 可观测性 (LangSmith 追踪)
"""
import json
import re
from typing import Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnablePassthrough

from agent.prompts import (
    question_prompt,
    scorer_prompt,
    followup_prompt,
    summary_prompt,
)
from agent.models import ScoreResult


# ============================================================
# 自定义评分输出解析器 (带容错)
# ============================================================

class RobustScoreParser:
    """健壮的评分输出解析器

    策略:
      1. 尝试从 LLM 输出中提取 JSON 并解析为 ScoreResult
      2. 如果失败, 尝试从文本中提取分数
      3. 如果全部失败, 返回默认评分
    """

    def __init__(self):
        self._pydantic_parser_failed = False

    def parse(self, text: str) -> ScoreResult:
        """解析 LLM 输出为 ScoreResult"""
        if not text:
            return self._default_result("LLM 返回空内容")

        # Step 1: 剥离 markdown 代码块
        cleaned = text.strip()
        code_block = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
        if code_block:
            cleaned = code_block.group(1).strip()

        # Step 2: 尝试直接解析
        try:
            data = json.loads(cleaned)
            return self._dict_to_result(data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Step 3: 正则提取最外层花括号
        try:
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return self._dict_to_result(data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Step 4: 平衡花括号匹配
        json_str = self._balanced_json_extract(cleaned)
        if json_str:
            try:
                data = json.loads(json_str)
                return self._dict_to_result(data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Step 5: 从文本中提取分数
        fallback_score = self._extract_score_from_text(text)
        if fallback_score > 0:
            return ScoreResult(
                score=fallback_score,
                max_score=10,
                score_breakdown={
                    "accuracy": fallback_score,
                    "completeness": fallback_score,
                    "depth": max(fallback_score - 1, 1),
                    "clarity": fallback_score,
                },
                hit_points=[],
                missed_points=["评分解析异常, 无法提取详细得分点"],
                feedback=f"评分解析异常, 已尝试提取分数({fallback_score})。LLM原始输出: {text[:200]}",
                is_correct=fallback_score >= 5,
            )

        return self._default_result(f"无法解析 LLM 输出: {text[:200]}")

    @staticmethod
    def _dict_to_result(data: dict) -> ScoreResult:
        """将字典转换为 ScoreResult, 处理字段缺失"""
        breakdown_data = data.get("score_breakdown", {})
        if not isinstance(breakdown_data, dict):
            breakdown_data = {}

        score = data.get("score", 0)
        if not isinstance(score, (int, float)):
            score = 0

        return ScoreResult(
            score=int(score),
            max_score=data.get("max_score", 10),
            score_breakdown={
                "accuracy": int(breakdown_data.get("accuracy", score)),
                "completeness": int(breakdown_data.get("completeness", score)),
                "depth": int(breakdown_data.get("depth", score)),
                "clarity": int(breakdown_data.get("clarity", score)),
            },
            hit_points=data.get("hit_points", []) if isinstance(data.get("hit_points"), list) else [],
            missed_points=data.get("missed_points", []) if isinstance(data.get("missed_points"), list) else [],
            feedback=data.get("feedback", ""),
            is_correct=data.get("is_correct", score >= 5),
        )

    @staticmethod
    def _default_result(reason: str) -> ScoreResult:
        return ScoreResult(
            score=0,
            max_score=10,
            score_breakdown={"accuracy": 0, "completeness": 0, "depth": 0, "clarity": 0},
            hit_points=[],
            missed_points=[],
            feedback=f"评分解析失败: {reason}",
            is_correct=False,
        )

    @staticmethod
    def _balanced_json_extract(text: str) -> Optional[str]:
        """平衡花括号匹配"""
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    @staticmethod
    def _extract_score_from_text(text: str) -> int:
        """从文本中提取分数"""
        patterns = [
            r'"score"\s*:\s*(\d+)',
            r"score\s*[:：]\s*(\d+)",
            r"得分\s*[:：]\s*(\d+)",
            r"评分\s*[:：]\s*(\d+)",
            r"\b(\d+)\s*/\s*10\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score = int(match.group(1))
                if 1 <= score <= 10:
                    return score
        return 0


# ============================================================
# Chain 工厂函数
# ============================================================

def build_question_chain(llm: BaseChatModel):
    """构建出题 Chain

    Chain: question_prompt | llm | StrOutputParser

    输入参数:
        role_title, difficulty_label, question_index, total_count,
        question_text, resume_section, history
    """
    return question_prompt | llm | StrOutputParser()


def build_scoring_chain(llm: BaseChatModel):
    """构建评分 Chain

    Chain: scorer_prompt | llm | RobustScoreParser

    输入参数:
        question, standard_answer, scoring_points, candidate_answer,
        format_instructions
    """
    from langchain_core.output_parsers import PydanticOutputParser

    pydantic_parser = PydanticOutputParser(pydantic_object=ScoreResult)
    robust_parser = RobustScoreParser()

    # 使用自定义 RobustScoreParser 替代 PydanticOutputParser
    # 但保留 format_instructions 用于 prompt
    chain = scorer_prompt | llm | StrOutputParser()

    def parse_score(text: str) -> ScoreResult:
        return robust_parser.parse(text)

    # 组合: prompt | llm | str_parser | robust_parser
    return scorer_prompt | llm | StrOutputParser() | parse_score


def build_followup_chain(llm: BaseChatModel):
    """构建追问 Chain

    Chain: followup_prompt | llm | StrOutputParser

    输入参数:
        current_question, missed_topic, reference_knowledge, history
    """
    return followup_prompt | llm | StrOutputParser()


def build_summary_chain(llm: BaseChatModel):
    """构建总结报告 Chain (独立上下文, 不使用 history)

    Chain: summary_prompt | llm | StrOutputParser

    输入参数:
        role_title, difficulty_label, avg_score, total_questions,
        high_score_count, low_score_count, score_details
    """
    return summary_prompt | llm | StrOutputParser()


def get_format_instructions() -> str:
    """获取 PydanticOutputParser 的格式指令 (注入到 scorer_prompt)"""
    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ScoreResult)
    return parser.get_format_instructions()
