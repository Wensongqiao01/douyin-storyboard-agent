"""语义分镜模块

使用 DeepSeek API 对文本进行语义分段，识别逻辑上的场景切换。
"""

import json
from typing import Union

from loguru import logger
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment]

from config import config
from models.schemas import SemanticResult, SemanticSegment, WhisperResult


class Segmenter:
    """DeepSeek 语义分镜器"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.deepseek_api_key
        self.model = model or config.deepseek_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_deepseek(self, text: str):
        """调用 DeepSeek API（带自动重试）"""
        if not self.api_key:
            raise RuntimeError(
                "DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY"
            )
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        return client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个视频文本语义分镜助手。请将视频的解说文本按语义分成多个段落，并返回 JSON 格式的结果。请务必使用简体中文输出。",
                },
                {
                    "role": "user",
                    "content": f"""请将以下文本按语义进行分段，返回 JSON 格式结果。

文本：
{text}

请返回如下 JSON 格式（不要包含其他内容）：
{{
    "segments": [
        {{
            "index": 0,
            "summary": "段落摘要",
            "start_text": "段落起始文字",
            "end_text": "段落结束文字"
        }}
    ]
}}""",
                },
            ],
        )

    def segment(self, text_or_result: Union[str, WhisperResult]) -> SemanticResult:
        """对文本进行语义分镜

        Args:
            text_or_result: 输入文本或 WhisperResult 对象

        Returns:
            SemanticResult 包含语义分镜列表

        Raises:
            ValueError: 文本为空
            RuntimeError: API 调用失败
        """
        text = (
            text_or_result.text
            if isinstance(text_or_result, WhisperResult)
            else text_or_result
        )
        if not text.strip():
            raise ValueError("文本不能为空")

        if OpenAI is None:
            raise RuntimeError("openai 未安装")

        logger.info("开始语义分镜: {} 字", len(text))
        try:
            response = self._call_deepseek(text)
        except Exception as e:
            logger.error("语义分镜失败: {}", e)
            raise RuntimeError(f"语义分镜失败: {e}") from e

        try:
            data = json.loads(response.choices[0].message.content)
            segments = []
            for seg_data in data["segments"]:
                # 补全缺失字段（不可变方式：创建新字典而非修改原数据）
                seg_fixed = {
                    **seg_data,
                    "end_text": seg_data.get("end_text") or seg_data.get("start_text", ""),
                }
                segments.append(SemanticSegment(**seg_fixed))
            return SemanticResult(segments=segments)
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as e:
            logger.warning("语义分镜解析失败，回退为单个分镜: {}", e)
            return SemanticResult(
                segments=[
                    SemanticSegment(
                        index=0,
                        summary="全文",
                        start_text=text,
                        end_text=text,
                    )
                ]
            )


def segment_text(
    text: str,
    api_key: str | None = None,
    model: str | None = None,
) -> SemanticResult:
    """快捷函数：对文本进行语义分镜"""
    segmenter = Segmenter(api_key=api_key, model=model)
    return segmenter.segment(text)
