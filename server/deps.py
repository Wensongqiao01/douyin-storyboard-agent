"""FastAPI 公共依赖：数据库会话、当前用户"""

from typing import Generator

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from server import auth, database
from server.database import User


def get_db() -> Generator[Session, None, None]:
    """每请求一个 DB 会话"""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """从 Authorization: Bearer 或 ?token= 解析当前用户"""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.removeprefix("Bearer ").strip()
    else:
        token = request.query_params.get("token", "")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = auth.decode_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
