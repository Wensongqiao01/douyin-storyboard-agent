"""Cookie 池 — 多用户轮询使用不同 cookie 下载视频，降低单号风控风险"""

import threading
from pathlib import Path
from typing import Optional

from loguru import logger


class CookiePool:
    """线程安全的 cookie 轮询池

    从 cookies.txt 读取，每行一个 cookie，跳过空行和注释行。
    轮询策略：Round-Robin，每次调用 next() 返回下一个 cookie。
    """

    def __init__(self, pool_file: str = "cookies.txt") -> None:
        self._file = Path(pool_file)
        self._cookies: list[str] = []
        self._index = 0
        self._lock = threading.Lock()
        self._reload()

    def _reload(self) -> None:
        """从文件重新加载 cookie 列表"""
        cookies: list[str] = []
        if self._file.exists():
            for line in self._file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    cookies.append(line)
        self._cookies = cookies
        if self._index >= max(len(cookies), 1):
            self._index = 0

    def next(self) -> Optional[str]:
        """轮询返回下一个 cookie，无可用时返回 None"""
        with self._lock:
            if not self._cookies:
                return None
            cookie = self._cookies[self._index]
            self._index = (self._index + 1) % len(self._cookies)
            return cookie

    @property
    def count(self) -> int:
        return len(self._cookies)

    def reload(self) -> None:
        """手动重新加载（热更新 cookie 文件）"""
        with self._lock:
            self._reload()
        logger.info("Cookie 池已重新加载，当前 {} 条", self.count)


# 全局单例
pool = CookiePool("cookies.txt")
