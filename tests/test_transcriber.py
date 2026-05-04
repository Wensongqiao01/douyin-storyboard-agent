"""测试语音转写模块"""
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import WhisperResult


class TestTranscriber:
    """测试 Transcriber"""

    @patch("core.transcriber.Path.exists")
    @patch("core.transcriber.WhisperModel")
    def test_successful_transcription(
        self,
        mock_model_cls: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试成功转写"""
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "audio.wav")
        mock_exists.return_value = True

        # 模拟 WhisperModel.transcribe 返回值
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model

        # 构造模拟的 segment 和 word
        mock_word1 = MagicMock()
        mock_word1.word = "你好"
        mock_word1.start = 0.0
        mock_word1.end = 0.5

        mock_word2 = MagicMock()
        mock_word2.word = "世界"
        mock_word2.start = 0.5
        mock_word2.end = 1.0

        mock_segment = MagicMock()
        mock_segment.text = "你好世界"
        mock_segment.words = [mock_word1, mock_word2]

        mock_info = MagicMock()
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        transcriber = Transcriber(model_size="tiny", device="cpu")
        result = transcriber.transcribe(audio_path)

        assert isinstance(result, WhisperResult)
        assert result.text == "你好世界"
        assert len(result.segments) == 2
        assert result.segments[0].word == "你好"
        assert result.segments[0].start == 0.0
        assert result.segments[0].end == 0.5
        assert result.segments[1].word == "世界"
        assert result.duration == 1.0

        mock_model_cls.assert_called_once_with(
            "tiny", device="cpu", compute_type="int8"
        )
        mock_model.transcribe.assert_called_once_with(
            audio_path, word_timestamps=True, language="zh"
        )

    @patch("core.transcriber.Path.exists")
    def test_audio_not_found(self, mock_exists: MagicMock, tmp_path):
        """测试音频文件不存在时抛出异常"""
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "nonexistent.wav")
        mock_exists.return_value = False

        transcriber = Transcriber()
        with pytest.raises(FileNotFoundError, match="音频文件不存在"):
            transcriber.transcribe(audio_path)

    @patch("core.transcriber.Path.exists")
    @patch("core.transcriber.WhisperModel")
    def test_model_load_failure(
        self,
        mock_model_cls: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试模型加载失败时抛出异常"""
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "audio.wav")
        mock_exists.return_value = True
        mock_model_cls.side_effect = Exception("CUDA out of memory")

        transcriber = Transcriber()
        with pytest.raises(RuntimeError, match="模型加载失败"):
            transcriber.transcribe(audio_path)

    @patch("core.transcriber.Path.exists")
    @patch("core.transcriber.WhisperModel")
    def test_transcribe_failure(
        self,
        mock_model_cls: MagicMock,
        mock_exists: MagicMock,
        tmp_path,
    ):
        """测试转写过程失败时抛出异常"""
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "audio.wav")
        mock_exists.return_value = True

        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model
        mock_model.transcribe.side_effect = Exception("transcription failed")

        transcriber = Transcriber()
        with pytest.raises(RuntimeError, match="转写失败"):
            transcriber.transcribe(audio_path)


class TestTranscribeAudio:
    """测试 transcribe_audio 快捷函数"""

    @patch("core.transcriber.Transcriber.transcribe")
    def test_transcribe_audio_convenience(
        self, mock_transcribe: MagicMock, tmp_path
    ):
        """测试 transcribe_audio 快捷函数"""
        from core.transcriber import transcribe_audio

        audio_path = str(tmp_path / "audio.wav")
        expected = WhisperResult(
            text="你好世界",
            segments=[],
            duration=1.0,
        )
        mock_transcribe.return_value = expected

        result = transcribe_audio(audio_path)

        assert result == expected
        mock_transcribe.assert_called_once()
