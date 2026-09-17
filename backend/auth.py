"""
auth.py — 用户认证模块 (SQLite 用户表 + bcrypt 密码哈希 + JWT)

v0.6 引入, 替代原先"固定账号 admin/123123 + MD5 token + 后端不校验"的演示级登录:
  - 用户存 SQLite (默认 backend/users.db, 可用 AUTH_DB_PATH 覆盖), 密码 bcrypt 哈希
  - 首次启动自动建表并预置演示账号 admin/123123 (答辩兼容)
  - 登录成功签发 JWT (HS256, 默认 24h 过期), 所有 REST 接口与 WS 握手均校验
  - JWT 密钥: 优先 .env 的 JWT_SECRET_KEY; 未配置则自动生成并落盘 .jwt_secret 复用

公开接口: POST /api/login、POST /api/register; 其余 REST 与 /ws/chat 均需 Bearer token。
"""
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config

ALGORITHM = "HS256"
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

# HTTPBearer(auto_error=False): 缺头/格式错时由我们自己抛 401 (而非默认 403)
_bearer_scheme = HTTPBearer(auto_error=False)


# ============================================================
# JWT 密钥管理
# ============================================================

def _load_or_create_secret() -> str:
    """读取签名密钥: .env 优先, 否则自动生成并持久化到 backend/.jwt_secret"""
    if config.JWT_SECRET_KEY:
        return config.JWT_SECRET_KEY
    secret_path = os.path.join(config.BASE_DIR, ".jwt_secret")
    try:
        if os.path.isfile(secret_path):
            with open(secret_path, encoding="utf-8") as f:
                existing = f.read().strip()
                if existing:
                    return existing
        generated = secrets.token_hex(32)
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(generated)
        return generated
    except OSError:
        # 文件不可用时退化为进程内随机密钥 (重启后旧 token 全部失效)
        return secrets.token_hex(32)


_SECRET_KEY = _load_or_create_secret()


# ============================================================
# SQLite 用户表
# ============================================================

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.AUTH_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表; 空库时预置演示账号 admin/123123。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        # v0.9: 登出吊销黑名单 (存 token 摘要, 不存原文)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                exp INTEGER NOT NULL
            )
            """
        )
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                ("admin", hash_password("123123"), _now_iso()),
            )


def _token_digest(token: str) -> str:
    import hashlib
    return hashlib.sha256(f"{_SECRET_KEY}:{token}".encode("utf-8")).hexdigest()


def revoke_token(token: str) -> bool:
    """登出吊销: 把 token 摘要写进黑名单, 到期后可清理。"""
    try:
        payload = verify_token(token)
    except jwt.InvalidTokenError:
        return False
    with _connect() as conn:
        # 顺手清理已过期的黑名单项
        conn.execute("DELETE FROM revoked_tokens WHERE exp < ?",
                     (int(datetime.now(timezone.utc).timestamp()),))
        conn.execute(
            "INSERT OR REPLACE INTO revoked_tokens (token_hash, username, exp) VALUES (?, ?, ?)",
            (_token_digest(token), payload.get("username", ""), int(payload.get("exp", 0))),
        )
    return True


def is_revoked(token: str) -> bool:
    try:
        digest = _token_digest(token)
    except Exception:
        return False
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM revoked_tokens WHERE token_hash = ?", (digest,)
        ).fetchone()
    return row is not None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# 密码与用户操作
# ============================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_credentials(username: str, password: str) -> Optional[str]:
    """校验用户名/密码格式, 返回错误信息 (None 表示合法)。"""
    if not _USERNAME_RE.fullmatch(username or ""):
        return "用户名须为 3-20 位字母、数字或下划线"
    # bcrypt 只取前 72 字节, 超长部分直接拒绝更安全
    if not password or len(password.encode("utf-8")) < 6:
        return "密码至少 6 位"
    if len(password.encode("utf-8")) > 72:
        return "密码过长 (最多 72 字节)"
    return None


def create_user(username: str, password: str) -> dict:
    """注册新用户。用户名冲突时抛 ValueError。"""
    error = validate_credentials(username, password)
    if error:
        raise ValueError(error)
    try:
        with _connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, hash_password(password), _now_iso()),
            )
            return {"id": cursor.lastrowid, "username": username}
    except sqlite3.IntegrityError as exc:
        raise ValueError("用户名已被注册") from exc


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """校验账号密码, 成功返回 {id, username}, 失败返回 None。"""
    if not username or not password:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"]}


# ============================================================
# 登录限流 (进程内, 按 IP + 用户名维度计数)
# ============================================================
# 窗口内连续失败达到上限即锁定; 单进程部署足够, 多进程部署需换 Redis。
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_LOCK_SECONDS = 15 * 60

_login_lock = threading.Lock()
_login_failures: dict[str, Deque[float]] = defaultdict(deque)
_login_locked_until: dict[str, float] = {}


def _login_key(ip: str, username: str) -> str:
    return f"{ip or 'unknown'}::{(username or '').strip().lower()}"


def login_retry_after(ip: str, username: str) -> int:
    """账号仍处于锁定时返回剩余秒数, 否则返回 0。"""
    remain = _login_locked_until.get(_login_key(ip, username), 0) - time.time()
    return int(remain) + 1 if remain > 0 else 0


def record_login_failure(ip: str, username: str) -> None:
    """记录一次失败登录; 窗口内失败数达上限则锁定。"""
    key = _login_key(ip, username)
    now = time.time()
    with _login_lock:
        attempts = _login_failures[key]
        attempts.append(now)
        while attempts and now - attempts[0] > LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_MAX_FAILURES:
            _login_locked_until[key] = now + LOGIN_LOCK_SECONDS


def record_login_success(ip: str, username: str) -> None:
    """登录成功后清除该 IP+用户名的失败计数与锁定。"""
    key = _login_key(ip, username)
    with _login_lock:
        _login_failures.pop(key, None)
        _login_locked_until.pop(key, None)


# ============================================================
# JWT 签发与校验
# ============================================================

def create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=config.TOKEN_EXPIRE_HOURS))
    payload = {
        "sub": username,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """校验并解析 JWT。无效/过期抛 jwt.InvalidTokenError 子类。"""
    return jwt.decode(token, _SECRET_KEY, algorithms=[ALGORITHM])


# ============================================================
# FastAPI 集成 (REST 依赖 + WS 握手)
# ============================================================

def get_user_from_token(token: str) -> Optional[dict]:
    """统一 token 校验: 吊销名单 → JWT 有效性 → 用户仍存在。成功返回用户, 失败 None。"""
    if not token or is_revoked(token):
        return None
    try:
        payload = verify_token(token)
    except jwt.InvalidTokenError:
        return None
    username = payload.get("username") or payload.get("sub") or ""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        # 用户已被删除但 token 仍有效
        return None
    return {"id": row["id"], "username": row["username"]}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """REST 接口鉴权依赖: Authorization: Bearer <jwt> → {id, username}。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未提供访问令牌，请先登录")
    user = get_user_from_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已过期或令牌无效，请重新登录")
    return user


def ws_authenticate(ws: WebSocket) -> Optional[dict]:
    """WebSocket 握手鉴权: query 参数 ?token=<jwt>。失败返回 None (由调用方关闭连接)。"""
    return get_user_from_token(ws.query_params.get("token", ""))
