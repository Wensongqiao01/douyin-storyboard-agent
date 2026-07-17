"""测试语音转写模块（阿里云百炼 Paraformer-v2）"""
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import WhisperResult


class TestTranscriber:
    """测试 Transcriber"""

    @patch("core.transcriber.Path.exists")
    def test_audio_not_found(self, mock_exists: MagicMock, tmp_path, monkeypatch):
        """测试音频文件不存在时抛出异常"""
        monkeypatch.setattr("core.transcriber.config.bailian_api_key", "sk-test")
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "nonexistent.wav")
        mock_exists.return_value = False

        transcriber = Transcriber()
        with pytest.raises(FileNotFoundError, match="音频文件不存在"):
            transcriber.transcribe(audio_path)

    @patch("core.transcriber.Transcriber._upload")
    @patch("core.transcriber.Transcription")
    @patch("core.transcriber.Path.exists")
    def test_successful_transcription(
        self,
        mock_exists: MagicMock,
        mock_trans_api: MagicMock,
        mock_upload: MagicMock,
        tmp_path,
        monkeypatch,
    ):
        """测试成功转写：Paraformer 结果正确转换为 WhisperResult"""
        monkeypatch.setattr("core.transcriber.config.bailian_api_key", "sk-test")
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "audio.wav")
        mock_exists.return_value = True
        mock_upload.return_value = "oss://bucket/audio.wav"

        # 模拟 Transcription.async_call
        mock_task = MagicMock()
        mock_task.output.task_id = "task-123"
        mock_trans_api.async_call.return_value = mock_task

        # 模拟 Transcription.wait 返回
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output = {
            "results": [{
                "subtask_status": "SUCCEEDED",
                "transcription_url": "https://example.com/result.json",
            }]
        }
        mock_trans_api.wait.return_value = mock_response

        # 模拟 httpx.get 下载的 JSON
        trans_json = {
            "transcripts": [{
                "channel_id": 0,
                "content_duration_in_milliseconds": 2000,
                "sentences": [{
                    "begin_time": 0,
                    "end_time": 1000,
                    "text": "你好",
                    "words": [
                        {"begin_time": 0, "end_time": 500, "text": "你"},
                        {"begin_time": 500, "end_time": 1000, "text": "好"},
                    ],
                }, {
                    "begin_time": 1000,
                    "end_time": 2000,
                    "text": "世界",
                    "words": [
                        {"begin_time": 1000, "end_time": 1500, "text": "世"},
                        {"begin_time": 1500, "end_time": 2000, "text": "界"},
                    ],
                }],
            }]
        }

        with patch("core.transcriber.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = trans_json
            mock_get.return_value = mock_resp

            transcriber = Transcriber()
            result = transcriber.transcribe(audio_path)

        assert isinstance(result, WhisperResult)
        assert result.text == "你好世界"
        assert result.duration == 2.0
        assert len(result.segments) == 4
        assert result.segments[0].word == "你"
        assert result.segments[0].start == 0.0
        assert result.segments[0].end == 0.5
        assert result.segments[3].word == "界"
        assert result.segments[3].start == 1.5
        assert result.segments[3].end == 2.0
        assert len(result.paragraphs) == 2
        assert result.paragraphs[0].text == "你好"
        assert result.paragraphs[1].text == "世界"

    def test_api_key_missing(self, monkeypatch):
        """测试未配置 API Key 时抛出异常"""
        monkeypatch.setattr("core.transcriber.config.bailian_api_key", "")
        from core.transcriber import Transcriber

        with pytest.raises(RuntimeError, match="BAILIAN_API_KEY"):
            Transcriber()

    @patch("core.transcriber.Transcriber._upload")
    @patch("core.transcriber.Transcription")
    @patch("core.transcriber.Path.exists")
    def test_api_failure(
        self,
        mock_exists: MagicMock,
        mock_trans_api: MagicMock,
        mock_upload: MagicMock,
        tmp_path,
        monkeypatch,
    ):
        """测试 API 返回失败时抛出异常"""
        monkeypatch.setattr("core.transcriber.config.bailian_api_key", "sk-test")
        from core.transcriber import Transcriber

        audio_path = str(tmp_path / "audio.wav")
        mock_exists.return_value = True
        mock_upload.return_value = "oss://bucket/audio.wav"

        mock_task = MagicMock()
        mock_task.output.task_id = "task-123"
        mock_trans_api.async_call.return_value = mock_task

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.code = "InvalidParameter"
        mock_response.message = "参数错误"
        mock_trans_api.wait.return_value = mock_response

        transcriber = Transcriber()
        with pytest.raises(RuntimeError, match="语音识别失败"):
            transcriber.transcribe(audio_path)


class TestTranscribeAudio:
    """测试 transcribe_audio 快捷函数"""

    @patch("core.transcriber.Transcriber.transcribe")
    def test_transcribe_audio_convenience(
        self, mock_transcribe: MagicMock, tmp_path, monkeypatch
    ):
        """测试 transcribe_audio 快捷函数"""
        monkeypatch.setattr("core.transcriber.config.bailian_api_key", "sk-test")
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
