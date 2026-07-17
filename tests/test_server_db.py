"""tests/test_server_db.py — 数据库模型与会话测试"""

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
