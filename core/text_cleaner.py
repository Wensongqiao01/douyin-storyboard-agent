"""文本清洗模块

使用 DeepSeek API 纠正 Whisper 语音识别中的同音字错误、漏字、多字等问题，
在融合完成后对最终输出的分镜文本进行后处理。
"""

import json
import re

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment]

from config import config
from models.schemas import FusedScene


class TextCleaner:
    """DeepSeek 文本清洗器

    在 fuser 完成融合对齐后，对每个分镜的 text 字段进行纠错。
    API 失败时静默保留原始文本，不影响流水线正常运行。
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.deepseek_api_key
        self.model = model or config.deepseek_model

    def clean(self, scenes: list[FusedScene]) -> list[FusedScene]:
        """清洗所有分镜的文本

        Args:
            scenes: 融合后的分镜列表

        Returns:
            清洗后文本的分镜列表（API 失败时返回原始列表）
        """
        if not scenes:
            return []

        original_texts = [s.text for s in scenes]
        if not any(t.strip() for t in original_texts):
            return scenes

        logger.info("开始 DeepSeek 文本清洗: {} 个分镜", len(scenes))

        try:
            corrected = self._call_deepseek(original_texts)
        except Exception as e:
            logger.warning("文本清洗失败，已保留原始文本: {}", e)
            return scenes

        # 容错：返回数量不匹配时截断/补齐
        if len(corrected) != len(scenes):
            logger.warning(
                "清洗结果数量不匹配: 预期 {}，实际 {}，已自动修正",
                len(scenes), len(corrected),
            )
            corrected = corrected[:len(scenes)]
            while len(corrected) < len(scenes):
                corrected.append(original_texts[len(corrected)])

        return [
            FusedScene(
                index=s.index,
                start_time=s.start_time,
                end_time=s.end_time,
                summary=s.summary,
                text=corrected[i],
                has_scene_cut=s.has_scene_cut,
            )
            for i, s in enumerate(scenes)
        ]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_deepseek(self, texts: list[str]) -> list[str]:
        """调用 DeepSeek API 纠正文本

        Args:
            texts: 各分镜的原始文本列表

        Returns:
            纠正后的文本列表

        Raises:
            RuntimeError: API Key 未配置
            ValueError: JSON 解析失败
        """
        if not self.api_key:
            raise RuntimeError(
                "DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY"
            )
        if OpenAI is None:
            raise RuntimeError("openai 未安装")

        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

        formatted = "\n\n".join(
            f"[{i}]\n{t}" for i, t in enumerate(texts)
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个语音识别(ASR)纠错助手。\n\n"
                        "任务：根据上下文纠正中文语音识别文本中的错误，包括"
                        "同音字错误、漏字、多字、英文单词识别错误等。\n\n"
                        "规则（必须遵守）：\n"
                        "1. 只修正确定是识别错误的字词\n"
                        "2. 不要改变原有的措辞、风格和语气\n"
                        "3. 不要做任何润色、改写、压缩或扩展\n"
                        "4. 原本正确的文字必须保持原样\n"
                        "5. 每个输出元素与输入一一对应，保持顺序不变"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请纠正以下语音识别文本中的错误：\n\n{formatted}\n\n"
                        '请直接输出 JSON（不要包含其他内容）：\n'
                        '{"corrected_texts": ["' + texts[0] + '", ...]}'
                    ),
                },
            ],
        )

        content = response.choices[0].message.content
        return self._parse_json_response(content, len(texts))

    def _parse_json_response(self, content: str, expected_count: int) -> list[str]:
        """从 API 响应中解析 JSON 结果

        支持：
        - 纯 JSON 响应
        - 含 markdown 代码围栏的响应
        - 响应前后有多余文本
        """
        # 尝试提取 JSON 代码围栏
        json_match = re.search(
            r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL
        )
        json_str = json_match.group(1) if json_match else content

        # 尝试提取最外层花括号
        brace_match = re.search(r'(\{.*\})', json_str, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(1)

        try:
            data = json.loads(json_str)
            corrected_texts = data.get("corrected_texts", data.get("texts", []))
            if not isinstance(corrected_texts, list) or len(corrected_texts) != expected_count:
                raise ValueError(
                    f"返回格式错误: 预期 {expected_count} 条，实际 {len(corrected_texts)} 条"
                )
            return [str(t) for t in corrected_texts]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("解析清洗结果失败: {}", e)
            raise ValueError(f"解析清洗结果失败: {e}") from e
