"""语音转写模块

使用阿里云百炼 Paraformer-v2 将音频转写为文字，附带字级时间戳。
相比本地 Whisper：速度从分钟级降到秒级，不消耗服务器 CPU。
"""

import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

try:
    import zhconv
except ImportError:
    zhconv = None
    logger.warning("zhconv 未安装，繁体中文不会自动转换为简体中文")

try:
    import dashscope
    from dashscope.audio.asr import Transcription
except ImportError:
    dashscope = None  # type: ignore
    Transcription = None  # type: ignore

from config import config
from models.schemas import TranscribedSegment, WhisperResult, WordTimestamp


class Transcriber:
    """阿里云百炼 Paraformer-v2 语音转写器

    每月 10 小时免费额度（自动续），超量 ~0.29 元/小时。
    API 调用全云端完成，不消耗本地 CPU。
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
    ):
        # 保留旧 Whisper 参数签名以兼容，但不再使用
        self.api_key = config.bailian_api_key
        if not self.api_key:
            raise RuntimeError(
                "BAILIAN_API_KEY 未配置，请在 .env 中设置阿里云百炼 API Key"
            )
        if dashscope is None:
            raise RuntimeError("dashscope 未安装，请执行 pip install dashscope")
        dashscope.api_key = self.api_key

    def transcribe(self, audio_path: str) -> WhisperResult:
        """转写音频文件为文字

        Args:
            audio_path: 音频文件路径（本地 WAV 文件）

        Returns:
            WhisperResult 包含全文、字级时间戳和时长
        """
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info("上传音频到 OSS: {}", audio_path)
        oss_url = self._upload(audio_path)
        logger.info("OSS 上传成功")

        logger.info("提交 Paraformer 识别任务")
        task = Transcription.async_call(
            model="paraformer-v2",
            file_urls=[oss_url],
            language_hints=["zh", "en"],
        )

        logger.info("等待识别完成, task_id={}", task.output.task_id)
        response = Transcription.wait(task=task.output.task_id)
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"语音识别失败: code={response.code} message={response.message}"
            )

        # 下载详细结果 JSON
        results = response.output.get("results", [])
        if not results:
            raise RuntimeError("语音识别返回空结果")
        result_entry = results[0]
        if result_entry.get("subtask_status") == "FAILED":
            raise RuntimeError(f"语音识别子任务失败: {result_entry}")

        trans_url = result_entry["transcription_url"]
        trans_json = httpx.get(trans_url).json()

        logger.info(
            "识别成功: {} 句, {} ms",
            len(trans_json.get("transcripts", [{}])[0].get("sentences", [])),
            trans_json.get("transcripts", [{}])[0].get(
                "content_duration_in_milliseconds", 0
            ),
        )

        return self._to_result(trans_json)

    def _upload(self, audio_path: str) -> str:
        """上传音频到 dashscope 管理的 OSS，返回文件 URL"""
        result = subprocess.run(
            [
                "dashscope",
                "oss.upload",
                "--model",
                "paraformer-v2",
                "--file",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"音频上传失败: {result.stderr or result.stdout}")
        url = result.stdout.strip()
        if not url:
            raise RuntimeError("OSS 上传未返回 URL")
        return url

    def _to_result(self, data: dict) -> WhisperResult:
        """Paraformer 识别结果 → WhisperResult（保持下游兼容）"""
        transcript = data["transcripts"][0]
        duration_ms = transcript.get("content_duration_in_milliseconds", 0)

        words: list[WordTimestamp] = []
        paragraphs: list[TranscribedSegment] = []
        text_parts: list[str] = []

        for sent in transcript.get("sentences", []):
            sent_text = sent["text"]
            text_parts.append(sent_text)
            paragraphs.append(
                TranscribedSegment(
                    text=self._simplify(sent_text),
                    start=sent["begin_time"] / 1000,
                    end=sent["end_time"] / 1000,
                )
            )
            for w in sent.get("words", []):
                words.append(
                    WordTimestamp(
                        word=self._simplify(w["text"]),
                        start=w["begin_time"] / 1000,
                        end=w["end_time"] / 1000,
                    )
                )

        return WhisperResult(
            text=self._simplify("".join(text_parts)),
            segments=words,
            paragraphs=paragraphs,
            duration=duration_ms / 1000,
        )

    @staticmethod
    def _simplify(text: str) -> str:
        """繁体→简体"""
        if zhconv:
            return zhconv.convert(text, "zh-hans")
        return text


def transcribe_audio(
    audio_path: str,
    model_size: Optional[str] = None,
    device: Optional[str] = None,
) -> WhisperResult:
    """快捷函数：转写音频文件"""
    transcriber = Transcriber(model_size=model_size, device=device)
    return transcriber.transcribe(audio_path)
