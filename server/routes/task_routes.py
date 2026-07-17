"""任务路由：创建、列表、详情、批量（后续任务追加 SSE/视频/导出/删除）"""

import json
import queue as queue_mod
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.database import Task, User
from server.deps import get_current_user, get_db
from server.services.task_queue import task_queue
from utils.file_helpers import cleanup_task, generate_task_id, get_task_paths

from models.schemas import FusedScene
from utils.exporters import (
    export_clips,
    scenes_to_csv,
    scenes_to_markdown,
    scenes_to_srt,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    url: str


class CreateBatchRequest(BaseModel):
    text: str


# URL 提取：从抖音分享文案中识别链接（正则与旧版 app.py 一致）
_URL_PATTERN = re.compile(r"https?://[^\s。，）)]+")


def _extract_url(text: str) -> str | None:
    """从输入文本中提取第一个视频链接"""
    match = _URL_PATTERN.search(text)
    if match:
        return match.group(0).rstrip("/")
    return None


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
    """创建任务：从分享文案中提取链接 → 持久化 → 入队"""
    raw = body.url.strip()
    url = _extract_url(raw)
    if not url:
        raise HTTPException(status_code=422, detail="未检测到视频链接，请粘贴抖音分享文案")
    task_id = generate_task_id()
    db.add(Task(id=task_id, user_id=user.id, url=url))
    db.commit()
    task_queue.submit(task_id, url)
    return {"task_id": task_id}


@router.post("/batch", status_code=201)
def create_batch_tasks(
    body: CreateBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """批量创建任务：每行一个链接（支持分享文案），逐条入队"""
    lines = body.text.strip().split("\n")
    result: list[dict] = []
    for line in lines:
        url = _extract_url(line.strip())
        if not url:
            continue
        task_id = generate_task_id()
        db.add(Task(id=task_id, user_id=user.id, url=url))
        db.commit()
        task_queue.submit(task_id, url)
        result.append({"task_id": task_id, "url": url})
    if not result:
        raise HTTPException(status_code=422, detail="未检测到有效的视频链接")
    return result


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


# 允许删除的状态：终态或还没被 worker 取走的排队态。
# 注意：删除 pending 任务后 worker 仍会执行它，但 publish 时 DB 行已不存在，
# 只是白跑一趟，不会出错——5 人内部工具接受这个取舍。
DELETABLE_STATUSES = ("done", "error", "pending")


@router.get("/{task_id}/video")
def get_video(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """原始视频下载/在线播放（Starlette FileResponse 自带 Range 支持）"""
    _get_owned_task(task_id, user, db)
    video_path = get_task_paths(task_id).original_video
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="视频文件已过期清理")
    return FileResponse(
        video_path, media_type="video/mp4", filename=f"{task_id}.mp4"
    )


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    task = _get_owned_task(task_id, user, db)
    if task.status not in DELETABLE_STATUSES:
        raise HTTPException(status_code=409, detail="任务处理中，暂不能删除")
    db.delete(task)
    db.commit()
    cleanup_task(task_id)
    return {"ok": True}


EXPORT_MEDIA_TYPES = {
    "srt": ("text/plain; charset=utf-8", "srt"),
    "md": ("text/markdown; charset=utf-8", "md"),
    "csv": ("text/csv; charset=utf-8", "csv"),
}


def _attachment_header(filename: str) -> dict:
    """中文文件名需 RFC 5987 编码"""
    return {
        "Content-Disposition":
            f"attachment; filename*=UTF-8''{quote(filename)}"
    }


@router.get("/{task_id}/export")
def export_task(
    task_id: str,
    format: str = "md",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, user, db)
    if task.status != "done":
        raise HTTPException(status_code=409, detail="任务尚未完成，无法导出")

    paths = get_task_paths(task_id)
    if not Path(paths.result_json).exists():
        raise HTTPException(status_code=404, detail="分析结果文件不存在")
    with open(paths.result_json, encoding="utf-8") as f:
        raw = json.load(f)
    scenes = [FusedScene(**s) for s in raw.get("scenes", [])]
    title = raw.get("title") or task.title or task_id

    if format in EXPORT_MEDIA_TYPES:
        media_type, ext = EXPORT_MEDIA_TYPES[format]
        if format == "srt":
            content = scenes_to_srt(scenes)
        elif format == "md":
            content = scenes_to_markdown(scenes, title=title)
        else:
            content = scenes_to_csv(scenes)
        return PlainTextResponse(
            content,
            media_type=media_type,
            headers=_attachment_header(f"{title}.{ext}"),
        )

    if format == "clips":
        if not Path(paths.original_video).exists():
            raise HTTPException(status_code=404, detail="视频文件已过期清理")
        clips_dir = str(Path(paths.task_dir) / "clips")
        zip_path = export_clips(paths.original_video, scenes, clips_dir)
        return FileResponse(
            zip_path,
            media_type="application/zip",
            headers=_attachment_header(f"{title}_clips.zip"),
        )

    raise HTTPException(status_code=422, detail="不支持的导出格式")
