"""文件操作工具函数"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from config import config


def generate_task_id() -> str:
    """生成唯一任务 ID

    格式：YYYYMMDD_HHMMSS_XXXXX（时间戳 + 随机后缀）
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    random_suffix = str(uuid.uuid4().hex)[:5]
    return f"{timestamp}_{random_suffix}"


def ensure_dir(path: str) -> str:
    """确保目录存在，不存在则创建"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


class TaskPaths:
    """任务路径集合"""

    def __init__(self, task_id: str, base_dir: str):
        self.task_id: str = task_id
        self.task_dir: str = str(Path(base_dir) / task_id)
        self.video_dir: str = str(Path(self.task_dir) / "video")
        self.audio_dir: str = str(Path(self.task_dir) / "audio")
        self.intermediate_dir: str = str(Path(self.task_dir) / "intermediate")

    @property
    def original_video(self) -> str:
        return str(Path(self.video_dir) / "original.mp4")

    @property
    def audio_file(self) -> str:
        return str(Path(self.audio_dir) / "audio.wav")

    @property
    def whisper_raw(self) -> str:
        return str(Path(self.intermediate_dir) / "whisper_raw.json")

    @property
    def scene_cuts_raw(self) -> str:
        return str(Path(self.intermediate_dir) / "scene_cuts_raw.json")

    @property
    def semantic_raw(self) -> str:
        return str(Path(self.intermediate_dir) / "semantic_raw.json")

    @property
    def result_json(self) -> str:
        return str(Path(self.task_dir) / "result.json")

    @property
    def report_md(self) -> str:
        return str(Path(self.task_dir) / "report.md")


def get_task_paths(
    task_id: str,
    base_dir: str | None = None,
) -> TaskPaths:
    """获取任务相关所有路径"""
    actual_base = base_dir or config.output_base_dir
    return TaskPaths(task_id, actual_base)


def cleanup_task(
    task_id: str,
    base_dir: str | None = None,
) -> None:
    """清理任务目录

    文件被占用时静默跳过，残留目录由人工或后续清理处理。
    """
    actual_base = base_dir or config.output_base_dir
    task_dir = Path(actual_base) / task_id
    if task_dir.exists():
        shutil.rmtree(str(task_dir), ignore_errors=True)
