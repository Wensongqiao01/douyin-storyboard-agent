"""密码哈希与 JWT 签发/校验"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import config


def hash_password(password: str) -> str:
    """bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码，哈希格式非法时返回 False 而不是抛异常"""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_token(user_id: int, username: str, is_admin: bool = False) -> str:
    """签发 JWT"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=config.jwt_expire_hours),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解析 JWT，失败抛 jwt.InvalidTokenError（含过期）"""
    return jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
