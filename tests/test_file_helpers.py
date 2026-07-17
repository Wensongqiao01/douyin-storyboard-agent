"""测试文件操作工具"""
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from utils.file_helpers import (
    generate_task_id,
    ensure_dir,
    TaskPaths,
    get_task_paths,
    cleanup_task,
)


class TestGenerateTaskId:
    """测试任务 ID 生成"""

    def test_generates_unique_ids(self):
        """测试生成唯一 ID"""
        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100

    def test_contains_timestamp(self):
        """测试 ID 包含时间信息"""
        task_id = generate_task_id()
        # 格式: YYYYMMDD_HHMMSS_XXXXX
        parts = task_id.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # 日期部分
        assert len(parts[1]) == 6  # 时间部分
        assert len(parts[2]) == 5  # 随机部分


class TestEnsureDir:
    """测试目录创建"""

    def test_creates_directory(self, tmp_path):
        """测试创建新目录"""
        test_dir = tmp_path / "new_dir" / "nested"
        assert not test_dir.exists()
        result = ensure_dir(str(test_dir))
        assert test_dir.exists()
        assert result == str(test_dir)

    def test_existing_directory(self, tmp_path):
        """测试已存在目录不报错"""
        test_dir = tmp_path / "existing"
        test_dir.mkdir(parents=True)
        result = ensure_dir(str(test_dir))
        assert test_dir.exists()


class TestTaskPaths:
    """测试任务路径管理"""

    def test_task_paths_structure(self, tmp_path):
        """测试任务路径结构正确"""
        task_id = "test-001"
        paths = get_task_paths(task_id, base_dir=str(tmp_path))

        assert isinstance(paths, TaskPaths)
        assert paths.task_id == task_id
        assert paths.task_dir == str(tmp_path / task_id)
        assert paths.video_dir == str(tmp_path / task_id / "video")
        assert paths.audio_dir == str(tmp_path / task_id / "audio")
        assert paths.intermediate_dir == str(tmp_path / task_id / "intermediate")

    def test_original_video_path(self, tmp_path):
        """测试原始视频路径"""
        paths = get_task_paths("test-001", base_dir=str(tmp_path))
        assert paths.original_video.endswith(".mp4")
        assert "original" in paths.original_video

    def test_audio_path(self, tmp_path):
        """测试音频文件路径"""
        paths = get_task_paths("test-001", base_dir=str(tmp_path))
        assert paths.audio_file.endswith(".wav")

    def test_result_json_path(self, tmp_path):
        """测试结果 JSON 路径"""
        paths = get_task_paths("test-001", base_dir=str(tmp_path))
        assert paths.result_json.endswith("result.json")

    def test_default_base_dir(self):
        """测试默认 base_dir 使用配置"""
        from config import config
        paths = get_task_paths("test-001")
        # 应使用 config.output_base_dir 作为前缀
        assert paths.task_dir.endswith("test-001")


class TestCleanupTask:
    """测试任务清理"""

    def test_removes_task_directory(self, tmp_path):
        """测试删除任务目录"""
        task_id = "to-delete"
        # 先创建任务路径
        get_task_paths(task_id, base_dir=str(tmp_path))
        # 创建一些文件
        task_dir = tmp_path / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "test.txt").write_text("hello")

        cleanup_task(task_id, base_dir=str(tmp_path))
        assert not task_dir.exists()

    def test_cleanup_nonexistent_task(self):
        """测试清理不存在的任务不报错"""
        cleanup_task("nonexistent")  # 不应抛出异常

    def test_cleanup_tolerates_locked_files(self, tmp_path):
        """测试 cleanup_task 传递 ignore_errors=True 给 rmtree"""
        task_id = "locked-task"
        task_dir = tmp_path / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "video.mp4").write_text("simulated video content")

        with patch.object(shutil, "rmtree") as mock_rmtree:
            cleanup_task(task_id, base_dir=str(tmp_path))
            mock_rmtree.assert_called_once_with(
                str(task_dir), ignore_errors=True
            )
