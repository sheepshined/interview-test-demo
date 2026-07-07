"""
agent/tools.py — LangChain Tool 定义

使用 @tool 装饰器将检索器操作封装为 LangChain Tool,
可被 LangChain Agent 调用, 也可被 InterviewEngine 直接调用。

Tools:
  1. search_question      — 搜索面试题 (混合检索 BM25+向量)
  2. get_standard_answer  — 获取标准答案和得分点
  3. get_categories       — 获取岗位分类列表
  4. get_random_question  — 随机抽题
"""
import json
from typing import Optional

from langchain_core.tools import tool

from retrieval.retriever import HybridRetriever


def create_tools(retriever: HybridRetriever):
    """创建绑定到特定检索器的 Tool 集合

    Args:
        retriever: HybridRetriever 实例

    Returns:
        List[Tool] — LangChain Tool 列表
    """

    @tool
    def search_question(
        topic: str,
        role: str,
        difficulty: Optional[int] = None,
        exclude_ids: Optional[list] = None,
        top_k: int = 5,
    ) -> str:
        """搜索面试题。使用 BM25 + 向量混合检索,返回匹配的候选题目列表(JSON)。

        Args:
            topic:       搜索关键词 (如 "Python 异步编程")
            role:        岗位标识 (如 "python_dev")
            difficulty:  难度过滤 1=初级 2=中级 3=高级 (可选)
            exclude_ids: 要排除的题目ID列表 (可选)
            top_k:       返回题目数量, 默认5
        """
        results = retriever.get_question(
            topic=topic,
            role=role,
            difficulty=difficulty,
            exclude_ids=exclude_ids or [],
            top_k=top_k,
        )
        return json.dumps(results, ensure_ascii=False, default=str)

    @tool
    def get_standard_answer(question_id: str) -> str:
        """根据题目ID获取标准答案和得分点(JSON)。

        Args:
            question_id: 题目ID (如 "py_001")
        """
        result = retriever.get_answer(question_id)
        if result:
            return json.dumps(result, ensure_ascii=False, default=str)
        return json.dumps({"error": f"未找到题目: {question_id}"}, ensure_ascii=False)

    @tool
    def get_categories(role: str) -> str:
        """获取指定岗位的所有知识分类列表(JSON)。

        Args:
            role: 岗位标识 (如 "python_dev")
        """
        cats = retriever.get_categories(role=role)
        return json.dumps(cats, ensure_ascii=False)

    @tool
    def get_random_question(
        role: str,
        difficulty: Optional[int] = None,
        exclude_ids: Optional[list] = None,
    ) -> str:
        """随机抽取一道面试题(JSON)。当语义检索无结果时使用。

        Args:
            role:        岗位标识
            difficulty:  难度过滤 (可选)
            exclude_ids: 要排除的题目ID列表 (可选)
        """
        result = retriever.get_random_question(
            role=role,
            difficulty=difficulty,
            exclude_ids=exclude_ids or [],
        )
        if result:
            return json.dumps(result, ensure_ascii=False, default=str)
        return json.dumps({"error": "题库已无更多题目"}, ensure_ascii=False)

    return [search_question, get_standard_answer, get_categories, get_random_question]
