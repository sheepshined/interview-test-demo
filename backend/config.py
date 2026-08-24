"""
config.py — AI模拟面试官全局配置 (LangChain 版)
从 .env 文件加载 API Key 和模型路径，不硬编码敏感信息。
"""
import os
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# 轻量日志配置 (各模块用 logging.getLogger(__name__) 即可)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
INTERVIEW_RECORDS_DIR = os.path.join(BASE_DIR, "agent")
COLLECTION_NAME = "interview_questions"

# 确保目录存在
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ==================== 分块参数 ====================
CHUNK_SIZE = 500
OVERLAP = 50

# ==================== 检索参数 ====================
TOP_K = 5
BM25_WEIGHT = 0.4       # BM25 检索权重
VECTOR_WEIGHT = 0.6     # 向量检索权重
RRF_K = 60              # Reciprocal Rank Fusion 参数

# ==================== BGE 嵌入模型路径 ====================
# 默认使用 HuggingFace Hub 模型名 (BAAI/bge-base-zh-v1.5), 跨平台可移植, 首次自动下载;
# 若已本地下载, 可在 .env 设 LOCAL_BGE_MODEL_PATH 指向本地快照目录以加速启动
EMBEDDING_MODEL_PATH = os.getenv(
    "LOCAL_BGE_MODEL_PATH", "BAAI/bge-base-zh-v1.5"
)

# ==================== LLM 配置 ====================
# API Key 优先读 LLM_API_KEY, 向后兼容 DEEPSEEK_API_KEY
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

# ---- 视觉模型 (千问 qwen-vl, 扫描件简历解析兜底; 未配置 Key 则该路径自动禁用) ----
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-plus")
VISION_BASE_URL = os.getenv(
    "VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 模型分层 (阶段3): fast=出题/评分/追问/开场/收尾(求速度), strong=总结报告(求质量)
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")               # 兼容旧引用
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", LLM_MODEL)          # 快速模型
LLM_MODEL_STRONG = os.getenv("LLM_MODEL_STRONG", LLM_MODEL)      # 强模型(总结, 可配 deepseek-reasoner/glm-4.5)
LLM_TEMPERATURE = 0.7
LLM_TEMPERATURE_STRONG = 0.3                                       # 总结低温求稳定
LLM_MAX_TOKENS = 4096
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY = 1.0

# ==================== CORS 配置 ====================
# 开发态允许的前端来源 (逗号分隔); 生产态按需收紧
CORS_ORIGINS = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:8080",
    ).split(",") if o.strip()
]

# ==================== Memory 配置 ====================
MEMORY_WINDOW_SIZE = 10         # 保留最近 N 条消息
MEMORY_COMPRESS_THRESHOLD = 6000  # 对话超过此字符数时触发摘要压缩

# ==================== 面试角色配置 ====================
ROLES = {
    "python_dev": {
        "title": "Python 开发工程师",
        "tags": ["Python", "Django", "Flask", "FastAPI", "数据库", "异步编程"],
        "file": "python_dev.md",
    },
    "java_dev": {
        "title": "Java 开发工程师",
        "tags": ["Java", "Spring", "MyBatis", "JVM", "微服务", "并发编程"],
        "file": "java_dev.md",
    },
    "frontend_dev": {
        "title": "前端开发工程师",
        "tags": ["JavaScript", "Vue", "React", "CSS", "TypeScript", "性能优化"],
        "file": "frontend_dev.md",
    },
    "product_manager": {
        "title": "产品经理",
        "tags": ["需求分析", "PRD", "用户研究", "数据分析", "竞品分析"],
        "file": "product_manager.md",
    },
    "general_hr": {
        "title": "通用能力面试",
        "tags": ["沟通表达", "项目经验", "问题解决", "团队协作", "职业规划"],
        "file": "general_hr.md",
    },
    "algorithm": {
        "title": "算法工程师",
        "tags": ["算法", "数据结构", "动态规划", "排序", "复杂度"],
        "file": "algorithm.md",
    },
    "devops": {
        "title": "运维工程师",
        "tags": ["Linux", "Docker", "Kubernetes", "CI/CD", "Nginx", "监控"],
        "file": "devops.md",
    },
    "data_analyst": {
        "title": "数据分析师",
        "tags": ["SQL", "Python", "统计", "数据分析", "可视化"],
        "file": "data_analyst.md",
    },
}

# ==================== 面试官人设 ====================
# 每种人设定义了面试官的性格、提问风格和追问偏好。
# configure_node 会随机选择一种人设注入到出题/追问/开场/收尾 prompt 中。
INTERVIEWER_PERSONAS = {
    "strict_cto": {
        "name": "严谨CTO",
        "description": (
            "你是一位严谨、高标准的技术 CTO。你注重技术深度和底层原理，"
            "对模糊或表面的回答不满意，会直接指出不足。"
            "你的语气专业但略显严肃，提问简洁有力，追问直切要害。"
            "你期望候选人能展示真正的技术理解，而不只是背诵概念。"
        ),
        "question_style": "提问直接，不寒暄，直奔技术核心。偏好追问'为什么'和'底层原理'。",
        "followup_style": "追问犀利，会针对回答中的模糊点直接质疑。",
    },
    "warm_hr": {
        "name": "温和HR",
        "description": (
            "你是一位温和、善于沟通的 HR 面试官。你注重候选人的表达能力、"
            "团队协作和职业态度。你的语气友善亲切，会用鼓励性的语言引导候选人。"
            "即使候选人回答不够完美，你也会先肯定做得好的部分，再温和提出改进方向。"
        ),
        "question_style": "提问自然流畅，会用'聊聊''分享'等亲和词汇。关注项目经验和软技能。",
        "followup_style": "追问温和，先肯定再引导，鼓励候选人展开。",
    },
    "deep_tech": {
        "name": "技术深挖型",
        "description": (
            "你是一位好奇心极强、喜欢深挖技术细节的资深工程师。"
            "你对每个话题都想了解更多，会连续追问'还有呢''具体怎么实现''举个例子'。"
            "你的语气充满好奇但不会让人觉得被审问，更像一场深入的技术对话。"
        ),
        "question_style": "提问喜欢从实际场景出发，偏好'你在项目中遇到过XX问题吗'。",
        "followup_style": "追问层层递进，从概念→实现→优化→边界情况。",
    },
}

# ==================== 难度标签 ====================
DIFFICULTY_LABELS = {1: "Junior", 2: "Intermediate", 3: "Senior"}

# ==================== 评分维度 ====================
SCORE_DIMENSIONS = ["accuracy", "completeness", "depth", "clarity"]
