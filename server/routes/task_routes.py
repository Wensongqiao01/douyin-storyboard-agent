"""任务路由：创建、列表、详情（后续任务追加 SSE/视频/导出/删除）"""

import json
import queue as queue_mod
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.database import Task, User
from server.deps import get_current_user, get_db
from server.services.task_queue import task_queue
from utils.file_helpers import generate_task_id, get_task_paths

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    url: str


def _task_to_dict(task: Task) -> dict:
    """Task ORM 转字典（绝不暴露 password_hash 等敏感字段）"""
    return {
        "id": task.id,
        "url": task.url,
        "title": task.title,
        "status": task.status,
        "scenes": task.scenes_count,
        "duration": task.duration,
        "error_message": task.error_message,
        "createdAt": task.created_at,
    }


def _get_owned_task(task_id: str, user: User, db: Session) -> Task:
    """按所有权取任务，越权与不存在统一返回 404"""
    task = db.get(Task, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("")
def list_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """当前用户的所有任务，按创建时间倒序"""
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .all()
    )
    return [_task_to_dict(t) for t in tasks]


@router.post("", status_code=201)
def create_task(
    body: CreateTaskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """创建任务：持久化 + 入队"""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="视频链接不能为空")
    task_id = generate_task_id()
    db.add(Task(id=task_id, user_id=user.id, url=url))
    db.commit()
    task_queue.submit(task_id, url)
    return {"task_id": task_id}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """任务详情，状态为 done 时额外返回 scenes_detail"""
    task = _get_owned_task(task_id, user, db)
    data = _task_to_dict(task)
    if task.status == "done":
        result_json = Path(get_task_paths(task_id).result_json)
        if result_json.exists():
            with open(result_json, encoding="utf-8") as f:
                data["scenes_detail"] = json.load(f).get("scenes", [])
        else:
            data["scenes_detail"] = []
    return data


TERMINAL_STATUSES = ("done", "error")
SSE_IDLE_TIMEOUT = 900  # 秒，超过则断开让前端重连


@router.get("/{task_id}/stream")
def stream_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE 实时进度：先推当前状态，终态后关闭连接"""
    task = _get_owned_task(task_id, user, db)
    current = task.status

    if current in TERMINAL_STATUSES:
        def done_stream():
            yield f"data: {json.dumps({'status': current})}\n\n"

        return StreamingResponse(done_stream(), media_type="text/event-stream")

    sub = task_queue.subscribe(task_id)

    def event_stream():
        try:
            yield f"data: {json.dumps({'status': current})}\n\n"
            while True:
                try:
                    status = sub.get(timeout=SSE_IDLE_TIMEOUT)
                except queue_mod.Empty:
                    break
                yield f"data: {json.dumps({'status': status})}\n\n"
                if status in TERMINAL_STATUSES:
                    break
        finally:
            task_queue.unsubscribe(task_id, sub)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
