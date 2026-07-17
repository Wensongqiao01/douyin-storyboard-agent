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
        for sub in ("video", "audio", "clips"):
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
