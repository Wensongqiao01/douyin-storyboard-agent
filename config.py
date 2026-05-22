"""应用配置

所有配置集中管理，通过 pydantic-settings 支持 .env 文件覆盖。
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


def _default_max_workers() -> int:
    """根据 CPU 核心数计算安全的并行数

    Ryzen 7 7840HS (8C/16T) 上 Whisper CPU 推理约需 2-3 核心/实例，
    公式：max(2, cpu_count // 6)，确保每个实例有充足 CPU 资源。
    16 // 6 = 2，8C 以上系统最多 4 路。
    """
    cores = os.cpu_count() or 4
    return max(2, min(cores // 6, 4))


class AppConfig(BaseSettings):
    """应用全局配置"""

    # ====== 平台相关 ======
    douyin_cookie: str = Field("", description="抖音 cookie，用于视频下载")

    # ====== 模型相关 ======
    whisper_model_size: str = Field("base", description="Whisper 模型大小")
    whisper_device: str = Field("cpu", description="Whisper 运行设备（cpu/cuda）")
    hf_endpoint: str = Field("", description="HuggingFace Hub 镜像地址（国内用户设为 https://hf-mirror.com）")

    # ====== API 相关 ======
    deepseek_api_key: str = Field("", description="DeepSeek API Key")
    deepseek_model: str = Field("deepseek-chat", description="DeepSeek 模型名")

    # ====== PySceneDetect ======
    scene_detect_threshold: float = Field(30.0, description="场景检测灵敏度")

    # ====== 路径相关 ======
    output_base_dir: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parent / "output"),
        description="输出根目录",
    )

    # ====== 融合逻辑 ======
    fuse_align_window: float = Field(
        1.0, description="语义边界匹配场景切点的窗口大小（秒）"
    )

    # ====== 超时控制 ======
    pipeline_timeout: int = Field(
        600, description="单条流水线超时时间（秒），0 表示不超时"
    )

    # ====== 批量处理 ======
    max_workers: int = Field(
        default_factory=_default_max_workers,
        description="批量处理最大并行数（根据 CPU 核心数自动计算）",
    )

    # ====== 场景切片 ======
    export_scene_clips: bool = Field(
        False, description="是否导出场景切片视频文件"
    )

    model_config = {
        "env_file": str(Path(__file__).resolve().parent / ".env"),
        "env_file_encoding": "utf-8",
    }


config = AppConfig()
