"""tests/test_task_routes.py — 任务 CRUD 路由"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import database
from server.auth import create_token, hash_password
from server.database import Task, User, init_db
from server.routes.auth_routes import router as auth_router
from server.routes.task_routes import router as task_router


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """测试环境：临时 DB + 两个用户 + mock 队列"""
    from config import config
    from server.services import task_queue as tq_module

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    monkeypatch.setattr(config, "output_base_dir", str(tmp_path / "output"))
    init_db(str(tmp_path / "test.db"))

    submitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tq_module.task_queue, "submit", lambda tid, url: submitted.append((tid, url))
    )

    session = database.SessionLocal()
    session.add(User(username="alice", password_hash=hash_password("pw")))
    session.add(User(username="bob", password_hash=hash_password("pw")))
    session.commit()
    session.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(task_router)
    client = TestClient(app)
    return client, submitted


def _auth(user_id: int, username: str) -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, username)}"}


def test_create_task_enqueues_and_persists(env):
    client, submitted = env
    resp = client.post(
        "/api/tasks",
        json={"url": "https://v.douyin.com/xyz/"},
        headers=_auth(1, "alice"),
    )
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]
    assert submitted == [(task_id, "https://v.douyin.com/xyz/")]

    session = database.SessionLocal()
    task = session.get(Task, task_id)
    assert task.user_id == 1
    assert task.status == "pending"
    session.close()


def test_create_task_rejects_empty_url(env):
    client, _ = env
    resp = client.post(
        "/api/tasks", json={"url": "  "}, headers=_auth(1, "alice")
    )
    assert resp.status_code == 422


def test_list_tasks_isolated_by_user(env):
    client, _ = env
    client.post("/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice"))
    client.post("/api/tasks", json={"url": "https://b/"}, headers=_auth(2, "bob"))

    tasks = client.get("/api/tasks", headers=_auth(1, "alice")).json()
    assert len(tasks) == 1
    assert tasks[0]["url"] == "https://a/"


def test_get_task_detail_includes_scenes_when_done(env, tmp_path):
    from config import config
    from utils.file_helpers import ensure_dir, get_task_paths

    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]

    # 模拟任务完成：DB 状态 + result.json
    session = database.SessionLocal()
    task = session.get(Task, task_id)
    task.status = "done"
    session.commit()
    session.close()

    paths = get_task_paths(task_id)
    ensure_dir(paths.task_dir)
    result = {
        "task_id": task_id,
        "status": "done",
        "title": "",
        "url": "https://a/",
        "scenes": [
            {
                "index": 0,
                "start_time": 0.0,
                "end_time": 5.0,
                "summary": "开场",
                "text": "大家好",
                "has_scene_cut": True,
            }
        ],
        "error_message": None,
    }
    with open(paths.result_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    detail = client.get(f"/api/tasks/{task_id}", headers=_auth(1, "alice")).json()
    assert detail["status"] == "done"
    assert detail["scenes_detail"][0]["summary"] == "开场"


def test_get_task_of_other_user_returns_404(env):
    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=_auth(2, "bob"))
    assert resp.status_code == 404


def _sse_lines(resp) -> list[dict]:
    """解析 SSE 响应体为 dict 列表"""
    return [
        json.loads(line.removeprefix("data: "))
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]


def test_stream_terminal_task_yields_final_status(env):
    """已完成的任务：流立即返回终态并结束"""
    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    session = database.SessionLocal()
    session.get(Task, task_id).status = "done"
    session.commit()
    session.close()

    resp = client.get(f"/api/tasks/{task_id}/stream", headers=_auth(1, "alice"))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _sse_lines(resp)
    assert events == [{"status": "done"}]


def test_stream_pushes_progress_until_done(env):
    """进行中的任务：先收当前状态，再收订阅事件，done 后关闭"""
    import threading
    import time

    from server.services.task_queue import task_queue

    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]

    def push_later() -> None:
        time.sleep(0.3)
        task_queue.publish(task_id, "transcribing")
        task_queue.publish(task_id, "done")

    threading.Thread(target=push_later, daemon=True).start()
    resp = client.get(f"/api/tasks/{task_id}/stream", headers=_auth(1, "alice"))
    statuses = [e["status"] for e in _sse_lines(resp)]
    assert statuses[0] == "pending"
    assert statuses[-1] == "done"
    assert "transcribing" in statuses


def test_video_serves_file(env):
    from utils.file_helpers import ensure_dir, get_task_paths

    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    paths = get_task_paths(task_id)
    ensure_dir(paths.video_dir)
    Path(paths.original_video).write_bytes(b"fake-mp4-bytes")

    resp = client.get(f"/api/tasks/{task_id}/video", headers=_auth(1, "alice"))
    assert resp.status_code == 200
    assert resp.content == b"fake-mp4-bytes"


def test_video_missing_returns_404(env):
    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    resp = client.get(f"/api/tasks/{task_id}/video", headers=_auth(1, "alice"))
    assert resp.status_code == 404
    assert "过期" in resp.json()["detail"]


def test_delete_task_removes_row_and_files(env):
    from utils.file_helpers import ensure_dir, get_task_paths

    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    paths = get_task_paths(task_id)
    ensure_dir(paths.video_dir)
    Path(paths.original_video).write_bytes(b"x")

    resp = client.delete(f"/api/tasks/{task_id}", headers=_auth(1, "alice"))
    assert resp.status_code == 200
    assert not Path(paths.task_dir).exists()

    session = database.SessionLocal()
    assert session.get(Task, task_id) is None
    session.close()


def test_delete_processing_task_returns_409(env):
    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    session = database.SessionLocal()
    session.get(Task, task_id).status = "transcribing"
    session.commit()
    session.close()

    resp = client.delete(f"/api/tasks/{task_id}", headers=_auth(1, "alice"))
    assert resp.status_code == 409
