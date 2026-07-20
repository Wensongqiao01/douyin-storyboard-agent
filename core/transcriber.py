"""语音转写模块

使用阿里云百炼 Fun-ASR 将音频转写为文字，附带字级时间戳。
相比本地 Whisper：速度从分钟级降到秒级，不消耗服务器 CPU。
"""

import time
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

try:
    from dashscope.utils.oss_utils import OssUtils
except ImportError:
    OssUtils = None  # type: ignore[assignment]

try:
    import zhconv
except ImportError:
    zhconv = None
    logger.warning("zhconv 未安装，繁体中文不会自动转换为简体中文")

from config import config
from models.schemas import TranscribedSegment, WhisperResult, WordTimestamp

# API 端点：优先使用业务空间独立端点，否则回退到旧通用端点
if config.bailian_workspace_id:
    API_BASE = f"https://{config.bailian_workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
else:
    API_BASE = "https://dashscope.aliyuncs.com/api/v1"
SUBMIT_URL = f"{API_BASE}/services/audio/asr/transcription"
QUERY_URL = f"{API_BASE}/tasks/{{task_id}}"


class Transcriber:
    """阿里云百炼 Fun-ASR 语音转写器

    每月 10 小时免费额度（自动续），超量 ~0.29 元/小时。
    API 调用全云端完成，不消耗本地 CPU。
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.api_key = config.bailian_api_key
        if not self.api_key:
            raise RuntimeError(
                "BAILIAN_API_KEY 未配置，请在 .env 中设置阿里云百炼 API Key"
            )
        if OssUtils is None:
            raise RuntimeError("dashscope 未安装，请执行 pip install dashscope")

    def transcribe(self, audio_path: str) -> WhisperResult:
        """转写音频文件为文字"""
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info("上传音频到 OSS: {}", audio_path)
        oss_url = self._upload(audio_path)
        logger.info("OSS 上传成功")

        logger.info("提交 Fun-ASR 识别任务")
        task_id = self._submit_task(oss_url)
        logger.info("等待识别完成, task_id={}", task_id)

        trans_json = self._wait_and_download(task_id)
        logger.info(
            "识别成功: {} 句, {} ms",
            len(trans_json.get("transcripts", [{}])[0].get("sentences", [])),
            trans_json.get("transcripts", [{}])[0].get(
                "content_duration_in_milliseconds", 0
            ),
        )
        return self._to_result(trans_json)

    def _submit_task(self, oss_url: str) -> str:
        """提交异步识别任务，返回 task_id"""
        params: dict = {"channel_id": [0], "language_hints": ["zh", "en"]}
        if config.asr_diarization_enabled:
            params["diarization_enabled"] = True
        resp = httpx.post(
            SUBMIT_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
                "X-DashScope-OssResourceResolve": "enable",
            },
            json={
                "model": "fun-asr",
                "input": {"file_urls": [oss_url]},
                "parameters": params,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"提交任务失败: {resp.status_code} {resp.text}")
        data = resp.json()
        task_id = data.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"提交任务返回无 task_id: {data}")
        return task_id

    def _wait_and_download(self, task_id: str) -> dict:
        """轮询任务状态，完成后下载识别结果 JSON"""
        for _ in range(360):
            time.sleep(3)
            resp = httpx.get(
                QUERY_URL.format(task_id=task_id),
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"查询任务失败: {resp.status_code}")
            data = resp.json()
            task_status = data.get("output", {}).get("task_status")
            if task_status == "FAILED":
                raise RuntimeError(f"识别任务失败: {data}")
            if task_status == "SUCCEEDED":
                results = data["output"]["results"]
                if not results:
                    raise RuntimeError("识别返回空结果")
                entry = results[0]
                if entry.get("subtask_status") != "SUCCEEDED":
                    raise RuntimeError(f"识别子任务失败: {entry}")
                trans_url = entry["transcription_url"]
                trans_resp = httpx.get(trans_url, timeout=30)
                return trans_resp.json()
        raise TimeoutError(f"识别任务超时: {task_id}")

    def _upload(self, audio_path: str) -> str:
        """上传音频到 DashScope OSS，返回 oss:// URL"""
        oss_url, _ = OssUtils.upload(
            model="fun-asr",
            file_path=audio_path,
            api_key=self.api_key,
        )
        if not oss_url:
            raise RuntimeError(f"OSS 上传失败: {audio_path}")
        return oss_url

    def _to_result(self, data: dict) -> WhisperResult:
        """Fun-ASR 识别结果 → WhisperResult（保持下游兼容）"""
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
                    speaker_id=sent.get("speaker_id"),
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
