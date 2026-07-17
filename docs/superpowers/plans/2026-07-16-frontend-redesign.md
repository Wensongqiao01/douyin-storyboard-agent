# 视频分镜分析 — 前后端重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Gradio 应用重构为 FastAPI + Vue 3 全栈应用，支持 JWT 多租户、SSE 实时进度、任务历史、视频/分镜导出、3天自动清理。

**Architecture:** FastAPI 提供 REST API + SSE，Vue 3 SPA 由 FastAPI 静态文件服务，SQLite 存储用户和任务元数据，核心 `core/` pipeline 模块近零改动（仅加 2 个向后兼容的可选参数）。内存 FIFO 队列串行执行 Whisper 任务。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite + PyJWT + bcrypt + APScheduler + core/ pipeline（现有）+ Vue 3 + Vite + Tailwind + Naive UI（现有原型）

**预期文件结构：**
```
server/
├── __init__.py
├── main.py              # FastAPI app, mount static, lifespan
├── auth.py              # JWT create/verify, password hash
├── database.py          # SQLAlchemy models + session
├── deps.py              # get_db / get_current_user 依赖
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py   # POST /api/auth/login
│   └── task_routes.py   # CRUD + SSE + export + video serve
├── services/
│   ├── __init__.py
│   ├── task_queue.py    # FIFO queue + pipeline runner
│   └── cleaner.py       # APScheduler video cleanup
utils/exporters.py       # SRT/MD/CSV/clips 导出
scripts/create_user.py   # 管理员创建账号 CLI
config.py                # 新增 jwt_secret, db_path, video_ttl_days
requirements.txt         # 新增 fastapi, uvicorn, sqlalchemy, pyjwt 等
```

**关键设计决定（与 spec 的差异说明）：**

1. **多租户存储路径**：spec 写的是 `output/{user_id}/{task_id}/`，本计划改为保持现有 `output/{task_id}/` 扁平结构，用 DB 的 `tasks.user_id` 做权限隔离（所有文件访问都经过 API 鉴权）。理由：`core/pipeline.py` 内部用 `get_task_paths(task_id)` 生成路径，改嵌套路径就要动 core；DB 隔离对 5 人内部工具完全够用。
2. **core/ 近零改动**：给 `Pipeline` 加两个向后兼容的可选参数——`on_progress` 回调（SSE 进度需要）和 `run(url, task_id=...)`（服务端要先建 DB 记录再跑 pipeline，必须预先拿到 task_id）。所有现有调用方（app.py、tests）不受影响。
3. **密码哈希用 bcrypt 直接调用**（不用 passlib，passlib 已停止维护且与 bcrypt 4.x 有兼容问题）。
4. **SSE 不引第三方库**：用 FastAPI 的 `StreamingResponse` + 同步 generator（Starlette 会自动放到线程池）。
5. **测试注意**：Starlette 的 `TestClient(app)` 不用 `with` 时不触发 lifespan，所以测试里手动调 `init_db(临时路径)`，不会碰真实 DB，也不会启动队列线程和调度器。

---

## Task 1: core/pipeline.py 加进度回调与外部 task_id（向后兼容）

**Files:**
- Modify: `core/pipeline.py`
- Test: `tests/test_pipeline_progress.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_pipeline_progress.py — Pipeline 进度回调与外部 task_id"""

from unittest.mock import MagicMock

from core.pipeline import Pipeline
from models.schemas import (
    SceneCutsResult,
    SemanticResult,
    TaskStatus,
    WhisperResult,
)


def _make_pipeline(on_progress=None) -> Pipeline:
    """构造全 mock 依赖的 Pipeline"""
    transcriber = MagicMock()
    transcriber.transcribe.return_value = WhisperResult(text="测试", duration=1.0)
    segmenter = MagicMock()
    segmenter.segment.return_value = SemanticResult(segments=[])
    scene = MagicMock()
    scene.detect.return_value = SceneCutsResult(cuts=[], total_frames=10)
    cleaner = MagicMock()
    cleaner.clean.side_effect = lambda scenes: scenes
    return Pipeline(
        downloader=lambda url, path: path,
        audio_extractor=MagicMock(extract=MagicMock(return_value="a.wav")),
        transcriber=transcriber,
        segmenter=segmenter,
        scene_detector=scene,
        fuser=lambda *a, **k: [],
        text_cleaner=cleaner,
        pipeline_timeout=0,
        on_progress=on_progress,
    )


def test_run_uses_external_task_id(tmp_path, monkeypatch):
    """run() 接受外部 task_id，结果里的 task_id 与之一致"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))
    pipeline = _make_pipeline()
    result = pipeline.run("https://example.com/v", task_id="my_task_001")
    assert result.task_id == "my_task_001"
    assert result.status == TaskStatus.DONE


def test_on_progress_called_for_each_stage(tmp_path, monkeypatch):
    """每个阶段开始时调用 on_progress，顺序正确"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))
    events: list[str] = []
    pipeline = _make_pipeline(on_progress=events.append)
    pipeline.run("https://example.com/v", task_id="my_task_002")
    assert events == [
        "downloading", "transcribing", "segmenting", "detecting", "fusing",
    ]


def test_on_progress_exception_does_not_break_pipeline(tmp_path, monkeypatch):
    """回调抛异常不影响流水线"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))

    def bad_callback(status: str) -> None:
        raise RuntimeError("boom")

    pipeline = _make_pipeline(on_progress=bad_callback)
    result = pipeline.run("https://example.com/v", task_id="my_task_003")
    assert result.status == TaskStatus.DONE
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_pipeline_progress.py -v`
Expected: FAIL — `TypeError: Pipeline.__init__() got an unexpected keyword argument 'on_progress'`

- [ ] **Step 3: 实现最小改动**

`core/pipeline.py` 三处修改：

(1) `__init__` 签名末尾加参数并保存（`log_file` 之后）：

```python
        log_file: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        ...
        self._on_progress = on_progress
```

顶部 import 补 `Callable`：`from typing import Callable, Optional`

(2) 新增 `_notify` 方法，并在 `_run_internal` 每个阶段开头调用：

```python
    def _notify(self, status: TaskStatus) -> None:
        """通知外部当前阶段（回调异常不影响流水线）"""
        if self._on_progress is None:
            return
        try:
            self._on_progress(status.value)
        except Exception as e:
            logger.warning("进度回调异常: {}", e)
```

`_run_internal` 中在各阶段 `logger.info` 之前插入：
- 下载前：`self._notify(TaskStatus.DOWNLOADING)`
- 转写前：`self._notify(TaskStatus.TRANSCRIBING)`
- 语义分镜前：`self._notify(TaskStatus.SEGMENTING)`
- 场景检测前：`self._notify(TaskStatus.DETECTING)`
- 融合前：`self._notify(TaskStatus.FUSING)`

(3) `run()` 接受外部 task_id：

```python
    def run(self, url: str, task_id: Optional[str] = None) -> TaskResult:
        task_id = task_id or generate_task_id()
```

（方法体其余不变，删除原来的 `task_id = generate_task_id()` 行）

- [ ] **Step 4: 运行测试确认通过 + 回归**

Run: `pytest tests/test_pipeline_progress.py tests/test_pipeline.py -v`
Expected: 全部 PASS（现有 test_pipeline.py 不受影响）

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline_progress.py
git commit -m "feat: pipeline 支持进度回调与外部 task_id（向后兼容）"
```

---

## Task 2: config.py 服务端配置扩展

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`（追加）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_config.py` 末尾）

```python
def test_server_config_defaults():
    """服务端配置字段有合理默认值"""
    from config import AppConfig

    cfg = AppConfig(_env_file=None)
    assert cfg.jwt_secret == ""
    assert cfg.jwt_expire_hours == 72
    assert cfg.db_path.endswith("app.db")
    assert cfg.video_ttl_days == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_config.py::test_server_config_defaults -v`
Expected: FAIL — `AttributeError: 'AppConfig' object has no attribute 'jwt_secret'`

- [ ] **Step 3: 实现**（`config.py` 的 `AppConfig` 类中，`model_config` 之前追加）

```python
    # ====== 服务端 ======
    jwt_secret: str = Field(
        "", description="JWT 签名密钥（生产环境必须在 .env 中设置强随机值）"
    )
    jwt_expire_hours: int = Field(72, description="JWT 有效期（小时）")
    db_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).resolve().parent / "server" / "app.db"
        ),
        description="SQLite 数据库文件路径",
    )
    video_ttl_days: int = Field(3, description="视频/音频文件保留天数")
```

同时在 `.env`（不提交）和 `.env.example`（如无则创建）中加：

```
JWT_SECRET=请改成强随机字符串

# 服务器部署必填：数据与代码分离，代码目录可随意更新/重建而不丢数据
# 本地开发可不设置（默认落在项目目录内）
# DB_PATH=/data/douyin-agent/app.db
# OUTPUT_BASE_DIR=/data/douyin-agent/output
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py .env.example
git commit -m "feat: 新增服务端配置（jwt_secret/db_path/video_ttl_days）"
```

---

## Task 3: server/database.py — SQLAlchemy 模型与会话

**Files:**
- Create: `server/__init__.py`（空文件）
- Create: `server/database.py`
- Test: `tests/test_server_db.py`

- [ ] **Step 1: 更新依赖并安装**

`requirements.txt` 追加：

```
# 服务端
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
pyjwt>=2.8.0
bcrypt>=4.0.0
apscheduler>=3.10.0
httpx>=0.27.0
```

Run: `pip install -r requirements.txt`
Expected: 安装成功

- [ ] **Step 2: 写失败测试**

```python
"""tests/test_server_db.py — 数据库模型与会话"""

from server import database
from server.database import Task, User, init_db


def test_init_db_creates_tables(tmp_path):
    """init_db 建表后可写入并读回 User 和 Task"""
    init_db(str(tmp_path / "test.db"))
    session = database.SessionLocal()
    try:
        session.add(User(username="alice", password_hash="hash"))
        session.add(Task(id="t1", user_id=1, url="https://example.com"))
        session.commit()

        user = session.query(User).filter(User.username == "alice").first()
        assert user is not None
        assert user.id == 1

        task = session.get(Task, "t1")
        assert task.status == "pending"
        assert task.scenes_count == 0
        assert task.created_at != ""
    finally:
        session.close()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_server_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 4: 实现**

创建空文件 `server/__init__.py`，然后创建 `server/database.py`：

```python
"""SQLAlchemy 模型与会话管理"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import config


class Base(DeclarativeBase):
    """ORM 基类"""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class User(Base):
    """用户表（管理员用脚本创建，无公开注册）"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(32), default=_now_iso)


class Task(Base):
    """任务元数据表（分镜内容仍在 output/{task_id}/result.json）"""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    scenes_count: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[str] = mapped_column(String(32), default=_now_iso)


_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def init_db(db_path: str | None = None) -> Engine:
    """初始化数据库引擎并建表（幂等）"""
    global _engine, SessionLocal
    path = db_path or config.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False
    )
    Base.metadata.create_all(_engine)
    return _engine
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_server_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/__init__.py server/database.py tests/test_server_db.py requirements.txt
git commit -m "feat: SQLite 数据库层（User/Task 模型 + 会话管理）"
```

---

## Task 4: server/auth.py — 密码哈希与 JWT

**Files:**
- Create: `server/auth.py`
- Test: `tests/test_server_auth.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_server_auth.py — 密码哈希与 JWT"""

import jwt as pyjwt
import pytest

from server.auth import create_token, decode_token, hash_password, verify_password


def test_hash_and_verify_password():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_with_invalid_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_create_and_decode_token(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    token = create_token(user_id=42, username="bob")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["username"] == "bob"


def test_decode_invalid_token_raises(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token("garbage.token.here")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_server_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.auth'`

- [ ] **Step 3: 实现** `server/auth.py`：

```python
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


def create_token(user_id: int, username: str) -> str:
    """签发 JWT"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=config.jwt_expire_hours),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解析 JWT，失败抛 jwt.InvalidTokenError（含过期）"""
    return jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_server_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/auth.py tests/test_server_auth.py
git commit -m "feat: JWT 签发校验与 bcrypt 密码哈希"
```

---

## Task 5: 登录接口与鉴权依赖

**Files:**
- Create: `server/deps.py`
- Create: `server/routes/__init__.py`（空文件）
- Create: `server/routes/auth_routes.py`
- Test: `tests/test_auth_routes.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_auth_routes.py — 登录接口与鉴权依赖"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server import database
from server.auth import hash_password
from server.database import User, init_db
from server.deps import get_current_user
from server.routes.auth_routes import router as auth_router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    init_db(str(tmp_path / "test.db"))
    session = database.SessionLocal()
    session.add(User(username="alice", password_hash=hash_password("pw123")))
    session.commit()
    session.close()

    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/api/whoami")
    def whoami(user: User = Depends(get_current_user)) -> dict:
        return {"username": user.username}

    return TestClient(app)


def test_login_success(client):
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["user"]["username"] == "alice"


def test_login_wrong_password(client):
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "nope"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "ghost", "password": "pw123"}
    )
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/whoami").status_code == 401


def test_protected_route_with_bearer_token(client):
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw123"}
    ).json()["token"]
    resp = client.get("/api/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_protected_route_with_query_token(client):
    """SSE/视频/导出链接无法带 header，支持 ?token= 传递"""
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw123"}
    ).json()["token"]
    resp = client.get(f"/api/whoami?token={token}")
    assert resp.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_auth_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.deps'`

- [ ] **Step 3: 实现**

创建空文件 `server/routes/__init__.py`。

`server/deps.py`：

```python
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
```

`server/routes/auth_routes.py`：

```python
"""认证路由：登录"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth import create_token, verify_password
from server.database import User
from server.deps import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """账号密码登录，返回 JWT 与用户信息"""
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "token": create_token(user.id, user.username),
        "user": {"id": user.id, "username": user.username},
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_auth_routes.py -v`
Expected: PASS（6 个测试）

- [ ] **Step 5: Commit**

```bash
git add server/deps.py server/routes/ tests/test_auth_routes.py
git commit -m "feat: 登录接口与 JWT 鉴权依赖（支持 header 与 query token）"
```

---

## Task 6: services/task_queue.py — 内存 FIFO 队列

**Files:**
- Create: `server/services/__init__.py`（空文件）
- Create: `server/services/task_queue.py`
- Test: `tests/test_task_queue.py`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_task_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services'`

- [ ] **Step 3: 实现**

创建空文件 `server/services/__init__.py`。

`server/services/task_queue.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_task_queue.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 5: Commit**

```bash
git add server/services/ tests/test_task_queue.py
git commit -m "feat: 内存 FIFO 任务队列（串行 worker + 订阅发布进度）"
```

---

## Task 7: 任务路由 — 创建/列表/详情

**Files:**
- Create: `server/routes/task_routes.py`
- Test: `tests/test_task_routes.py`

- [ ] **Step 1: 写失败测试**

```python
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
        "/api/tasks", json={"url": "https://v.douyin.com/xyz/"},
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
    resp = client.post("/api/tasks", json={"url": "  "}, headers=_auth(1, "alice"))
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
        "task_id": task_id, "status": "done", "title": "", "url": "https://a/",
        "scenes": [{
            "index": 0, "start_time": 0.0, "end_time": 5.0,
            "summary": "开场", "text": "大家好", "has_scene_cut": True,
        }],
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_task_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.routes.task_routes'`

- [ ] **Step 3: 实现** `server/routes/task_routes.py`：

```python
"""任务路由：创建、列表、详情（后续任务追加 SSE/视频/导出/删除）"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
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
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_task_routes.py -v`
Expected: PASS（5 个测试）

- [ ] **Step 5: Commit**

```bash
git add server/routes/task_routes.py tests/test_task_routes.py
git commit -m "feat: 任务创建/列表/详情接口（按用户隔离）"
```

---

## Task 8: SSE 实时进度流

**Files:**
- Modify: `server/routes/task_routes.py`
- Test: `tests/test_task_routes.py`（追加）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_task_routes.py`）

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_task_routes.py -k stream -v`
Expected: FAIL — 404（路由不存在）

- [ ] **Step 3: 实现**（追加到 `server/routes/task_routes.py`）

顶部补 import：

```python
import queue as queue_mod

from fastapi.responses import StreamingResponse
```

追加常量与路由：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_task_routes.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add server/routes/task_routes.py tests/test_task_routes.py
git commit -m "feat: SSE 任务实时进度流"
```

---

## Task 9: 视频文件服务与删除任务

**Files:**
- Modify: `server/routes/task_routes.py`
- Test: `tests/test_task_routes.py`（追加）

- [ ] **Step 1: 写失败测试**（追加）

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_task_routes.py -k "video or delete" -v`
Expected: FAIL（404/405，路由不存在）

- [ ] **Step 3: 实现**（追加到 `server/routes/task_routes.py`）

顶部补 import：

```python
from fastapi.responses import FileResponse, StreamingResponse

from utils.file_helpers import cleanup_task, generate_task_id, get_task_paths
```

追加路由：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_task_routes.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add server/routes/task_routes.py tests/test_task_routes.py
git commit -m "feat: 视频文件服务与任务删除接口"
```

---

## Task 10: utils/exporters.py — SRT/Markdown/CSV 导出

**Files:**
- Create: `utils/exporters.py`
- Test: `tests/test_exporters.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_exporters.py — 分镜导出格式"""

from models.schemas import FusedScene
from utils.exporters import scenes_to_csv, scenes_to_markdown, scenes_to_srt

SCENES = [
    FusedScene(index=0, start_time=0.0, end_time=25.5,
               summary="开场", text="大家好", has_scene_cut=True),
    FusedScene(index=1, start_time=25.5, end_time=61.02,
               summary="产品介绍", text="这是新品", has_scene_cut=False),
]


def test_scenes_to_srt_format():
    srt = scenes_to_srt(SCENES)
    blocks = srt.strip().split("\n\n")
    assert len(blocks) == 2
    assert blocks[0].splitlines() == [
        "1", "00:00:00,000 --> 00:00:25,500", "大家好",
    ]
    assert "00:00:25,500 --> 00:01:01,020" in blocks[1]


def test_scenes_to_markdown_contains_title_and_rows():
    md = scenes_to_markdown(SCENES, title="发布会")
    assert md.startswith("# 发布会")
    assert "| 1 | 00:00 | 00:25 | 开场 | 大家好 |" in md


def test_scenes_to_csv_has_header_and_rows():
    rows = scenes_to_csv(SCENES).strip().splitlines()
    assert rows[0] == "序号,开始时间,结束时间,摘要,文字内容"
    assert rows[1].startswith("1,0.0,25.5,开场")
    assert len(rows) == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_exporters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.exporters'`

- [ ] **Step 3: 实现** `utils/exporters.py`：

```python
"""分镜导出工具：SRT / Markdown / CSV / 视频片段"""

import csv
import io
import subprocess
import zipfile
from pathlib import Path

from models.schemas import FusedScene


def _fmt_srt_time(seconds: float) -> str:
    """秒 → SRT 时间格式 HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_mmss(seconds: float) -> str:
    """秒 → MM:SS"""
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def scenes_to_srt(scenes: list[FusedScene]) -> str:
    blocks = [
        f"{i}\n{_fmt_srt_time(sc.start_time)} --> {_fmt_srt_time(sc.end_time)}\n{sc.text}"
        for i, sc in enumerate(scenes, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


def scenes_to_markdown(scenes: list[FusedScene], title: str = "分镜稿") -> str:
    lines = [
        f"# {title}",
        "",
        "| 序号 | 开始 | 结束 | 摘要 | 文字内容 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sc in scenes:
        text = sc.text.replace("|", "\\|").replace("\n", " ")
        summary = sc.summary.replace("|", "\\|")
        lines.append(
            f"| {sc.index + 1} | {_fmt_mmss(sc.start_time)} "
            f"| {_fmt_mmss(sc.end_time)} | {summary} | {text} |"
        )
    return "\n".join(lines) + "\n"


def scenes_to_csv(scenes: list[FusedScene]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["序号", "开始时间", "结束时间", "摘要", "文字内容"])
    for sc in scenes:
        writer.writerow(
            [sc.index + 1, sc.start_time, sc.end_time, sc.summary, sc.text]
        )
    return buf.getvalue()


def export_clips(video_path: str, scenes: list[FusedScene], out_dir: str) -> str:
    """用 ffmpeg 按分镜切割视频并打包 zip，返回 zip 路径

    -c copy 不重编码，速度快；切点可能有 ±1 关键帧误差，剪辑师可接受。
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for sc in scenes:
        clip_path = Path(out_dir) / f"scene_{sc.index + 1:02d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(sc.start_time), "-to", str(sc.end_time),
            "-i", video_path, "-c", "copy", str(clip_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    zip_path = Path(out_dir) / "clips.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sorted(Path(out_dir).glob("scene_*.mp4")):
            zf.write(f, f.name)
    return str(zip_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_exporters.py -v`
Expected: PASS（`export_clips` 依赖真实 ffmpeg，不做单测，由 Task 11 的路由测试 mock 覆盖 + 最终 E2E 验证）

- [ ] **Step 5: Commit**

```bash
git add utils/exporters.py tests/test_exporters.py
git commit -m "feat: 分镜导出工具（SRT/Markdown/CSV/视频片段）"
```

---

## Task 11: 导出路由

**Files:**
- Modify: `server/routes/task_routes.py`
- Test: `tests/test_task_routes.py`（追加）

- [ ] **Step 1: 写失败测试**（追加）

```python
def _make_done_task(client, headers) -> str:
    """创建一个已完成、带 result.json 的任务，返回 task_id"""
    from utils.file_helpers import ensure_dir, get_task_paths

    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=headers
    ).json()["task_id"]
    session = database.SessionLocal()
    session.get(Task, task_id).status = "done"
    session.commit()
    session.close()

    paths = get_task_paths(task_id)
    ensure_dir(paths.task_dir)
    result = {
        "task_id": task_id, "status": "done", "title": "测试视频",
        "url": "https://a/",
        "scenes": [{
            "index": 0, "start_time": 0.0, "end_time": 5.0,
            "summary": "开场", "text": "大家好", "has_scene_cut": True,
        }],
        "error_message": None,
    }
    with open(paths.result_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    return task_id


def test_export_srt(env):
    client, _ = env
    task_id = _make_done_task(client, _auth(1, "alice"))
    resp = client.get(
        f"/api/tasks/{task_id}/export?format=srt", headers=_auth(1, "alice")
    )
    assert resp.status_code == 200
    assert "00:00:00,000 --> 00:00:05,000" in resp.text
    assert "attachment" in resp.headers["content-disposition"]


def test_export_md_and_csv(env):
    client, _ = env
    task_id = _make_done_task(client, _auth(1, "alice"))
    md = client.get(
        f"/api/tasks/{task_id}/export?format=md", headers=_auth(1, "alice")
    )
    assert md.status_code == 200 and "| 开场 |" in md.text
    csv_resp = client.get(
        f"/api/tasks/{task_id}/export?format=csv", headers=_auth(1, "alice")
    )
    assert csv_resp.status_code == 200 and "序号" in csv_resp.text


def test_export_unknown_format_returns_422(env):
    client, _ = env
    task_id = _make_done_task(client, _auth(1, "alice"))
    resp = client.get(
        f"/api/tasks/{task_id}/export?format=docx", headers=_auth(1, "alice")
    )
    assert resp.status_code == 422


def test_export_unfinished_task_returns_409(env):
    client, _ = env
    task_id = client.post(
        "/api/tasks", json={"url": "https://a/"}, headers=_auth(1, "alice")
    ).json()["task_id"]
    resp = client.get(
        f"/api/tasks/{task_id}/export?format=srt", headers=_auth(1, "alice")
    )
    assert resp.status_code == 409


def test_export_clips_calls_ffmpeg_helper(env, monkeypatch):
    """clips 导出调用 export_clips 并返回 zip 文件"""
    from server.routes import task_routes
    from utils.file_helpers import get_task_paths

    client, _ = env
    task_id = _make_done_task(client, _auth(1, "alice"))
    paths = get_task_paths(task_id)
    Path(paths.video_dir).mkdir(parents=True, exist_ok=True)
    Path(paths.original_video).write_bytes(b"fake")

    def fake_export_clips(video_path: str, scenes, out_dir: str) -> str:
        zip_path = Path(out_dir) / "clips.zip"
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(b"PK-fake-zip")
        return str(zip_path)

    monkeypatch.setattr(task_routes, "export_clips", fake_export_clips)
    resp = client.get(
        f"/api/tasks/{task_id}/export?format=clips", headers=_auth(1, "alice")
    )
    assert resp.status_code == 200
    assert resp.content == b"PK-fake-zip"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_task_routes.py -k export -v`
Expected: FAIL（404，路由不存在）

- [ ] **Step 3: 实现**（追加到 `server/routes/task_routes.py`）

顶部补 import：

```python
from urllib.parse import quote

from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from models.schemas import FusedScene
from utils.exporters import (
    export_clips,
    scenes_to_csv,
    scenes_to_markdown,
    scenes_to_srt,
)
```

追加路由：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_task_routes.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add server/routes/task_routes.py tests/test_task_routes.py
git commit -m "feat: 分镜导出接口（SRT/MD/CSV/视频片段 zip）"
```

---

## Task 12: services/cleaner.py — 3 天 TTL 视频清理

**Files:**
- Create: `server/services/cleaner.py`
- Test: `tests/test_cleaner.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_cleaner.py — 过期视频清理"""

import os
import time
from pathlib import Path

from server.services.cleaner import cleanup_expired_videos


def _make_task_dir(base: Path, task_id: str, age_days: float) -> Path:
    """构造带 video/audio/result.json 的任务目录，并把 mtime 调旧"""
    task_dir = base / task_id
    for sub in ("video", "audio"):
        (task_dir / sub).mkdir(parents=True)
        (task_dir / sub / "f.bin").write_bytes(b"x")
    (task_dir / "result.json").write_text("{}", encoding="utf-8")
    old = time.time() - age_days * 86400
    for sub in ("video", "audio"):
        os.utime(task_dir / sub, (old, old))
    return task_dir


def test_removes_expired_media_keeps_result(tmp_path):
    task_dir = _make_task_dir(tmp_path, "old_task", age_days=5)
    removed = cleanup_expired_videos(base_dir=str(tmp_path), ttl_days=3)
    assert removed == 2
    assert not (task_dir / "video").exists()
    assert not (task_dir / "audio").exists()
    assert (task_dir / "result.json").exists()


def test_keeps_fresh_media(tmp_path):
    task_dir = _make_task_dir(tmp_path, "new_task", age_days=1)
    removed = cleanup_expired_videos(base_dir=str(tmp_path), ttl_days=3)
    assert removed == 0
    assert (task_dir / "video").exists()


def test_missing_base_dir_returns_zero(tmp_path):
    assert cleanup_expired_videos(
        base_dir=str(tmp_path / "nope"), ttl_days=3
    ) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cleaner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.cleaner'`

- [ ] **Step 3: 实现** `server/services/cleaner.py`：

```python
"""过期媒体文件清理：删除超过 TTL 的 video/ 与 audio/ 目录

只删媒体大文件，保留 result.json 和 intermediate/，
用户仍可查看分镜结果，只是视频不能再播放/导出。
"""

import shutil
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from config import config

CLEANUP_INTERVAL_HOURS = 6


def cleanup_expired_videos(
    base_dir: str | None = None, ttl_days: int | None = None
) -> int:
    """删除过期任务的 video/audio 目录，返回删除的目录数"""
    base = Path(base_dir or config.output_base_dir)
    ttl = ttl_days if ttl_days is not None else config.video_ttl_days
    cutoff = time.time() - ttl * 86400
    if not base.exists():
        return 0
    removed = 0
    for task_dir in base.iterdir():
        if not task_dir.is_dir():
            continue
        for sub in ("video", "audio"):
            target = task_dir / sub
            if target.exists() and target.stat().st_mtime < cutoff:
                shutil.rmtree(target, ignore_errors=True)
                removed += 1
                logger.info("清理过期媒体: {}", target)
    return removed


def start_scheduler() -> BackgroundScheduler:
    """启动后台定时清理（每 6 小时一次，启动时立即跑一次）"""
    cleanup_expired_videos()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        cleanup_expired_videos, "interval", hours=CLEANUP_INTERVAL_HOURS
    )
    scheduler.start()
    return scheduler
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cleaner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/cleaner.py tests/test_cleaner.py
git commit -m "feat: 视频 3 天 TTL 自动清理（APScheduler）"
```

---

## Task 13: server/main.py 组装 + 建号脚本

**Files:**
- Create: `server/main.py`
- Create: `scripts/create_user.py`
- Test: `tests/test_main_app.py`

- [ ] **Step 1: 写失败测试**

```python
"""tests/test_main_app.py — 应用组装与 SPA 回退"""

from fastapi.testclient import TestClient

from server.main import create_app


def test_app_includes_api_routes():
    app = create_app()
    paths = {r.path for r in app.routes}
    assert "/api/auth/login" in paths
    assert "/api/tasks" in paths
    assert "/api/tasks/{task_id}/stream" in paths


def test_api_404_stays_json(tmp_path, monkeypatch):
    """API 未匹配路径不应被 SPA 回退吞掉"""
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    from server.database import init_db

    init_db(str(tmp_path / "t.db"))
    client = TestClient(create_app())  # 不用 with，不触发 lifespan
    resp = client.get("/api/nonexistent")
    assert resp.status_code in (401, 404)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_main_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.main'`

- [ ] **Step 3: 实现**

`server/main.py`：

```python
"""FastAPI 应用入口

启动方式：uvicorn server.main:app --host 0.0.0.0 --port 7860
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from config import config
from server.database import init_db
from server.routes.auth_routes import router as auth_router
from server.routes.task_routes import router as task_router
from server.services.cleaner import start_scheduler
from server.services.task_queue import task_queue

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置，请在 .env 中设置强随机值")
    init_db()
    task_queue.start()
    scheduler = start_scheduler()
    logger.info("服务已启动，前端目录: {}", FRONTEND_DIST)
    yield
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="视频分镜分析", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(task_router)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """静态文件 + SPA history 路由回退（/api 已被上面的路由优先匹配）"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        if not FRONTEND_DIST.exists():
            raise HTTPException(
                status_code=404,
                detail="前端未构建，请先执行 cd frontend && npm run build",
            )
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
```

`scripts/create_user.py`：

```python
"""创建用户账号（管理员手动执行，无公开注册）

用法：python scripts/create_user.py <用户名> <密码>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import database
from server.auth import hash_password
from server.database import User, init_db


def main() -> None:
    if len(sys.argv) != 3:
        print("用法: python scripts/create_user.py <用户名> <密码>")
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 6:
        print("密码至少 6 位")
        sys.exit(1)
    init_db()
    session = database.SessionLocal()
    try:
        exists = session.query(User).filter(User.username == username).first()
        if exists is not None:
            print(f"用户 {username} 已存在")
            sys.exit(1)
        session.add(User(username=username, password_hash=hash_password(password)))
        session.commit()
        print(f"用户 {username} 创建成功")
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过 + 手动冒烟**

Run: `pytest tests/test_main_app.py -v`
Expected: PASS

冒烟（.env 中先设置 `JWT_SECRET=dev-secret`）：

```bash
python scripts/create_user.py admin admin123
uvicorn server.main:app --port 7860
```

另开终端验证：
`curl -X POST http://127.0.0.1:7860/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'`
Expected: 返回 `{"token": "...", "user": {...}}`

- [ ] **Step 5: 运行全量测试 + Commit**

Run: `pytest tests/ -v --cov=server --cov=utils --cov-report=term-missing`
Expected: 全部 PASS，server/ 覆盖率 ≥ 80%

```bash
git add server/main.py scripts/create_user.py tests/test_main_app.py
git commit -m "feat: FastAPI 应用组装（lifespan/SPA回退）+ 建号脚本"
```

---

## Task 14: 前端 API 层 + 登录接真实接口

**Files:**
- Create: `frontend/src/api/client.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/views/LoginPage.vue`（登录调用改异步错误处理，若已是则不动）
- Modify: `frontend/vite.config.js`（加 /api 代理）

- [ ] **Step 1: 创建 API 客户端** `frontend/src/api/client.js`：

```javascript
// 统一 API 客户端：自动带 token，401 统一跳登录
const BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  let res
  try {
    res = await fetch(BASE + path, { ...options, headers })
  } catch {
    throw new Error('网络连接失败，请检查服务是否在线')
  }
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `请求失败 (${res.status})`)
  }
  return res.json()
}

function tokenQuery() {
  return `token=${encodeURIComponent(localStorage.getItem('token') || '')}`
}

export const api = {
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  listTasks: () => request('/tasks'),
  createTask: (url) =>
    request('/tasks', { method: 'POST', body: JSON.stringify({ url }) }),
  getTask: (id) => request(`/tasks/${id}`),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
  // EventSource / <video> / 下载链接无法带 header，用 query token
  streamUrl: (id) => `${BASE}/tasks/${id}/stream?${tokenQuery()}`,
  videoUrl: (id) => `${BASE}/tasks/${id}/video?${tokenQuery()}`,
  exportUrl: (id, format) =>
    `${BASE}/tasks/${id}/export?format=${format}&${tokenQuery()}`,
}
```

- [ ] **Step 2: auth store 接真实 API**（重写 `frontend/src/stores/auth.js` 的 login）

```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('token') || '')

  async function login(username, password) {
    if (!username || !password) {
      throw new Error('用户名和密码不能为空')
    }
    const data = await api.login(username, password)
    user.value = data.user
    token.value = data.token
    localStorage.setItem('user', JSON.stringify(data.user))
    localStorage.setItem('token', data.token)
    return data.user
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('user')
    localStorage.removeItem('token')
  }

  return { user, token, login, logout }
})
```

检查 `LoginPage.vue` 中调用 `auth.login(...)` 的地方：确保用 `try/catch` 或 `.catch()` 把 `err.message` 显示给用户（原型中如已有错误提示则确认文案生效）。

- [ ] **Step 3: vite 代理**（`frontend/vite.config.js` 的 `defineConfig` 中加）

```javascript
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:7860',
    },
  },
```

- [ ] **Step 4: 浏览器验证**

```bash
# 终端1（.env 已有 JWT_SECRET）
uvicorn server.main:app --port 7860
# 终端2
cd frontend && npm run dev
```

浏览器打开 `http://localhost:5173/login`：
- 用 `admin/admin123` 登录 → 跳转 /dashboard
- 用错误密码登录 → 显示"用户名或密码错误"

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.js frontend/src/stores/auth.js frontend/src/views/LoginPage.vue frontend/vite.config.js
git commit -m "feat: 前端 API 客户端 + 登录接真实接口"
```

---

## Task 15: Dashboard 与新建任务接 API + SSE

**Files:**
- Modify: `frontend/src/views/DashboardPage.vue`
- Modify: `frontend/src/components/NewTaskModal.vue`

- [ ] **Step 1: DashboardPage 换掉 mock**（`<script setup>` 部分改为）

```javascript
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import NewTaskModal from '../components/NewTaskModal.vue'
import AppLayout from '../components/AppLayout.vue'

const router = useRouter()
const message = useMessage()

const searchQuery = ref('')
const statusFilter = ref('all')
const showNewTask = ref(false)
const tasks = ref([])
const loading = ref(true)

// 后端细分状态归并为前端 4 类
const PROCESSING = ['downloading', 'transcribing', 'detecting', 'segmenting', 'fusing']
function displayStatus(s) {
  if (PROCESSING.includes(s)) return 'processing'
  return s // pending / done / error
}

const statusLabel = { done: '已完成', processing: '处理中', error: '失败', pending: '排队中' }
const statusColor = { done: 'oklch(0.58 0.16 160)', processing: 'oklch(0.62 0.165 60)', error: 'oklch(0.52 0.20 25)', pending: 'oklch(0.68 0.005 105)' }

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await api.listTasks()
  } catch (err) {
    message.error(err.message)
  } finally {
    loading.value = false
  }
}
onMounted(loadTasks)

const filteredTasks = computed(() => {
  return tasks.value.filter(t => {
    const ds = displayStatus(t.status)
    const matchStatus = statusFilter.value === 'all' || ds === statusFilter.value
    const matchSearch = !searchQuery.value || (t.title || '').includes(searchQuery.value) || t.url.includes(searchQuery.value)
    return matchStatus && matchSearch
  })
})

function formatDuration(s) {
  if (!s) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

function viewResult(task) {
  if (task.status === 'done') router.push(`/result/${task.id}`)
}

async function deleteTask(task) {
  try {
    await api.deleteTask(task.id)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
    message.success('任务已删除')
  } catch (err) {
    message.error(err.message)
  }
}

function onTaskCreated() {
  showNewTask.value = false
  loadTasks()
}
```

模板改动点：
- 状态点/标签处把 `task.status` 换成 `displayStatus(task.status)`：`statusColor[displayStatus(task.status)]`、`statusLabel[displayStatus(task.status)]`
- 任务列表前加 loading 态：`<div v-if="loading" class="text-center py-20 text-sm" style="color: oklch(0.68 0.005 105)">加载中...</div>`，原空状态改为 `v-else-if="filteredTasks.length === 0"`，列表改为 `v-else`

- [ ] **Step 2: NewTaskModal 接 API + SSE**（`<script setup>` 逻辑部分改为）

```javascript
import { ref, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'

const emit = defineEmits(['close', 'created'])
const message = useMessage()
const url = ref('')
const submitted = ref(false)
const currentStep = ref(0)
const errorMsg = ref('')
const elapsed = ref([0, 0, 0, 0])
let es = null
let tick = null

const steps = [
  { key: 'download', label: '下载视频', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
  { key: 'transcribe', label: '语音转写', icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m2-4a2 2 0 01-2-2V6a2 2 0 012-2h4a2 2 0 012 2v8a2 2 0 01-2 2h-4z' },
  { key: 'segment', label: '语义分镜', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { key: 'done', label: '完成', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
]

// 后端状态 → 步骤索引
const STATUS_STEP = {
  pending: 0, downloading: 0,
  transcribing: 1,
  detecting: 2, segmenting: 2, fusing: 2,
  done: 3,
}

async function submit() {
  if (!url.value.trim()) return
  submitted.value = true
  errorMsg.value = ''
  try {
    const { task_id } = await api.createTask(url.value.trim())
    tick = setInterval(() => { elapsed.value[currentStep.value]++ }, 1000)
    es = new EventSource(api.streamUrl(task_id))
    es.onmessage = (ev) => {
      const { status } = JSON.parse(ev.data)
      if (status === 'error') {
        errorMsg.value = '分析失败，请检查链接是否有效'
        cleanup()
        return
      }
      currentStep.value = STATUS_STEP[status] ?? currentStep.value
      if (status === 'done') {
        cleanup()
        emit('created', task_id)
      }
    }
    es.onerror = () => {
      // SSE 断开（如服务重启）：不报错，提示用户到列表查看
      cleanup()
      emit('created', task_id)
    }
  } catch (err) {
    submitted.value = false
    message.error(err.message)
  }
}

function cleanup() {
  if (es) { es.close(); es = null }
  if (tick) { clearInterval(tick); tick = null }
}

function formatElapsed(s) {
  if (!s) return ''
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m > 0 ? `${m}分${sec}秒` : `${sec}秒`
}

onUnmounted(cleanup)
```

模板改动点：进度区块底部加错误显示：

```html
<p v-if="errorMsg" class="text-center text-sm mt-4" style="color: oklch(0.52 0.20 25)">
  {{ errorMsg }}
  <button class="underline ml-2" @click="emit('close')">关闭</button>
</p>
```

- [ ] **Step 3: 浏览器验证**

后端 + 前端 dev server 都在跑的状态下：
- Dashboard 显示真实任务列表（首次为空态）
- 新建任务粘贴一条真实抖音链接 → 弹窗步骤随 SSE 推进（下载→转写→分镜→完成）
- 完成后回到列表，出现新任务，可删除

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/DashboardPage.vue frontend/src/components/NewTaskModal.vue
git commit -m "feat: 工作台与新建任务接真实 API + SSE 实时进度"
```

---

## Task 16: ResultPage 接 API + 视频播放 + 导出

**Files:**
- Modify: `frontend/src/views/ResultPage.vue`

- [ ] **Step 1: 换掉 mock 数据**（`<script setup>` 数据部分改为）

```javascript
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import AppLayout from '../components/AppLayout.vue'
import TimelineBar from '../components/TimelineBar.vue'
import SceneCard from '../components/SceneCard.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const taskId = route.params.id
const currentIndex = ref(-1)
const loading = ref(true)
const videoEl = ref(null)
const taskResult = ref({ title: '', url: '', status: '', scenes: [] })

onMounted(async () => {
  try {
    const data = await api.getTask(taskId)
    taskResult.value = {
      title: data.title || '未命名任务',
      url: data.url,
      status: data.status,
      scenes: data.scenes_detail || [],
    }
  } catch (err) {
    message.error(err.message)
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
})

const videoSrc = api.videoUrl(taskId)

const totalDuration = computed(() => {
  const scenes = taskResult.value.scenes
  if (!scenes.length) return 0
  return scenes[scenes.length - 1].end_time - scenes[0].start_time
})

function selectScene(index) {
  currentIndex.value = index
  const scene = taskResult.value.scenes[index]
  if (videoEl.value && scene) {
    videoEl.value.currentTime = scene.start_time
    videoEl.value.play().catch(() => {})
  }
  const card = document.getElementById(`scene-${index}`)
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function highlightTimeline(index) {
  currentIndex.value = index
  const scene = taskResult.value.scenes[index]
  if (videoEl.value && scene) {
    videoEl.value.currentTime = scene.start_time
  }
}

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function exportFormat(format) {
  window.open(api.exportUrl(taskId, format), '_blank')
}

function downloadVideo() {
  window.open(api.videoUrl(taskId), '_blank')
}

function backToDashboard() {
  router.push('/dashboard')
}
```

- [ ] **Step 2: 模板中占位播放器换成真实 `<video>`**

把原「视频播放器」占位区块替换为：

```html
<div class="glass rounded-2xl overflow-hidden mb-6">
  <video
    ref="videoEl"
    :src="videoSrc"
    controls
    class="w-full aspect-video"
    style="background: oklch(0.12 0.005 105)"
  ></video>
</div>
```

- [ ] **Step 3: 浏览器验证**

对一条已完成的真实任务：
- 结果页正常加载分镜卡片与时间轴（数据来自 API）
- 视频可播放、可拖动进度条（Range 请求）
- 点击时间轴色块 → 视频跳到对应 start_time 且卡片滚动定位
- 导出 SRT/MD/CSV 各下载一次，打开确认内容正确；视频片段导出得到 zip
- 「视频」按钮可下载完整视频

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ResultPage.vue
git commit -m "feat: 结果页接真实 API（视频播放/时间轴联动/导出下载）"
```

---

## Task 17: 生产构建 + E2E 验证 + 文档

**Files:**
- Create: `test_e2e_server.py`（Playwright，项目根目录，与现有 test_playwright.py 同风格）
- Modify: `README.md`（部署章节）
- Modify: `.gitignore`（排除 `server/app.db`、`frontend/dist/`、`frontend/node_modules/`，如已排除则跳过）

- [ ] **Step 1: 前端生产构建 + FastAPI 托管验证**

```bash
cd frontend && npm run build && cd ..
uvicorn server.main:app --port 7860
```

浏览器打开 `http://127.0.0.1:7860/`：
- 落地页正常渲染（静态资源无 404）
- 直接访问 `http://127.0.0.1:7860/dashboard` 刷新不 404（SPA 回退生效）
- 登录 → 工作台 → 结果页全链路可用

- [ ] **Step 2: 写 Playwright E2E**（`test_e2e_server.py`，运行前先建好 `e2e_user/e2e_pass123` 账号并启动服务）

```python
"""端到端测试：登录 → 工作台 → 登出

运行前提：
1. python scripts/create_user.py e2e_user e2e_pass123
2. 前端已 build，uvicorn server.main:app --port 7860 已启动
运行：PYTHONIOENCODING=utf-8 python test_e2e_server.py
"""

from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:7860"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # 未登录访问 dashboard → 重定向到 /login
        page.goto(f"{BASE}/dashboard")
        page.wait_for_url("**/login")

        # 错误密码 → 留在登录页
        page.fill('input[type="text"]', "e2e_user")
        page.fill('input[type="password"]', "wrong")
        page.click('button[type="submit"]')
        page.wait_for_timeout(1000)
        assert "/login" in page.url

        # 正确登录 → 进入工作台
        page.fill('input[type="password"]', "e2e_pass123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard")
        expect(page.locator("h1")).to_contain_text("工作台")

        browser.close()
        print("E2E 全部通过")


if __name__ == "__main__":
    main()
```

注意：登录表单的选择器需与 `LoginPage.vue` 实际 DOM 对照，若输入框没有 `type="password"`/`type="submit"`，先给组件补上语义属性再写选择器。

Run: `PYTHONIOENCODING=utf-8 python test_e2e_server.py`
Expected: 输出「E2E 全部通过」

- [ ] **Step 3: README 部署章节**（追加到 `README.md`）

```markdown
## 部署（FastAPI + Vue 版本）

### 数据与代码分离（服务器必读）

代码是无状态的，可随意 `git pull` 更新或整目录重建；数据必须放在代码目录之外：

```bash
sudo mkdir -p /data/douyin-agent/output
```

`.env` 中配置（不设置则默认落在项目目录内，仅限本地开发）：

```
DB_PATH=/data/douyin-agent/app.db
OUTPUT_BASE_DIR=/data/douyin-agent/output
```

备份：SQLite 备份就是拷贝 `app.db` 一个文件，建议定时拷到其他机器。

### 首次部署

1. `pip install -r requirements.txt`
2. `cd frontend && npm install && npm run build && cd ..`
3. `.env` 中配置：`JWT_SECRET`（强随机值）、`DEEPSEEK_API_KEY`、`DOUYIN_COOKIE`、`DB_PATH`、`OUTPUT_BASE_DIR`
   - 2核4G 服务器建议再加 `WHISPER_MODEL_SIZE=tiny`
4. 创建账号：`python scripts/create_user.py <用户名> <密码>`
5. 启动：`uvicorn server.main:app --host 0.0.0.0 --port 7860`

### 更新代码

```bash
git pull
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
# 重启 uvicorn 即可，/data 下的数据库和视频不受影响
```

### 说明

- 任务串行执行（内存 FIFO 队列），服务重启后进行中/排队任务不会恢复，需重新提交
- 视频/音频文件保留 3 天后自动清理（`VIDEO_TTL_DAYS` 可调），分镜结果永久保留
- 旧版 Gradio 入口 `python app.py` 仍可用，与新服务互不影响
```

- [ ] **Step 4: 全量回归 + Commit**

```bash
pytest tests/ -v --cov=server --cov=utils --cov=core --cov-report=term-missing
ruff check server/ utils/exporters.py scripts/create_user.py
```

Expected: 测试全部 PASS，覆盖率 ≥ 80%，ruff 无告警

```bash
git add test_e2e_server.py README.md .gitignore
git commit -m "feat: 生产构建托管 + E2E 测试 + 部署文档"
```

---

## 收尾

全部任务完成后触发 `requesting-code-review`（含 security-reviewer 安全审计：JWT、鉴权隔离、路径拼接），通过后走 `verification-before-completion` 与 `finishing-a-development-branch`。
