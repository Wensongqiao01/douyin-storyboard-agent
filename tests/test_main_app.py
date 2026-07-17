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


def test_spa_cannot_escape_dist(tmp_path, monkeypatch):
    """路径遍历攻击无法读取 FRONTEND_DIST 之外的文件"""
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    from server.database import init_db
    from server.main import create_app

    # 构造测试目录树:
    #   tmp_path/
    #     dist/
    #       index.html   (合法前端文件)
    #     sentinel.txt   (应被隔离的哨兵文件)
    dist_root = tmp_path / "dist"
    dist_root.mkdir(parents=True)
    INDEX_CONTENT = "<html>index</html>"
    (dist_root / "index.html").write_text(INDEX_CONTENT, encoding="utf-8")

    sentinel = tmp_path / "sentinel.txt"
    SENTINEL_CONTENT = "SECRET_FILE_CONTENT"
    sentinel.write_text(SENTINEL_CONTENT, encoding="utf-8")

    monkeypatch.setattr("server.main.FRONTEND_DIST", dist_root)
    init_db(str(tmp_path / "test_spa.db"))
    client = TestClient(create_app())

    # 1) 正常请求应返回合法文件
    resp = client.get("/index.html")
    assert resp.status_code == 200
    assert resp.text == INDEX_CONTENT

    # 2) 各种路径遍历向量均应返回 index.html，绝不泄漏哨兵
    # 注意：TestClient/httpx 会归一化 raw `..`（/../foo → /foo），
    # 但 URL 编码变体（%2f=%2e%2e%2f）会正确解码为 `../` 并通过。
    for path in [
        # URL 编码变体——TestClient 解码后含 `..`，走真实验证
        "..%2fsentinel.txt",
        "%2e%2e%2fsentinel.txt",
        "..%2f..%2f..%2fsentinel.txt",
        "a%2f..%2f..%2f..%2fsentinel.txt",
        # raw `..`——会被 TestClient 归一化，不构成路径遍历测试，但确保不崩溃
        "../sentinel.txt",
        "a/../../sentinel.txt",
    ]:
        resp = client.get(f"/{path}")
        assert resp.status_code == 200, f"路径 '{path}' 应为 200，实际 {resp.status_code}"
        assert resp.text == INDEX_CONTENT, f"路径 '{path}' 应返回 index.html 内容"
        assert SENTINEL_CONTENT not in resp.text, f"路径 '{path}' 泄漏了哨兵内容！"
