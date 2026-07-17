"""tests/test_pipeline_progress.py — Pipeline 进度回调与外部 task_id"""

from unittest.mock import MagicMock

from core.pipeline import Pipeline
from models.schemas import (
    SceneCutsResult,
    SemanticResult,
    TaskStatus,
    WhisperResult,
)


def _make_pipeline(on_progress=None) -> Pipeline:
    """构造全 mock 依赖的 Pipeline"""
    transcriber = MagicMock()
    transcriber.transcribe.return_value = WhisperResult(text="测试", duration=1.0)
    segmenter = MagicMock()
    segmenter.segment.return_value = SemanticResult(segments=[])
    scene = MagicMock()
    scene.detect.return_value = SceneCutsResult(cuts=[], total_frames=10)
    cleaner = MagicMock()
    cleaner.clean.side_effect = lambda scenes: scenes
    return Pipeline(
        downloader=lambda url, path: path,
        audio_extractor=MagicMock(extract=MagicMock(return_value="a.wav")),
        transcriber=transcriber,
        segmenter=segmenter,
        scene_detector=scene,
        fuser=lambda *a, **k: [],
        text_cleaner=cleaner,
        pipeline_timeout=0,
        on_progress=on_progress,
    )


def test_run_uses_external_task_id(tmp_path, monkeypatch):
    """run() 接受外部 task_id，结果里的 task_id 与之一致"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))
    pipeline = _make_pipeline()
    result = pipeline.run("https://example.com/v", task_id="my_task_001")
    assert result.task_id == "my_task_001"
    assert result.status == TaskStatus.DONE


def test_on_progress_called_for_each_stage(tmp_path, monkeypatch):
    """每个阶段开始时调用 on_progress，顺序正确"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))
    events: list[str] = []
    pipeline = _make_pipeline(on_progress=events.append)
    pipeline.run("https://example.com/v", task_id="my_task_002")
    assert events == [
        "downloading",
        "transcribing",
        "segmenting",
        "detecting",
        "fusing",
    ]


def test_on_progress_exception_does_not_break_pipeline(tmp_path, monkeypatch):
    """回调抛异常不影响流水线"""
    from config import config

    monkeypatch.setattr(config, "output_base_dir", str(tmp_path))

    def bad_callback(status: str) -> None:
        raise RuntimeError("boom")

    pipeline = _make_pipeline(on_progress=bad_callback)
    result = pipeline.run("https://example.com/v", task_id="my_task_003")
    assert result.status == TaskStatus.DONE
