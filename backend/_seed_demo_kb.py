"""临时: 向知识库灌入演示数据 (仅 admin), 看图谱效果用。"""
import httpx

BASE = "http://127.0.0.1:8000"

DEMO = [
    ("RAG 检索增强生成", "RAG = 检索 + 生成。核心流程: 文档分块 → [[向量检索]] → 拼接上下文 → LLM 生成。分块策略直接影响效果, 参见 [[文本分块策略]]。", ["LLM", "RAG"]),
    ("向量检索", "Embedding 把文本映射为稠密向量, 用余弦相似度找最近邻。常用 BGE 系列。是 [[RAG 检索增强生成]] 和 [[语义关联]] 的基础。", ["LLM", "基础"]),
    ("文本分块策略", "固定长度/重叠/按语义分块。块太大检索稀释, 太小丢失上下文。与 [[Embedding 模型]] 的最大长度有关。", ["RAG"]),
    ("Embedding 模型", "BGE / text2vec / OpenAI embedding。中文推荐 BAAI/bge-base-zh。用于 [[向量检索]]。", ["LLM", "基础"]),
    ("Transformer 架构", "自注意力 + 前馈层。是 [[BERT]] 与 [[GPT 系列]] 的共同基础。", ["深度学习"]),
    ("BERT", "双向编码器, 擅长理解任务。基于 [[Transformer 架构]]。", ["深度学习"]),
    ("GPT 系列", "自回归解码器, 擅长生成。基于 [[Transformer 架构]], 大规模预训练涌现出 [[Prompt 工程]] 能力。", ["LLM"]),
    ("Prompt 工程", "设计指令让 [[GPT 系列]] 稳定输出。few-shot / CoT / 结构化输出约束。", ["LLM"]),
    ("语义关联", "两个笔记向量相似度高时在图谱中自动连虚线边, 区别于手写的 [[向量检索]] 显式链接。", ["知识库"]),
    ("微调 LoRA", "低秩适配, 只训少量参数。与 [[Prompt 工程]] 是成本互补方案。", ["LLM"]),
    ("MySQL 索引", "B+ 树结构, 联合索引最左前缀。面试薄弱点。", ["面试薄弱点", "数据库"]),
    ("Redis 持久化", "RDB 快照 vs AOF 日志。面试薄弱点。", ["面试薄弱点", "数据库"]),
]


def main():
    http = httpx.Client(base_url=BASE, timeout=15)
    # 清掉 admin 旧演示数据
    r = http.post("/api/login", json={"username": "admin", "password": "123123"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    for n in http.get("/api/kb/notes", headers=h).json().get("notes", []):
        http.delete(f"/api/kb/notes/{n['id']}", headers=h)
    ok = 0
    for title, content, tags in DEMO:
        r = http.post("/api/kb/notes", headers=h,
                      json={"title": title, "content": content, "tags": tags})
        ok += 1 if r.status_code == 200 else 0
    print(f"seeded {ok}/{len(DEMO)} notes")


if __name__ == "__main__":
    main()
