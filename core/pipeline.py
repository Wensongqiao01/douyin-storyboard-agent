"""任务编排流水线

将下载、音频提取、语音转写、语义分镜、场景检测、融合对齐
串联为完整的端到端流程。
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from config import config
from core.audio_extractor import AudioExtractor
from core.downloader import download_video
from core.fuser import fuse_scenes
from core.scene_detector import SceneDetector
from core.segmenter import Segmenter
from core.text_cleaner import TextCleaner
from core.transcriber import Transcriber
from models.schemas import (
    BatchResult,
    FusedScene,
    SceneCutsResult,
    SemanticResult,
    TaskResult,
    TaskStatus,
    WhisperResult,
)
from utils.file_helpers import (
    ensure_dir,
    generate_task_id,
    get_task_paths,
)


class Pipeline:
    """任务编排流水线"""

    def __init__(
        self,
        downloader=download_video,
        audio_extractor: Optional[AudioExtractor] = None,
        transcriber: Optional[Transcriber] = None,
        segmenter: Optional[Segmenter] = None,
        scene_detector: Optional[SceneDetector] = None,
        fuser=fuse_scenes,
        text_cleaner: TextCleaner | None = None,
        audio_sample_rate: int = 16000,
        scene_threshold: Optional[float] = None,
        deepseek_api_key: Optional[str] = None,
        deepseek_model: Optional[str] = None,
        fuse_align_window: Optional[float] = None,
        pipeline_timeout: Optional[int] = None,
        log_file: Optional[str] = None,
        # 注意：batch_run 模式下该回调会被多个 worker 线程并发调用，实现方需保证线程安全
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        self._download = downloader
        self._audio = audio_extractor or AudioExtractor(sample_rate=audio_sample_rate)
        self._transcriber = transcriber or Transcriber()
        self._segmenter = segmenter or Segmenter(
            api_key=deepseek_api_key, model=deepseek_model
        )
        self._scene = scene_detector or SceneDetector(threshold=scene_threshold)
        self._fuser = fuser
        self._text_cleaner = text_cleaner if text_cleaner is not None else TextCleaner(
            api_key=deepseek_api_key, model=deepseek_model,
        )
        self._fuse_align_window = fuse_align_window
        self._pipeline_timeout = (
            config.pipeline_timeout if pipeline_timeout is None else pipeline_timeout
        )
        # 保存 result.json 的输出目录（由 batch_run 设置）
        self._batch_output_dir: str | None = None
        # 为当前任务创建独立的日志文件
        if log_file:
            logger.add(log_file, encoding="utf-8", rotation="50 MB", retention=3)
        # 进度回调
        self._on_progress = on_progress

    def _notify(self, status: TaskStatus) -> None:
        """通知外部当前阶段（回调异常不影响流水线）"""
        if self._on_progress is None:
            return
        try:
            self._on_progress(status.value)
        except Exception as e:
            logger.warning("进度回调异常: {}", e)

    def _run_internal(self, url: str, task_id: str) -> TaskResult:
        """实际流水线执行体，无超时逻辑"""
        paths = get_task_paths(task_id)
        ensure_dir(paths.video_dir)
        ensure_dir(paths.audio_dir)
        ensure_dir(paths.intermediate_dir)

        # 1. 下载视频
        self._notify(TaskStatus.DOWNLOADING)
        logger.info("[{}] 开始下载: {}", task_id, url)
        video_path = self._download(url, paths.original_video)

        # 2. 提取音频
        logger.info("[{}] 开始提取音频", task_id)
        audio_path = self._audio.extract(video_path, paths.audio_file)

        # 3. 语音转写
        self._notify(TaskStatus.TRANSCRIBING)
        logger.info("[{}] 开始转写", task_id)
        whisper_result: WhisperResult = self._transcriber.transcribe(audio_path)
        with open(paths.whisper_raw, "w", encoding="utf-8") as f:
            json.dump(whisper_result.model_dump(), f, ensure_ascii=False, indent=2)

        # 4. 语义分镜
        self._notify(TaskStatus.SEGMENTING)
        logger.info("[{}] 开始语义分镜", task_id)
        semantic_result: SemanticResult = self._segmenter.segment(whisper_result)
        with open(paths.semantic_raw, "w", encoding="utf-8") as f:
            json.dump(semantic_result.model_dump(), f, ensure_ascii=False, indent=2)

        # 5. 场景检测
        self._notify(TaskStatus.DETECTING)
        logger.info("[{}] 开始场景检测", task_id)
        scene_result: SceneCutsResult = self._scene.detect(video_path)
        with open(paths.scene_cuts_raw, "w", encoding="utf-8") as f:
            json.dump(scene_result.model_dump(), f, ensure_ascii=False, indent=2)

        # 6. 融合对齐
        self._notify(TaskStatus.FUSING)
        logger.info("[{}] 开始融合对齐", task_id)
        fused: list[FusedScene] = self._fuser(
            semantic_result,
            scene_result,
            whisper_result,
            align_window=self._fuse_align_window,
        )

        # 7. DeepSeek 文本清洗（后处理修正 ASR 错字，不影响时间对齐）
        logger.info("[{}] 开始文本清洗", task_id)
        fused = self._text_cleaner.clean(fused)

        logger.info("[{}] 任务完成: {} 个分镜", task_id, len(fused))
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.DONE,
            url=url,
            scenes=fused,
        )

        # 保存 result.json
        with open(paths.result_json, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

        return result

    def run(self, url: str, task_id: Optional[str] = None) -> TaskResult:
        """执行完整流水线（带超时控制）

        Args:
            url: 抖音视频链接
            task_id: 外部传入的任务 ID，None 则自动生成

        Returns:
            TaskResult 包含最终分镜列表或错误信息
        """
        task_id = task_id or generate_task_id()

        if self._pipeline_timeout <= 0:
            # 不超时，直接执行
            try:
                return self._run_internal(url, task_id)
            except Exception as e:
                logger.error("[{}] 任务失败: {}", task_id, e)
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.ERROR,
                    url=url,
                    error_message=str(e),
                )

        # 在独立线程中执行，带超时控制
        result_holder: list[TaskResult] = []
        exception_holder: list[Exception] = []

        def _worker():
            try:
                result_holder.append(self._run_internal(url, task_id))
            except Exception as e:
                exception_holder.append(e)

        worker_thread = threading.Thread(target=_worker, daemon=True)
        worker_thread.start()
        worker_thread.join(timeout=self._pipeline_timeout)

        if worker_thread.is_alive():
            logger.error("[{}] 任务超时（超过 {} 秒）", task_id, self._pipeline_timeout)
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                url=url,
                error_message=f"分析超时：任务运行超过 {self._pipeline_timeout} 秒，请检查视频链接是否有效或网络是否通畅",
            )
            paths = get_task_paths(task_id)
            with open(paths.result_json, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
            return result

        if exception_holder:
            logger.error("[{}] 任务失败: {}", task_id, exception_holder[0])
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                url=url,
                error_message=str(exception_holder[0]),
            )
            paths = get_task_paths(task_id)
            with open(paths.result_json, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
            return result

        return result_holder[0]

    def batch_run(
        self,
        urls: list[str],
        max_workers: int | None = None,
    ) -> BatchResult:
        """批量执行流水线

        使用 ThreadPoolExecutor 并发执行多个任务。
        Whisper CPU 推理是主要瓶颈，根据 CPU 核心数自动计算并行数。

        Args:
            urls: 抖音视频链接列表（最多 50 条）
            max_workers: 最大并行数。None 则根据 CPU 核心数自动计算。

        Returns:
            BatchResult 聚合结果
        """
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            logger.warning("批量处理：URL 列表为空")
            return BatchResult()
        if len(urls) > 50:
            logger.warning("批量处理：URL 数量超过 50，截断到前 50 条")
            urls = urls[:50]

        # 自动计算并行数
        if max_workers is None:
            cores = os.cpu_count() or 4
            max_workers = max(2, min(cores // 6, 4))
        if len(urls) < max_workers:
            max_workers = len(urls)

        logger.info(
            "开始批量处理 {} 个任务（并行数={}，CPU核心={}）",
            len(urls), max_workers, os.cpu_count() or "?",
        )

        results: list[TaskResult | None] = [None] * len(urls)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.run, url): i
                for i, url in enumerate(urls)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error("批量任务 #{} 异常: {}", idx, e)
                    results[idx] = TaskResult(
                        task_id=generate_task_id(),
                        status=TaskStatus.ERROR,
                        url=urls[idx],
                        error_message=str(e),
                    )

        valid = [r for r in results if r is not None]
        succeeded = [r for r in valid if r.status == TaskStatus.DONE]
        failed = [r for r in valid if r.status == TaskStatus.ERROR]
        total_duration = sum(
            (s.scenes[-1].end_time - s.scenes[0].start_time)
            for s in succeeded
            if s.scenes
        )

        summary = BatchResult(
            total=len(valid),
            succeeded=len(succeeded),
            failed=len(failed),
            total_duration=total_duration,
            results=valid,
        )
        logger.info(
            "批量处理完成: 总计 {}，成功 {}，失败 {}",
            summary.total, summary.succeeded, summary.failed,
        )
        return summary


    def batch_run_stream(
        self,
        urls: list[str],
        max_workers: int | None = None,
    ):
        """Generator: 批量执行流水线，每完成一个任务 yield 一次进度

        Args:
            urls: 抖音视频链接列表（最多 50 条）
            max_workers: 最大并行数

        Yields:
            (completed: dict[int, TaskResult], total: int)
            其中 completed 的 key 是任务在原始列表中的索引
        """
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return
        if len(urls) > 50:
            logger.warning("批量处理：URL 数量超过 50，截断到前 50 条")
            urls = urls[:50]

        if max_workers is None:
            cores = os.cpu_count() or 4
            max_workers = max(2, min(cores // 6, 4))
        if len(urls) < max_workers:
            max_workers = len(urls)

        logger.info(
            "开始批量流式处理 {} 个任务（并行数={}）",
            len(urls), max_workers,
        )

        completed: dict[int, TaskResult] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.run, url): i
                for i, url in enumerate(urls)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    completed[idx] = future.result()
                except Exception as e:
                    logger.error("批量任务 #{} 异常: {}", idx, e)
                    completed[idx] = TaskResult(
                        task_id=generate_task_id(),
                        status=TaskStatus.ERROR,
                        url=urls[idx],
                        error_message=str(e),
                    )
                yield completed, len(urls)

        logger.info(
            "批量流式处理完成: 总计 {}",
            len(urls),
        )


def run_pipeline(
    url: str,
    audio_sample_rate: int = 16000,
    scene_threshold: Optional[float] = None,
    deepseek_api_key: Optional[str] = None,
    deepseek_model: Optional[str] = None,
    fuse_align_window: Optional[float] = None,
    pipeline_timeout: Optional[int] = None,
) -> TaskResult:
    """快捷函数：执行完整流水线

    Args:
        url: 抖音视频链接
        audio_sample_rate: 音频采样率
        scene_threshold: 场景检测阈值
        deepseek_api_key: DeepSeek API Key
        deepseek_model: DeepSeek 模型名
        fuse_align_window: 融合对齐窗口（秒）
        pipeline_timeout: 超时秒数，None 使用 config 默认值

    Returns:
        TaskResult 任务结果
    """
    pipeline = Pipeline(
        audio_sample_rate=audio_sample_rate,
        scene_threshold=scene_threshold,
        deepseek_api_key=deepseek_api_key,
        deepseek_model=deepseek_model,
        fuse_align_window=fuse_align_window,
        pipeline_timeout=pipeline_timeout,
    )
    return pipeline.run(url)


def batch_run_pipeline_stream(
    urls: list[str],
    max_workers: int | None = None,
    audio_sample_rate: int = 16000,
    scene_threshold: Optional[float] = None,
    deepseek_api_key: Optional[str] = None,
    deepseek_model: Optional[str] = None,
    fuse_align_window: Optional[float] = None,
    pipeline_timeout: Optional[int] = None,
):
    """Generator: 批量流水线流式快捷函数

    Args:
        同 batch_run_pipeline

    Yields:
        (completed: dict[int, TaskResult], total: int)
    """
    pipeline = Pipeline(
        audio_sample_rate=audio_sample_rate,
        scene_threshold=scene_threshold,
        deepseek_api_key=deepseek_api_key,
        deepseek_model=deepseek_model,
        fuse_align_window=fuse_align_window,
        pipeline_timeout=pipeline_timeout,
    )
    yield from pipeline.batch_run_stream(urls, max_workers=max_workers)


def batch_run_pipeline(
    urls: list[str],
    max_workers: int | None = None,
    audio_sample_rate: int = 16000,
    scene_threshold: Optional[float] = None,
    deepseek_api_key: Optional[str] = None,
    deepseek_model: Optional[str] = None,
    fuse_align_window: Optional[float] = None,
    pipeline_timeout: Optional[int] = None,
) -> BatchResult:
    """快捷函数：批量执行流水线

    Args:
        urls: 抖音视频链接列表（最多 50 条）
        max_workers: 最大并行数
        audio_sample_rate: 音频采样率
        scene_threshold: 场景检测阈值
        deepseek_api_key: DeepSeek API Key
        deepseek_model: DeepSeek 模型名
        fuse_align_window: 融合对齐窗口（秒）
        pipeline_timeout: 超时秒数，None 使用 config 默认值

    Returns:
        BatchResult 聚合结果
    """
    pipeline = Pipeline(
        audio_sample_rate=audio_sample_rate,
        scene_threshold=scene_threshold,
        deepseek_api_key=deepseek_api_key,
        deepseek_model=deepseek_model,
        fuse_align_window=fuse_align_window,
        pipeline_timeout=pipeline_timeout,
    )
    return pipeline.batch_run(urls, max_workers=max_workers)
