"""管理员路由：用户管理 + 使用统计"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.auth import hash_password
from server.database import Task, User
from server.deps import get_current_user, get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员权限守卫"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    is_admin: bool = False


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
) -> list[dict]:
    """列出所有用户及其使用统计"""
    users = db.query(User).order_by(User.id).all()
    result = []
    for u in users:
        task_count = db.query(func.count(Task.id)).filter(Task.user_id == u.id).scalar()
        done_count = (
            db.query(func.count(Task.id))
            .filter(Task.user_id == u.id, Task.status == "done")
            .scalar()
        )
        total_duration = (
            db.query(func.sum(Task.duration))
            .filter(Task.user_id == u.id)
            .scalar()
        ) or 0.0
        result.append({
            "id": u.id,
            "username": u.username,
            "is_admin": u.is_admin,
            "created_at": u.created_at,
            "task_count": task_count,
            "done_count": done_count,
            "total_duration": round(total_duration, 1),
        })
    return result


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(_require_admin),
) -> dict:
    """创建新用户"""
    exists = db.query(User).filter(User.username == body.username).first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
) -> dict:
    """删除用户（不能删除自己）"""
    if user_id == admin.id:
        raise HTTPException(status_code=422, detail="不能删除自己")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"ok": True}
