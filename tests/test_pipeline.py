"""测试 Pipeline 编排层"""
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import (
    FusedScene,
    SceneCut,
    SceneCutsResult,
    SemanticResult,
    SemanticSegment,
    TaskResult,
    TaskStatus,
    WhisperResult,
    WordTimestamp,
)


class TestPipeline:
    """测试 Pipeline 编排"""

    def make_whisper(self) -> WhisperResult:
        return WhisperResult(
            text="hello world",
            segments=[
                WordTimestamp(word="hello", start=0.0, end=0.5),
                WordTimestamp(word="world", start=0.5, end=1.0),
            ],
            duration=1.0,
        )

    def make_semantic(self) -> SemanticResult:
        return SemanticResult(
            segments=[
                SemanticSegment(index=0, summary="开场", start_text="hello", end_text="world"),
            ]
        )

    def make_scenes(self) -> SceneCutsResult:
        return SceneCutsResult(
            cuts=[SceneCut(time=0.5, frame=15)],
            total_frames=30,
        )

    def make_fused(self) -> list[FusedScene]:
        return [
            FusedScene(index=0, start_time=0.0, end_time=1.0, summary="开场", text="hello world"),
        ]

    # --- Happy path ---

    @patch("core.pipeline.download_video")
    def test_run_success(self, mock_download):
        """测试完整成功流程"""
        from core.pipeline import Pipeline

        mock_download.return_value = "/tmp/video.mp4"
        mock_audio = MagicMock()
        mock_audio.extract.return_value = "/tmp/audio.wav"
        mock_transcriber = MagicMock()
        whisper = self.make_whisper()
        mock_transcriber.transcribe.return_value = whisper
        mock_segmenter = MagicMock()
        semantic = self.make_semantic()
        mock_segmenter.segment.return_value = semantic
        mock_scene = MagicMock()
        scenes = self.make_scenes()
        mock_scene.detect.return_value = scenes
        mock_fuser = MagicMock()
        fused = self.make_fused()
        mock_fuser.return_value = fused

        pipeline = Pipeline(
            downloader=mock_download,
            audio_extractor=mock_audio,
            transcriber=mock_transcriber,
            segmenter=mock_segmenter,
            scene_detector=mock_scene,
            fuser=mock_fuser,
        )
        result = pipeline.run("https://example.com/v")

        assert result.status == TaskStatus.DONE
        assert isinstance(result.task_id, str)
        assert len(result.scenes) == 1
        assert result.scenes[0].summary == "开场"
        assert result.error_message is None

        mock_download.assert_called_once()
        mock_audio.extract.assert_called_once()
        mock_transcriber.transcribe.assert_called_once_with("/tmp/audio.wav")
        mock_segmenter.segment.assert_called_once_with(whisper)
        mock_scene.detect.assert_called_once_with("/tmp/video.mp4")
        mock_fuser.assert_called_once()

    # --- Error cases ---

    def _assert_error(self, mock_download, component_attr: str, error_msg: str):
        """Helper: 验证某个步骤失败返回 ERROR，直接映射组件→方法名"""
        from core.pipeline import Pipeline

        mock_download.return_value = "/tmp/video.mp4"
        mock_audio = MagicMock()
        mock_audio.extract.return_value = "/tmp/audio.wav"
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = self.make_whisper()
        mock_segmenter = MagicMock()
        mock_segmenter.segment.return_value = self.make_semantic()
        mock_scene = MagicMock()
        mock_scene.detect.return_value = self.make_scenes()
        mock_fuser = MagicMock()
        mock_fuser.return_value = self.make_fused()

        # 让指定组件失败
        if component_attr == "fuser":
            mock_fuser.side_effect = RuntimeError(error_msg)
        else:
            method_name = {
                "audio_extractor": "extract",
                "transcriber": "transcribe",
                "segmenter": "segment",
                "scene_detector": "detect",
            }[component_attr]
            component = {
                "audio_extractor": mock_audio,
                "transcriber": mock_transcriber,
                "segmenter": mock_segmenter,
                "scene_detector": mock_scene,
            }[component_attr]
            getattr(component, method_name).side_effect = RuntimeError(error_msg)

        pipeline = Pipeline(
            downloader=mock_download,
            audio_extractor=mock_audio,
            transcriber=mock_transcriber,
            segmenter=mock_segmenter,
            scene_detector=mock_scene,
            fuser=mock_fuser,
        )
        result = pipeline.run("https://example.com/v")

        assert result.status == TaskStatus.ERROR
        assert error_msg in result.error_message
        assert result.scenes == []

    @patch("core.pipeline.download_video")
    def test_download_failure(self, mock_download):
        """下载失败返回 ERROR"""
        from core.pipeline import Pipeline

        mock_download.side_effect = RuntimeError("下载失败")

        pipeline = Pipeline(downloader=mock_download)
        result = pipeline.run("https://example.com/v")

        assert result.status == TaskStatus.ERROR
        assert "下载失败" in result.error_message

    @patch("core.pipeline.download_video")
    def test_audio_extract_failure(self, mock_download):
        """音频提取失败返回 ERROR"""
        self._assert_error(mock_download, "audio_extractor", "音频提取失败")

    @patch("core.pipeline.download_video")
    def test_transcribe_failure(self, mock_download):
        """语音转写失败返回 ERROR"""
        self._assert_error(mock_download, "transcriber", "转写失败")

    @patch("core.pipeline.download_video")
    def test_segment_failure(self, mock_download):
        """语义分镜失败返回 ERROR"""
        self._assert_error(mock_download, "segmenter", "语义分镜失败")

    @patch("core.pipeline.download_video")
    def test_scene_detect_failure(self, mock_download):
        """场景检测失败返回 ERROR"""
        self._assert_error(mock_download, "scene_detector", "场景检测失败")

    @patch("core.pipeline.download_video")
    def test_fuse_failure(self, mock_download):
        """融合失败返回 ERROR"""
        self._assert_error(mock_download, "fuser", "融合失败")


class TestRunPipeline:
    """测试 run_pipeline 快捷函数"""

    @patch("core.pipeline.Pipeline")
    def test_convenience(self, mock_pipeline_cls):
        """测试快捷函数正确创建 Pipeline 并调用 run"""
        from core.pipeline import run_pipeline

        mock_instance = MagicMock()
        mock_pipeline_cls.return_value = mock_instance
        expected = TaskResult(
            task_id="abc", status=TaskStatus.DONE, scenes=[]
        )
        mock_instance.run.return_value = expected

        result = run_pipeline("https://example.com/v")

        assert result is expected
        mock_pipeline_cls.assert_called_once()
        mock_instance.run.assert_called_once_with("https://example.com/v")

    @patch("core.pipeline.Pipeline")
    def test_passes_kwargs(self, mock_pipeline_cls):
        """验证参数透传"""
        from core.pipeline import run_pipeline

        mock_instance = MagicMock()
        mock_pipeline_cls.return_value = mock_instance

        run_pipeline(
            "https://example.com/v",
            audio_sample_rate=48000,
            scene_threshold=20.0,
            deepseek_api_key="sk-test",
            deepseek_model="deepseek-reasoner",
            fuse_align_window=2.0,
        )

        mock_pipeline_cls.assert_called_once_with(
            audio_sample_rate=48000,
            scene_threshold=20.0,
            deepseek_api_key="sk-test",
            deepseek_model="deepseek-reasoner",
            fuse_align_window=2.0,
        )
