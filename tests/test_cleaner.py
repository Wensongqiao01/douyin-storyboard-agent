"""tests/test_cleaner.py — 过期视频清理"""

import os
import time
from pathlib import Path

from server.services.cleaner import cleanup_expired_videos


def _make_task_dir(base: Path, task_id: str, age_days: float) -> Path:
    """构造带 video/audio/clips/result.json 的任务目录，并把 mtime 调旧"""
    task_dir = base / task_id
    for sub in ("video", "audio", "clips"):
        (task_dir / sub).mkdir(parents=True)
        (task_dir / sub / "f.bin").write_bytes(b"x")
    (task_dir / "result.json").write_text("{}", encoding="utf-8")
    old = time.time() - age_days * 86400
    for sub in ("video", "audio", "clips"):
        os.utime(task_dir / sub, (old, old))
    return task_dir


def test_removes_expired_media_keeps_result(tmp_path):
    task_dir = _make_task_dir(tmp_path, "old_task", age_days=5)
    removed = cleanup_expired_videos(base_dir=str(tmp_path), ttl_days=3)
    assert removed == 3
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
