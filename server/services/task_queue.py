"""内存 FIFO 任务队列 — 单 worker 线程串行执行 pipeline，推送进度事件

服务器只有 2 核 4GB，Whisper 必须串行（worker 固定 1 个）。
进度事件同时写入 DB（刷新页面可恢复状态）和推给 SSE 订阅者。
"""

import queue
import threading
from typing import Callable

from loguru import logger

from core.pipeline import Pipeline
from models.schemas import TaskStatus
from server import database
from server.database import Task


class TaskQueue:
    """FIFO 任务队列，publish 同时更新 DB 与通知订阅者"""

    def __init__(self, runner: Callable[[str, str], None] | None = None):
        self._queue: queue.Queue = queue.Queue()
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._runner = runner or self._run_pipeline
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动 worker 线程（daemon，随主进程退出）"""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, task_id: str, url: str) -> None:
        """任务入队"""
        self._queue.put((task_id, url))

    def subscribe(self, task_id: str) -> queue.Queue:
        """订阅任务进度，返回接收事件的 Queue"""
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        with self._lock:
            subs = self._subscribers.get(task_id, [])
            if q in subs:
                subs.remove(q)
            if not subs:
                self._subscribers.pop(task_id, None)

    def publish(self, task_id: str, status: str) -> None:
        """更新 DB 状态并推送给所有订阅者"""
        session = database.SessionLocal()
        try:
            task = session.get(Task, task_id)
            if task is not None:
                task.status = status
                session.commit()
        finally:
            session.close()
        with self._lock:
            for q in self._subscribers.get(task_id, []):
                q.put(status)

    def _worker(self) -> None:
        while True:
            task_id, url = self._queue.get()
            try:
                self._runner(task_id, url)
            except Exception as e:
                logger.error("[{}] 队列执行异常: {}", task_id, e)
                self._finish(task_id, TaskStatus.ERROR.value, error=str(e))

    def _run_pipeline(self, task_id: str, url: str) -> None:
        """默认 runner：跑完整 pipeline 并把结果写回 DB"""
        pipeline = Pipeline(
            on_progress=lambda status: self.publish(task_id, status),
        )
        result = pipeline.run(url, task_id=task_id)
        session = database.SessionLocal()
        try:
            task = session.get(Task, task_id)
            if task is not None:
                task.title = result.title
                task.scenes_count = len(result.scenes)
                if result.scenes:
                    task.duration = (
                        result.scenes[-1].end_time - result.scenes[0].start_time
                    )
                task.error_message = result.error_message or ""
                session.commit()
        finally:
            session.close()
        self.publish(task_id, result.status.value)

    def _finish(self, task_id: str, status: str, error: str = "") -> None:
        """异常兜底：写入错误信息并推送终态"""
        session = database.SessionLocal()
        try:
            task = session.get(Task, task_id)
            if task is not None:
                task.error_message = error
                session.commit()
        finally:
            session.close()
        self.publish(task_id, status)


# 全局单例，由 server/main.py 在启动时 start()
task_queue = TaskQueue()
