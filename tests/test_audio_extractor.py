"""测试音频提取模块"""
from unittest.mock import MagicMock, patch

import pytest

from core.audio_extractor import AudioExtractor, extract_audio


class TestAudioExtractor:
    """测试 AudioExtractor"""

    @patch("core.audio_extractor.Path.exists")
    @patch("core.audio_extractor.ffmpeg")
    def test_successful_extraction(
        self,
        mock_ffmpeg: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试成功提取音频"""
        video_path = str(tmp_path / "video.mp4")
        audio_path = str(tmp_path / "audio.wav")

        mock_exists.return_value = True
        # 设置链式调用：ffmpeg.input().output().run()
        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream

        extractor = AudioExtractor(sample_rate=16000)
        result = extractor.extract(video_path, audio_path)

        assert result == audio_path
        mock_ffmpeg.input.assert_called_once_with(video_path)
        mock_stream.output.assert_called_once()
        mock_stream.run.assert_called_once_with(overwrite_output=True)

    @patch("core.audio_extractor.Path.exists")
    @patch("core.audio_extractor.ffmpeg")
    def test_video_not_found(
        self,
        mock_ffmpeg: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试输入视频不存在时抛出异常"""
        video_path = str(tmp_path / "nonexistent.mp4")
        audio_path = str(tmp_path / "audio.wav")

        mock_exists.return_value = False

        extractor = AudioExtractor()
        with pytest.raises(FileNotFoundError, match="视频文件不存在"):
            extractor.extract(video_path, audio_path)

        # ffmpeg 不应被调用
        mock_ffmpeg.input.assert_not_called()

    @patch("core.audio_extractor.Path.exists")
    @patch("core.audio_extractor.ffmpeg")
    def test_ffmpeg_failure(
        self,
        mock_ffmpeg: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试 ffmpeg 执行失败时抛出异常"""
        video_path = str(tmp_path / "video.mp4")
        audio_path = str(tmp_path / "audio.wav")

        mock_exists.return_value = True
        mock_ffmpeg.input.side_effect = RuntimeError("ffmpeg error")

        extractor = AudioExtractor()
        with pytest.raises(RuntimeError, match="音频提取失败"):
            extractor.extract(video_path, audio_path)

    @patch("core.audio_extractor.Path.exists")
    @patch("core.audio_extractor.ffmpeg")
    def test_custom_sample_rate(
        self,
        mock_ffmpeg: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试自定义采样率"""
        video_path = str(tmp_path / "video.mp4")
        audio_path = str(tmp_path / "audio.wav")

        mock_exists.return_value = True
        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream

        extractor = AudioExtractor(sample_rate=44100)
        extractor.extract(video_path, audio_path)

        mock_stream.output.assert_called_once()
        _, kwargs = mock_stream.output.call_args
        assert kwargs.get("ar") == "44100"


class TestExtractAudio:
    """测试 extract_audio 快捷函数"""

    @patch("core.audio_extractor.ensure_dir")
    @patch("core.audio_extractor.AudioExtractor.extract")
    def test_extract_audio_convenience(
        self,
        mock_extract: MagicMock,
        mock_ensure_dir: MagicMock,
        tmp_path,
    ):
        """测试 extract_audio 快捷函数调用正确"""
        video_path = str(tmp_path / "video.mp4")

        mock_ensure_dir.return_value = str(tmp_path / "audio")
        mock_extract.return_value = str(tmp_path / "audio" / "audio.wav")

        result = extract_audio(
            video_path, output_dir=str(tmp_path / "audio")
        )

        assert result == str(tmp_path / "audio" / "audio.wav")
        mock_ensure_dir.assert_called_once()
        mock_extract.assert_called_once()
