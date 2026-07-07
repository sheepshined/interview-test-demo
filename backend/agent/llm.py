"""
agent/llm.py — LangChain LLM 和 Embeddings 工厂

使用 LangChain 的 ChatOpenAI (兼容智谱/DeepSeek/OpenAI 等 OpenAI 兼容接口)
和 HuggingFaceEmbeddings (本地 BGE 模型) 作为底层组件。
"""
from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

import config


def get_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatOpenAI:
    """创建 LangChain ChatOpenAI 实例 (兼容智谱 GLM / DeepSeek / OpenAI)

    Args:
        temperature: 采样温度, 默认使用 config.LLM_TEMPERATURE
        max_tokens:  最大输出 token 数
        model:       模型名称, 默认使用 config.LLM_MODEL

    Returns:
        ChatOpenAI 实例, 可直接用于 LCEL Chain
    """
    api_key = config.LLM_API_KEY
    if not api_key:
        raise ValueError(
            "未配置 LLM API Key, 请检查 .env 文件中的 ZHIPUAI_API_KEY"
        )

    return ChatOpenAI(
        model=model or config.LLM_MODEL,
        api_key=api_key,
        base_url=config.LLM_BASE_URL,
        temperature=temperature if temperature is not None else config.LLM_TEMPERATURE,
        max_tokens=max_tokens or config.LLM_MAX_TOKENS,
        max_retries=config.LLM_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """创建 HuggingFaceEmbeddings 实例 (本地 BGE 模型)

    使用 lru_cache 确保全局只加载一次模型。

    Returns:
        HuggingFaceEmbeddings 实例
    """
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_PATH)
