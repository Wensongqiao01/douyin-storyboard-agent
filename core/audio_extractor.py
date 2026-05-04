"""音频提取模块

使用 ffmpeg-python 从视频文件中提取音频，输出 WAV 格式。
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import ffmpeg
except ImportError:
    ffmpeg = None  # type: ignore[assignment]

from config import config
from utils.file_helpers import ensure_dir


class AudioExtractor:
    """ffmpeg 音频提取器"""

    _path_fixed = False  # 类级别标记，确保 PATH 只修改一次

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        if not AudioExtractor._path_fixed:
            self._ensure_ffmpeg_command()
            AudioExtractor._path_fixed = True

    @staticmethod
    def _ensure_ffmpeg_command() -> None:
        """确保 ffmpeg-python 能找到 ffmpeg 可执行文件"""
        import shutil
        # shutil.which 能搜到当前目录，但 subprocess.Popen 搜不到
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path and os.path.isabs(ffmpeg_path):
            return
        # 在项目根目录查找 ffmpeg.exe
        project_root = Path(__file__).resolve().parent.parent
        local_ffmpeg = project_root / "ffmpeg.exe"
        if local_ffmpeg.exists():
            os.environ["PATH"] = str(project_root) + os.pathsep + os.environ.get("PATH", "")
            logger.info("已添加 ffmpeg.exe 到 PATH: {}", local_ffmpeg)
        else:
            logger.warning("未找到 ffmpeg.exe，请确保 ffmpeg 已安装并添加到 PATH")

    def extract(self, video_path: str, output_path: str) -> str:
        """从视频中提取音频

        Args:
            video_path: 输入视频文件路径
            output_path: 输出音频文件路径（.wav）

        Returns:
            输出音频文件路径

        Raises:
            FileNotFoundError: 视频文件不存在
            RuntimeError: ffmpeg 处理失败
        """
        if ffmpeg is None:
            raise RuntimeError("ffmpeg-python 未安装")

        if not Path(video_path).exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        logger.info("开始提取音频: {} -> {}", video_path, output_path)
        try:
            stream = ffmpeg.input(video_path)
            stream = stream.output(
                output_path,
                acodec="pcm_s16le",
                ac=1,
                ar=str(self.sample_rate),
                loglevel="error",
            )
            stream.run(overwrite_output=True)
        except Exception as e:
            logger.error("音频提取失败: {}", e)
            raise RuntimeError(f"音频提取失败: {e}") from e

        logger.info("音频提取成功: {}", output_path)
        return output_path


def extract_audio(
    video_path: str,
    output_dir: Optional[str] = None,
    sample_rate: int = 16000,
) -> str:
    """快捷函数：从视频提取音频到指定目录

    Args:
        video_path: 输入视频文件路径
        output_dir: 输出目录，默认使用 config.output_base_dir
        sample_rate: 音频采样率

    Returns:
        输出音频文件路径
    """
    if output_dir:
        ensure_dir(output_dir)
        output_path = str(Path(output_dir) / "audio.wav")
    else:
        output_path = str(
            Path(config.output_base_dir) / "temp" / "audio.wav"
        )
        ensure_dir(str(Path(output_path).parent))

    extractor = AudioExtractor(sample_rate=sample_rate)
    return extractor.extract(video_path, output_path)
