"""语音转写模块

使用 faster-whisper 将音频转写为文字，附带字级时间戳。
"""

import os
import threading
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment]

from config import config
from models.schemas import WhisperResult, WordTimestamp


class Transcriber:
    """faster-whisper 语音转写器"""

    _model_cache: dict[str, "WhisperModel"] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_size = model_size or config.whisper_model_size
        self.device = device or config.whisper_device
        # GPU 用 float16 加速，CPU 用 int8 节省内存
        self._compute_type = "float16" if self.device and "cuda" in self.device else "int8"

    def _get_model(self) -> "WhisperModel":
        """获取或加载 Whisper 模型（线程安全缓存）"""
        cache_key = f"{self.model_size}:{self.device}:{self._compute_type}"
        if cache_key not in self._model_cache:
            with self._lock:
                if cache_key not in self._model_cache:
                    logger.info("加载 Whisper 模型: {} ({}, {})", self.model_size, self.device, self._compute_type)
                    self._model_cache[cache_key] = WhisperModel(
                        self.model_size, device=self.device, compute_type=self._compute_type,
                    )
        return self._model_cache[cache_key]

    def transcribe(self, audio_path: str) -> WhisperResult:
        """转写音频文件为文字

        Args:
            audio_path: 音频文件路径

        Returns:
            WhisperResult 包含全文、字级时间戳和时长

        Raises:
            FileNotFoundError: 音频文件不存在
            RuntimeError: 模型加载或转写失败
        """
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if WhisperModel is None:
            raise RuntimeError("faster-whisper 未安装")

        logger.info("开始转写: {}", audio_path)

        # 设置 HF_ENDPOINT（线程安全：try/finally 保证恢复原始值）
        old_endpoint = os.environ.get("HF_ENDPOINT")
        if config.hf_endpoint:
            os.environ["HF_ENDPOINT"] = config.hf_endpoint
        try:
            model = self._get_model()
        except Exception as e:
            logger.error("模型加载失败: {}", e)
            raise RuntimeError(f"模型加载失败: {e}") from e
        finally:
            if config.hf_endpoint:
                if old_endpoint:
                    os.environ["HF_ENDPOINT"] = old_endpoint
                else:
                    os.environ.pop("HF_ENDPOINT", None)

        try:
            segments, info = model.transcribe(
                audio_path, word_timestamps=True, language="zh",
            )
        except Exception as e:
            logger.error("转写失败: {}", e)
            raise RuntimeError(f"转写失败: {e}") from e

        text_parts: list[str] = []
        word_timestamps: list[WordTimestamp] = []
        try:
            for segment in segments:
                text_parts.append(segment.text)
                if segment.words:
                    for word in segment.words:
                        word_timestamps.append(
                            WordTimestamp(
                                word=word.word,
                                start=word.start,
                                end=word.end,
                            )
                        )
        except Exception as e:
            logger.error("转写失败: {}", e)
            raise RuntimeError(f"转写失败: {e}") from e

        result = WhisperResult(
            text="".join(text_parts),
            segments=word_timestamps,
            duration=info.duration,
        )
        logger.info("转写成功: {} 字, {:.2f} 秒", len(result.text), result.duration)
        return result


def transcribe_audio(
    audio_path: str,
    model_size: Optional[str] = None,
    device: Optional[str] = None,
) -> WhisperResult:
    """快捷函数：转写音频文件"""
    transcriber = Transcriber(model_size=model_size, device=device)
    return transcriber.transcribe(audio_path)
