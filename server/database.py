"""SQLAlchemy 模型与会话管理"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, Float, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import config


class Base(DeclarativeBase):
    """ORM 基类"""


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串（精确到秒）"""
    return datetime.now().isoformat(timespec="seconds")


class User(Base):
    """用户表（管理员用脚本创建，无公开注册）"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    is_admin: Mapped[bool] = mapped_column(default=False)
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

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection, connection_record
    ) -> None:
        """启用 WAL 模式：读不阻塞写、写不阻塞读（多线程并发必需）"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False
    )
    Base.metadata.create_all(_engine)

    # 迁移：为已有数据库补加 is_admin 列
    try:
        with _engine.connect() as conn:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            conn.commit()
    except Exception:
        pass  # 列已存在则跳过

    # 首个用户自动成为管理员
    session = SessionLocal()
    try:
        first_user = session.query(User).filter(User.id == 1).first()
        if first_user and not first_user.is_admin:
            first_user.is_admin = True
            session.commit()
    finally:
        session.close()

    return _engine
