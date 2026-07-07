"""
config.py — AI模拟面试官全局配置 (LangChain 版)
从 .env 文件加载 API Key 和模型路径，不硬编码敏感信息。
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
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
EMBEDDING_MODEL_PATH = os.getenv(
    "LOCAL_BGE_MODEL_PATH",
    "D:/BGE_BASE_ZN_1.5/models--BAAI--bge-base-zh-v1.5/"
    "snapshots/f03589ceff5aac7111bd60cfc7d497ca17ecac65",
)

# ==================== LLM 配置 ====================
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 4096
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY = 1.0

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
}

# ==================== 评分维度 ====================
SCORE_DIMENSIONS = ["accuracy", "completeness", "depth", "clarity"]
