"""融合对齐模块

将语义分镜、画面场景切点、Whisper 时间戳融合为最终分镜列表。
DeepSeek 语义分段为骨架，场景切点精修边界，Whisper 时间戳提供精准时间映射。
"""

from rapidfuzz import fuzz

from loguru import logger

from config import config
from models.schemas import (
    FusedScene,
    SceneCut,
    SceneCutsResult,
    SemanticResult,
    SemanticSegment,
    WhisperResult,
)
from utils.text_matcher import find_text_timestamp, match_boundary

# 模糊匹配阈值，end_text 与下一段 start_text 得分 >= 此值时保留精确边界
_CONFIDENT_MATCH_THRESHOLD = 90


class Fuser:
    """融合对齐器"""

    def __init__(self, align_window: float | None = None):
        self.align_window = align_window or config.fuse_align_window

    def fuse(
        self,
        semantic: SemanticResult,
        scenes: SceneCutsResult,
        whisper: WhisperResult,
    ) -> list[FusedScene]:
        """融合三个模块的结果为最终分镜列表"""
        if not semantic.segments:
            return []

        words = whisper.segments
        total_duration = whisper.duration

        # 1. 计算每个语义分镜的起止时间
        times, is_confident = self._compute_times(semantic.segments, words, total_duration)

        # 2. 对齐场景切点（仅对齐 fallback 边界）
        times = self._align_scene_cuts(times, scenes.cuts, is_confident)

        # 3. 构建最终结果
        return self._build_fused_scenes(semantic.segments, words, times)

    def _compute_times(
        self,
        segments: list[SemanticSegment],
        words: list,
        total_duration: float,
    ) -> tuple[list[dict], list[bool]]:
        """计算每个分镜的起止时间"""
        n = len(segments)
        times: list[dict] = []
        is_confident: list[bool] = []

        # 第一遍：计算 start_time（fallback 用 -1 占位，稍后修正避免重叠）
        start_times: list[float] = []
        for i, seg in enumerate(segments):
            ts = find_text_timestamp(seg.start_text, words)
            if ts is not None:
                start_times.append(ts["start"])
            elif i == 0:
                start_times.append(0.0)
            else:
                start_times.append(-1.0)

        # 第二遍：计算 end_time，同时修正 fallback start_time
        for i, seg in enumerate(segments):
            if start_times[i] < 0:
                start_times[i] = times[i - 1]["end"] if times else 0.0

            end_time, confident = self._compute_end_time(
                i, seg, segments, start_times, words, total_duration,
            )
            times.append({"start": start_times[i], "end": end_time})
            is_confident.append(confident)

        return times, is_confident

    def _compute_end_time(
        self,
        i: int,
        seg: SemanticSegment,
        segments: list[SemanticSegment],
        start_times: list[float],
        words: list,
        total_duration: float,
    ) -> tuple[float, bool]:
        """计算单个分镜的结束时间

        Returns:
            (end_time, is_confident) — is_confident 表示 end_text 是否成功匹配到时间戳
        """
        n = len(segments)
        end_ts = match_boundary(seg.end_text, words, direction="end")

        if i < n - 1:
            next_start = start_times[i + 1]
            if next_start < 0:
                next_start = start_times[i] + (total_duration / n)

            if end_ts is not None:
                if fuzz.ratio(seg.end_text, segments[i + 1].start_text) >= _CONFIDENT_MATCH_THRESHOLD:
                    return end_ts, True
                return min(end_ts, next_start), True
            return next_start, False

        return (end_ts if end_ts is not None else total_duration), (end_ts is not None)

    def _align_scene_cuts(
        self,
        times: list[dict],
        cuts: list[SceneCut],
        is_confident: list[bool],
    ) -> list[dict]:
        """将分镜边界对齐到最近的场景切点（仅对齐 fallback 边界）"""
        if not cuts:
            return times

        result = []
        for i, t in enumerate(times):
            aligned_end = t["end"]
            has_cut = False

            if i < len(times) - 1:
                boundary = t["end"]
                best_cut = None
                best_dist = float("inf")

                for cut in cuts:
                    dist = abs(cut.time - boundary)
                    if dist <= self.align_window and dist < best_dist:
                        best_dist = dist
                        best_cut = cut

                if best_cut is not None:
                    has_cut = True
                    if not is_confident[i]:
                        aligned_end = best_cut.time

            result.append({"start": t["start"], "end": aligned_end, "has_scene_cut": has_cut})

        return result

    def _build_fused_scenes(
        self,
        segments: list[SemanticSegment],
        words: list,
        times: list[dict],
    ) -> list[FusedScene]:
        """构建最终 FusedScene 列表"""
        fused: list[FusedScene] = []

        for i, seg in enumerate(segments):
            t = times[i]
            start_time = t["start"]
            end_time = t["end"]
            has_scene_cut = t.get("has_scene_cut", False)

            # 容错：当文字匹配失败导致 start_time > end_time 时自动修正
            if end_time < start_time:
                logger.warning(
                    "分镜 #{} 时间异常: {} > {}，已自动修正",
                    i, start_time, end_time,
                )
                end_time = start_time

            # 提取该时间范围内的文字（使用重叠检测，避免跨边界字词被丢弃）
            text_parts: list[str] = []
            for w in words:
                if w.start < end_time and w.end > start_time:
                    text_parts.append(w.word)

            fused.append(
                FusedScene(
                    index=i,
                    start_time=start_time,
                    end_time=end_time,
                    summary=seg.summary,
                    text="".join(text_parts),
                    has_scene_cut=has_scene_cut,
                )
            )

        return fused


def fuse_scenes(
    semantic: SemanticResult,
    scenes: SceneCutsResult,
    whisper: WhisperResult,
    align_window: float | None = None,
) -> list[FusedScene]:
    """快捷函数：融合语义分镜、场景切点和时间戳"""
    fuser = Fuser(align_window=align_window)
    return fuser.fuse(semantic, scenes, whisper)
