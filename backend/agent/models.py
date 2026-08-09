"""
agent/models.py — Pydantic 数据模型

定义结构化输出模型, 用于 LangChain PydanticOutputParser
确保 LLM 评分结果可被可靠解析。
"""
from typing import List
from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """评分维度细分 (四维度)"""
    accuracy: int = Field(
        description="准确性评分 1-10, 是否正确回答核心概念"
    )
    completeness: int = Field(
        description="完整性评分 1-10, 是否覆盖所有关键点"
    )
    depth: int = Field(
        description="深度评分 1-10, 是否有深入分析和独到见解"
    )
    clarity: int = Field(
        description="表达清晰度评分 1-10, 逻辑是否清晰、表达是否规范"
    )


class ScoreResult(BaseModel):
    """LLM 评分结果 — 通过 PydanticOutputParser 强制结构化输出"""
    score: int = Field(description="总分 1-10 的整数")
    max_score: int = Field(default=10, description="满分分值")
    score_breakdown: ScoreBreakdown = Field(description="四维度评分细分")
    hit_points: List[str] = Field(
        default_factory=list, description="候选人命中的得分点列表"
    )
    missed_points: List[str] = Field(
        default_factory=list, description="候选人遗漏的得分点列表"
    )
    feedback: str = Field(description="简短的中文点评, 50-100字")
    is_correct: bool = Field(description="回答是否基本正确")

    def to_record(self) -> dict:
        """转换为评分记录字典 (兼容原有数据格式)"""
        return {
            "score": self.score,
            "max_score": self.max_score,
            "score_breakdown": {
                "accuracy": self.score_breakdown.accuracy,
                "completeness": self.score_breakdown.completeness,
                "depth": self.score_breakdown.depth,
                "clarity": self.score_breakdown.clarity,
            },
            "hit_points": self.hit_points,
            "missed_points": self.missed_points,
            "feedback": self.feedback,
            "is_correct": self.is_correct,
        }

