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
