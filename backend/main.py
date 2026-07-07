"""
main.py — AI 模拟面试官 CLI 入口 (LangChain 版, 流式输出)

用法:
  python main.py build    # 离线建库 (题库更新后执行一次)
  python main.py chat     # 开始模拟面试 (流式输出)
  python main.py rebuild  # 清空旧库 + 重建
"""
import sys
import os

# 将项目根目录加入 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config


def stream_print(generator, prefix="", suffix="\n"):
    """流式打印 generator 的输出, 逐块输出到终端

    Args:
        generator: yield 字符串片段的 generator
        prefix:   开始前打印的前缀 (如 "[AI 面试官] ")
        suffix:   结束后打印的后缀 (默认换行)
    Returns:
        完整文本
    """
    full_text = ""
    if prefix:
        print(prefix, end="", flush=True)
    for chunk in generator:
        full_text += chunk
        sys.stdout.write(chunk)
        sys.stdout.flush()
    if suffix:
        print(suffix, end="")
    return full_text


def cmd_build():
    """离线建库"""
    from retrieval.kb_builder import KnowledgeBaseBuilder
    builder = KnowledgeBaseBuilder()
    success = builder.build()
    if success:
        print("\n[TIP] 下一步: python main.py chat")


def cmd_rebuild():
    """清空旧库并重建"""
    import shutil
    chroma_path = os.path.abspath(config.CHROMA_DB_PATH)
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"[CLEAN] 已删除旧向量库: {chroma_path}")
    cmd_build()


def cmd_chat():
    """启动模拟面试 (流式输出)"""
    from retrieval.retriever import HybridRetriever
    from agent.engine import InterviewEngine
    from resume.parser import parse_resume, build_resume_context

    # ---- 初始化检索器 ----
    print("[MODEL] 正在初始化混合检索器 (BM25 + 向量)...")
    retriever = HybridRetriever()

    # ---- 选择入口: 手动选岗位 / 传简历自动匹配 ----
    print("\n" + "=" * 50)
    print("AI 模拟面试官 (LangChain 版 · 流式输出)")
    print("=" * 50)
    print("\n请选择启动方式:")
    print("  1. 手动选择岗位")
    print("  2. 上传简历自动匹配岗位")
    print()

    resume_context = ""
    resume_skills = []
    role_key = None

    try:
        mode = input("请输入编号 (1-2, 默认1): ").strip()
    except (ValueError, EOFError):
        mode = "1"

    if mode == "2":
        # ---- 路径B: 传简历 → 自动匹配 ----
        print("\n请输入简历 PDF 路径:")
        pdf_path = input("> ").strip()

        if pdf_path:
            pdf_path = pdf_path.strip('"').strip("'")
            print(f"[解析] {pdf_path}")
            resume_data = parse_resume(pdf_path)
        else:
            resume_data = None
            print("[WARN] 未输入路径, 切换到手动选岗位模式")

        if resume_data:
            resume_context = build_resume_context(resume_data)
            resume_skills = resume_data.get("skills", [])

            # ---- 展示解析结果 ----
            print(f"[OK] 解析完成 ({resume_data['char_count']}字)")

            # 基本信息 (一行)
            info_parts = []
            if resume_data.get("name"):
                info_parts.append(resume_data["name"])
            if resume_data.get("phone"):
                info_parts.append(resume_data["phone"])
            if resume_data.get("email"):
                info_parts.append(resume_data["email"])
            if resume_data.get("location"):
                info_parts.append(resume_data["location"])
            if info_parts:
                print(f"  {' | '.join(info_parts)}")

            # 技能
            if resume_data.get("skills"):
                skills = resume_data["skills"]
                print(f"  技能({len(skills)}): {', '.join(skills)}")

            # 教育 (1行)
            if resume_data.get("education"):
                print(f"  教育: {resume_data['education']}")

            # 工作经历 (每段一行)
            if resume_data.get("experience"):
                print("  工作经历:")
                for el in resume_data["experience"].split('\n'):
                    if el.strip():
                        print(f"    {el.strip()}")

            # 项目经历 (每个一行)
            if resume_data.get("projects"):
                print("  项目经历:")
                for pl in resume_data["projects"].split('\n'):
                    if pl.strip():
                        print(f"    {pl.strip()}")

            # 摘要
            if resume_data.get("summary"):
                print(f"  摘要: {resume_data['summary']}")

            # 自动匹配岗位
            print("\n[匹配] 正在根据简历技能匹配岗位...")
            role_scores = []
            for rk, ri in config.ROLES.items():
                match = sum(1 for t in ri["tags"] if any(
                    t.lower() in s.lower() for s in resume_skills))
                role_scores.append((rk, match))
            role_scores.sort(key=lambda x: x[1], reverse=True)

            print("  匹配结果:")
            for i, (rk, score) in enumerate(role_scores):
                tag = " ← 推荐" if i == 0 and score > 0 else ""
                print(f"    {i+1}. {config.ROLES[rk]['title']} "
                      f"(技能匹配: {score}){tag}")

            if role_scores[0][1] > 0:
                recommended = role_scores[0][0]
                print(f"\n  推荐岗位: {config.ROLES[recommended]['title']}")
                print("  回车=确认推荐 / 输入编号=手动选")
                try:
                    confirm = input("> ").strip()
                except (ValueError, EOFError):
                    confirm = ""

                if confirm == "":
                    role_key = recommended
                else:
                    try:
                        pick = int(confirm) - 1
                        if 0 <= pick < len(role_scores):
                            role_key = role_scores[pick][0]
                        else:
                            role_key = recommended
                    except ValueError:
                        role_key = recommended
            else:
                print("  [WARN] 简历未匹配到任何岗位, 请手动选择")
                role_key = None

        if role_key is None and not resume_data:
            # 简历解析失败, 回退到手动选
            pass

    # ---- 路径A / 回退: 手动选岗位 ----
    if role_key is None:
        print("\n请选择面试岗位:")
        role_keys = list(config.ROLES.keys())
        for i, key in enumerate(role_keys, 1):
            print(f"  {i}. {config.ROLES[key]['title']}")
        print()

        try:
            choice = input("请输入编号 (1-5): ").strip()
            idx = int(choice) - 1
            if idx < 0 or idx >= len(role_keys):
                idx = 0
        except (ValueError, EOFError):
            print("输入无效, 默认选择 Python 开发工程师")
            idx = 0

        role_key = role_keys[idx]

    print(f"\n[INFO] 面试岗位: {config.ROLES[role_key]['title']}")
    if not resume_context:
        print("[INFO] 模式: 无简历")

    # ---- 面试配置 ----
    print(f"\n请选择题量 (默认5题):")
    try:
        count = int(input("> ").strip())
    except (ValueError, EOFError):
        count = 5

    print(f"\n请选择难度: 1=初级 2=中级 3=高级 (默认2):")
    try:
        diff = int(input("> ").strip())
        if diff not in (1, 2, 3):
            diff = 2
    except (ValueError, EOFError):
        diff = 2

    # ---- 初始化引擎 ----
    print(f"\n[AI] 正在连接 LLM ({config.LLM_MODEL})...")
    try:
        engine = InterviewEngine(retriever)
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        return

    init_msg = engine.configure(
        role_key, total_count=count, difficulty=diff,
        resume_context=resume_context, resume_skills=resume_skills,
    )
    print(init_msg)
    print(f"\n[提示] quit=退出 | skip=换题")
    print(f"[提示] 面试过程中不显示评分, 结束后统一给出报告")
    print(f"[提示] AI 回答为流式输出, 逐字显示\n")

    # ---- 面试主循环 (流式) ----
    try:
        print("[AI 面试官] ", end="", flush=True)
        first_q = stream_print(
            engine.generate_question_stream(),
            prefix="",
            suffix="\n\n",
        )
    except Exception as e:
        print(f"\n[ERROR] 出题失败: {e}")
        return

    while True:
        try:
            user_input = input("[你] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n面试中断。")
            break

        if not user_input:
            continue

        # 退出
        if user_input.lower() in ("quit", "exit", "q"):
            print("\n[报告] 正在生成面试综合评价...\n")
            stream_print(engine.generate_summary_stream(), suffix="\n")
            print("\n感谢参与模拟面试!")
            break

        # 换题
        if user_input.lower() in ("下一题", "换一题", "skip"):
            print("\n[系统] 跳过当前题目, 换下一题")
            print("[AI 面试官] ", end="", flush=True)
            try:
                nq = stream_print(
                    engine.generate_question_stream(),
                    prefix="",
                    suffix="\n\n",
                )
                continue
            except Exception as e:
                print(f"\n[ERROR] 出题失败: {e}")
                break

        # 正常流程: 回答 → 评分(静默) → 决策
        engine.receive_answer(user_input)
        engine.score_answer()
        decision = engine.decide()
        action = decision.get("action", "next")

        if action == "followup":
            topic = decision.get("followup_topic", "")
            print("\n[追问] ", end="", flush=True)
            stream_print(
                engine.generate_followup_stream(topic),
                prefix="",
                suffix="\n\n",
            )
            continue

        elif action == "end":
            print("\n[完成] 面试结束, 正在生成综合评价...\n")
            stream_print(engine.generate_summary_stream(), suffix="\n")
            print("\n感谢参与!")
            break

        else:  # next question
            try:
                print("[AI 面试官] ", end="", flush=True)
                nq = stream_print(
                    engine.generate_question_stream(),
                    prefix="",
                    suffix="\n\n",
                )
                if nq.startswith("[System]"):
                    # 题库耗尽, 生成报告
                    stream_print(engine.generate_summary_stream(), suffix="\n")
                    break
            except Exception as e:
                print(f"\n[ERR] {e}")
                break


def main():
    if len(sys.argv) < 2:
        print("AI 模拟面试官 — LangChain 版 (流式输出)")
        print("用法:")
        print("  python main.py build    # 离线建库 (题库更新后执行一次)")
        print("  python main.py chat     # 模拟面试 (流式)")
        print("  python main.py rebuild  # 清空旧库 + 重建")
        return

    cmd = sys.argv[1].lower()
    if cmd == "build":
        cmd_build()
    elif cmd == "chat":
        cmd_chat()
    elif cmd == "rebuild":
        cmd_rebuild()
    else:
        print(f"未知命令: {cmd}")
        print("可用: build | chat | rebuild")


if __name__ == "__main__":
    main()
