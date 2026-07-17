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
