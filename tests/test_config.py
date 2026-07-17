"""测试配置模块"""
import os
from typing import Generator

import pytest
from config import AppConfig


@pytest.fixture(autouse=True)
def _clear_deepseek_env() -> Generator[None, None, None]:
    """测试前清除 DEEPSEEK_API_KEY 环境变量，避免 .env 干扰"""
    old = os.environ.pop("DEEPSEEK_API_KEY", None)
    yield
    if old is not None:
        os.environ["DEEPSEEK_API_KEY"] = old


class TestAppConfig:
    """测试 AppConfig 配置类"""

    def test_default_values(self):
        """测试默认值正确"""
        config = AppConfig(_env_file=None)
        assert config.whisper_model_size == "base"
        assert config.whisper_device == "cpu"
        assert config.deepseek_model == "deepseek-chat"
        assert config.scene_detect_threshold == 30.0
        assert config.output_base_dir.endswith("output")
        assert os.path.isabs(config.output_base_dir)
        assert config.fuse_align_window == 1.0
        assert config.export_scene_clips is False

    def test_empty_sensitive_defaults(self):
        """测试敏感字段默认值为空"""
        config = AppConfig(_env_file=None)
        assert config.douyin_cookie == ""
        assert config.deepseek_api_key == ""

    def test_custom_values_override(self):
        """测试自定义值覆盖默认值"""
        config = AppConfig(
            whisper_model_size="base",
            whisper_device="cuda",
            scene_detect_threshold=20.0,
            export_scene_clips=True,
        )
        assert config.whisper_model_size == "base"
        assert config.whisper_device == "cuda"
        assert config.scene_detect_threshold == 20.0
        assert config.export_scene_clips is True

    def test_output_base_dir_custom(self):
        """测试输出目录自定义"""
        config = AppConfig(output_base_dir="/tmp/output")
        assert config.output_base_dir == "/tmp/output"

    def test_fuse_align_window_zero(self):
        """测试融合窗口为0的边界情况"""
        config = AppConfig(fuse_align_window=0.0)
        assert config.fuse_align_window == 0.0


def test_server_config_defaults():
    """服务端配置字段有合理默认值"""
    from config import AppConfig

    cfg = AppConfig(_env_file=None)
    assert cfg.jwt_secret == ""
    assert cfg.jwt_expire_hours == 72
    assert cfg.db_path.endswith("app.db")
    assert cfg.video_ttl_days == 3
