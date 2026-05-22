"""语义分镜模块 (v2)

将 Whisper 段落按语义主题分组为分镜。
v2 改动：不再一次发送全文到 DeepSeek，改为段落组批 → 分镜 → 跨批合并，
避免长视频 API 超时。
"""

import json
import re
from difflib import SequenceMatcher
from typing import Optional

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment]

from config import config
from models.schemas import (
    SemanticResult,
    SemanticSegment,
    TranscribedSegment,
    WhisperResult,
)

BATCH_MAX_CHARS = 2000  # 每批最大字符数
MERGE_SIMILARITY = 0.45  # 相邻批边界话题合并的相似度阈值
SENTENCE_MIN_CHARS = 60  # 预合并的最小句子长度（字）


class Segmenter:
    """DeepSeek 语义分镜器 (v2: 组批 + 合并)"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.deepseek_api_key
        self.model = model or config.deepseek_model
        self._client: Optional["OpenAI"] = None

    @property
    def client(self) -> "OpenAI":
        if self._client is None:
            if OpenAI is None:
                raise RuntimeError("openai 未安装")
            if not self.api_key:
                raise RuntimeError("DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY")
            self._client = OpenAI(
                api_key=self.api_key, base_url="https://api.deepseek.com"
            )
        return self._client

    def segment(self, whisper_result: WhisperResult) -> SemanticResult:
        """对 Whisper 转写结果进行语义分镜

        Args:
            whisper_result: WhisperResult 对象（含 paragraphs 字段）

        Returns:
            SemanticResult 包含语义分镜列表
        """
        paragraphs = whisper_result.paragraphs
        if not paragraphs:
            logger.warning("无段落数据，回退为全文单分镜")
            return SemanticResult(
                segments=[
                    SemanticSegment(
                        index=0,
                        summary="全文",
                        start_text=whisper_result.text[:200],
                        end_text=whisper_result.text[-200:],
                    )
                ]
            )

        logger.info("语义分镜: {} 段落, {} 字", len(paragraphs), len(whisper_result.text))

        # 0. 预合并：将 Whisper 的短语级小段落合并为句子级段落
        sentences = self._merge_small_paragraphs(paragraphs)
        logger.info("预合并: {} 段落 → {} 句子", len(paragraphs), len(sentences))

        # 1. 组批
        batches = self._build_batches(sentences)
        logger.info("组批完成: {} 批", len(batches))

        # 2. 逐批分镜
        all_topics: list[list[int]] = []  # [[句子索引组], ...]
        for i, batch in enumerate(batches):
            try:
                topic_groups = self._segment_batch(batch, i, len(batches))
                all_topics.extend(topic_groups)
            except Exception as e:
                logger.warning("分镜失败 [批 {}/{}]，保留为独立段落: {}", i + 1, len(batches), e)
                for sent in batch:
                    all_topics.append([sent["idx"]])

        # 3. 跨批边界合并
        merged = self._merge_across_boundaries(all_topics, sentences)
        logger.info("分镜完成: {} → {} 个分镜", len(all_topics), len(merged))

        # 4. 构建 SemanticResult
        segments = []
        for group in merged:
            if not group:
                continue
            first_idx, last_idx = group[0], group[-1]
            start_text = sentences[first_idx]["text"][:200]
            end_text = sentences[last_idx]["text"][-200:]
            combined = "".join(sentences[i]["text"] for i in group)
            summary = combined[:80]

            segments.append(
                SemanticSegment(
                    index=len(segments),
                    summary=summary,
                    start_text=start_text,
                    end_text=end_text,
                )
            )

        if not segments:
            return SemanticResult(
                segments=[
                    SemanticSegment(
                        index=0,
                        summary="全文",
                        start_text=whisper_result.text[:200],
                        end_text=whisper_result.text[-200:],
                    )
                ]
            )

        return SemanticResult(segments=segments)

    @staticmethod
    def _merge_small_paragraphs(paragraphs: list[TranscribedSegment]) -> list[dict]:
        """将短语级段落合并为句子级段落（~80 字/句）

        Whisper 的停顿划分非常细（平均 10 字/段），且不带标点。
        直接按字数阈值合并，不依赖标点符号。
        """
        sentences: list[dict] = []
        buf_text: list[str] = []
        buf_start: float | None = None
        buf_end: float = 0.0
        buf_chars = 0

        def _flush():
            nonlocal buf_text, buf_start, buf_end, buf_chars
            if buf_text:
                sentences.append({
                    "idx": len(sentences),
                    "text": "".join(buf_text),
                    "start": buf_start or 0.0,
                    "end": buf_end,
                })
            buf_text = []
            buf_start = None
            buf_end = 0.0
            buf_chars = 0

        for para in paragraphs:
            if not para.text.strip():
                _flush()
                continue

            if buf_start is None:
                buf_start = para.start
            buf_text.append(para.text)
            buf_end = para.end
            buf_chars += len(para.text)

            # 累计超过阈值就切断（Whisper 输出无标点，不依赖标点判断）
            if buf_chars >= SENTENCE_MIN_CHARS:
                _flush()

        _flush()
        return sentences

    def _build_batches(self, sentences: list[dict]) -> list[list[dict]]:
        """将句子归并为字符数不超过 BATCH_MAX_CHARS 的批"""
        batches: list[list[dict]] = []
        current: list[dict] = []
        current_len = 0

        for sent in sentences:
            para_len = len(sent["text"])
            if current and current_len + para_len > BATCH_MAX_CHARS:
                batches.append(current)
                current = []
                current_len = 0
            current.append({"idx": sent["idx"], "text": sent["text"], "start": sent["start"]})
            current_len += para_len

        if current:
            batches.append(current)
        return batches

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _segment_batch(self, batch: list[dict], batch_idx: int, total: int) -> list[list[int]]:
        """对一批段落调用 DeepSeek 做话题分组

        Returns:
            [[段落索引组1], [段落索引组2], ...]
        """
        # 构建编号段落文本
        lines = []
        for item in batch:
            lines.append(f"[{item['idx']}] {item['text']}")
        text_block = "\n".join(lines)

        logger.info("分镜中 [{}/{}]: {} 段落, {} 字", batch_idx + 1, total, len(batch), len(text_block))

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个视频文案语义分镜助手。\n"
                        "输入是一组标好索引的语音转写段落，请按话题将它们分组，"
                        "同一话题的连续段落归为一组。\n\n"
                        "规则：\n"
                        "1. 只返回 JSON，不要加任何解释\n"
                        "2. 每个段落的 index 必须属于某个组\n"
                        "3. 组必须保持段落的原始顺序（按 index 升序）\n"
                        "4. 不要合并不同话题的段落\n"
                        "5. 当话题发生明显变化时（如从'介绍功能A'切换到'介绍功能B'），"
                        "应该分成不同的组"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请对以下段落进行话题分组：\n\n{text_block}\n\n"
                        "输出 JSON 格式：\n"
                        '{"groups": [{"indices": [0,1,2]}, {"indices": [3,4]}, ...]}'
                    ),
                },
            ],
            timeout=180,
        )

        content = response.choices[0].message.content
        data = self._parse_json(content)

        groups = data.get("groups", [])
        if not groups:
            raise ValueError("DeepSeek 返回空分组")

        # 转换为 [[索引列表], ...]
        result = []
        for g in groups:
            indices = g.get("indices", g.get("index", []))
            if isinstance(indices, int):
                indices = [indices]
            result.append([int(i) for i in indices])

        return result

    @staticmethod
    def _parse_json(content: str) -> dict:
        """解析 DeepSeek 返回的 JSON（兼容 markdown 围栏）"""
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content
        brace_match = re.search(r"(\{.*\})", json_str, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(1)
        return json.loads(json_str)

    def _merge_across_boundaries(
        self,
        topic_groups: list[list[int]],
        sentences: list[dict],
    ) -> list[list[int]]:
        """合并跨批边界的相似话题

        检查每对相邻话题组的首尾段落文本相似度，高于阈值则合并。
        """
        if len(topic_groups) <= 1:
            return topic_groups

        merged: list[list[int]] = [list(topic_groups[0])]

        for i in range(1, len(topic_groups)):
            prev = merged[-1]
            curr = list(topic_groups[i])

            # 获取前一组尾部和当前组首部的文本
            prev_tail = "".join(sentences[idx]["text"] for idx in prev[-2:])
            curr_head = "".join(sentences[idx]["text"] for idx in curr[:2])

            similarity = SequenceMatcher(None, prev_tail, curr_head).ratio()

            if similarity > MERGE_SIMILARITY:
                # 同一话题被批次边界切断，合并
                prev.extend(curr)
            else:
                merged.append(curr)

        return merged


def segment_text(
    whisper_result: WhisperResult,
    api_key: str | None = None,
    model: str | None = None,
) -> SemanticResult:
    """快捷函数：对 Whisper 转写结果进行语义分镜"""
    segmenter = Segmenter(api_key=api_key, model=model)
    return segmenter.segment(whisper_result)
