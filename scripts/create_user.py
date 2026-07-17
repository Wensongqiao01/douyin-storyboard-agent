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
