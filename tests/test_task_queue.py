"""tests/test_task_queue.py — FIFO 队列：订阅/发布/串行执行"""

import queue
import time

from server import database
from server.database import Task, init_db
from server.services.task_queue import TaskQueue


def _seed_task(task_id: str) -> None:
    session = database.SessionLocal()
    session.add(Task(id=task_id, user_id=1, url="https://example.com"))
    session.commit()
    session.close()


def test_publish_updates_db_and_notifies_subscribers(tmp_path):
    init_db(str(tmp_path / "q.db"))
    _seed_task("t1")
    tq = TaskQueue(runner=lambda tid, url: None)

    sub = tq.subscribe("t1")
    tq.publish("t1", "transcribing")

    assert sub.get(timeout=1) == "transcribing"
    session = database.SessionLocal()
    assert session.get(Task, "t1").status == "transcribing"
    session.close()


def test_unsubscribe_stops_notifications(tmp_path):
    init_db(str(tmp_path / "q.db"))
    _seed_task("t2")
    tq = TaskQueue(runner=lambda tid, url: None)

    sub = tq.subscribe("t2")
    tq.unsubscribe("t2", sub)
    tq.publish("t2", "done")
    assert sub.empty()


def test_worker_runs_tasks_in_fifo_order(tmp_path):
    init_db(str(tmp_path / "q.db"))
    executed: list[str] = []

    tq = TaskQueue(runner=lambda tid, url: executed.append(tid))
    tq.start()
    tq.submit("a", "url-a")
    tq.submit("b", "url-b")

    deadline = time.time() + 3
    while len(executed) < 2 and time.time() < deadline:
        time.sleep(0.05)
    assert executed == ["a", "b"]


def test_runner_exception_marks_task_error(tmp_path):
    init_db(str(tmp_path / "q.db"))
    _seed_task("t3")

    def bad_runner(tid: str, url: str) -> None:
        raise RuntimeError("下载失败")

    tq = TaskQueue(runner=bad_runner)
    sub = tq.subscribe("t3")
    tq.start()
    tq.submit("t3", "url")

    assert sub.get(timeout=3) == "error"
    session = database.SessionLocal()
    task = session.get(Task, "t3")
    assert task.status == "error"
    assert "下载失败" in task.error_message
    session.close()
