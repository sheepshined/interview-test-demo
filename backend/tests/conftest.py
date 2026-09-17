"""pytest 共享夹具与环境隔离。

在导入任何项目模块之前, 把认证 SQLite 库与 JWT 密钥指向临时目录,
避免测试污染开发库 (backend/users.db) 与 .jwt_secret。
"""
import os
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TESTS_DIR)

# 确保能 import server / config / auth
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# 认证隔离: 必须在 import config 之前设置 (conftest 先于测试模块加载)
_TMP_DIR = tempfile.mkdtemp(prefix="smartsteer_auth_test_")
os.environ.setdefault("AUTH_DB_PATH", os.path.join(_TMP_DIR, "users.db"))
# 知识库隔离 (v0.7): 同上, 测试不碰开发库 backend/knowledge.db
os.environ.setdefault("KB_DB_PATH", os.path.join(_TMP_DIR, "knowledge.db"))
# 知识库向量库隔离 (v0.8)
os.environ.setdefault("KB_CHROMA_PATH", os.path.join(_TMP_DIR, "kb_chroma"))
# ≥32 字节, 满足 pyjwt 对 HS256 密钥长度的建议 (避免 InsecureKeyLengthWarning)
os.environ.setdefault(
    "JWT_SECRET_KEY", "pytest-fixed-secret-key-0123456789abcdef0123456789abcdef"
)
