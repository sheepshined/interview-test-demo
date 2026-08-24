"""题库管理入口。

用法：
  python main.py build    # 从 Markdown 题库构建向量库
  python main.py rebuild  # 删除现有向量库后重新构建
"""
import os
import shutil
import sys

import config


def build_knowledge_base() -> None:
    """构建题库向量库。"""
    from retrieval.kb_builder import KnowledgeBaseBuilder

    success = KnowledgeBaseBuilder().build()
    if success:
        print("\n[完成] 题库已就绪，请启动 FastAPI 与 Vite 前端。")


def rebuild_knowledge_base() -> None:
    """删除现有向量库并重新构建。"""
    chroma_path = os.path.abspath(config.CHROMA_DB_PATH)
    if os.path.isdir(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"[清理] 已删除旧向量库: {chroma_path}")
    build_knowledge_base()


def main() -> None:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if command == "build":
        build_knowledge_base()
    elif command == "rebuild":
        rebuild_knowledge_base()
    else:
        print("AI 模拟面试官 — 题库管理")
        print("用法:")
        print("  python main.py build    # 构建题库")
        print("  python main.py rebuild  # 清空并重建题库")


if __name__ == "__main__":
    main()
