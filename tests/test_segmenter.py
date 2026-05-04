"""测试语义分镜模块"""
import json
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import SemanticResult, SemanticSegment


class TestSegmenter:
    """测试 Segmenter"""

    @patch("core.segmenter.OpenAI")
    def test_successful_segmentation(self, mock_openai_cls: MagicMock):
        """测试成功进行语义分镜"""
        from core.segmenter import Segmenter

        text = "大家好今天我们来聊一聊人工智能这个话题。首先让我们看看什么是人工智能。人工智能是模拟人类智能的技术。"
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "segments": [
                    {
                        "index": 0,
                        "summary": "开场白",
                        "start_text": "大家好",
                        "end_text": "这个话题",
                    },
                    {
                        "index": 1,
                        "summary": "人工智能定义",
                        "start_text": "首先",
                        "end_text": "技术",
                    },
                ]
            },
            ensure_ascii=False,
        )

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        segmenter = Segmenter(api_key="test_key")
        result = segmenter.segment(text)

        assert isinstance(result, SemanticResult)
        assert len(result.segments) == 2
        assert result.segments[0].index == 0
        assert result.segments[0].summary == "开场白"
        assert result.segments[1].summary == "人工智能定义"

        mock_openai_cls.assert_called_once_with(
            api_key="test_key", base_url="https://api.deepseek.com"
        )
        mock_client.chat.completions.create.assert_called_once()

    @patch("core.segmenter.OpenAI")
    def test_empty_text_raises(self, mock_openai_cls: MagicMock):
        """测试空文本抛出异常"""
        from core.segmenter import Segmenter

        segmenter = Segmenter()
        with pytest.raises(ValueError, match="文本不能为空"):
            segmenter.segment("")

    @patch("core.segmenter.OpenAI")
    def test_api_failure(self, mock_openai_cls: MagicMock):
        """测试 API 调用失败"""
        from core.segmenter import Segmenter

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        segmenter = Segmenter(api_key="test_key")
        with pytest.raises(RuntimeError, match="语义分镜失败"):
            segmenter.segment("这是一段测试文本")

    @patch("core.segmenter.OpenAI")
    def test_malformed_response(self, mock_openai_cls: MagicMock):
        """测试 API 返回格式错误"""
        from core.segmenter import Segmenter

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "不是 JSON 格式"

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        segmenter = Segmenter(api_key="test_key")
        result = segmenter.segment("这是一段测试文本")
        # 解析失败时回退为单个分镜
        assert isinstance(result, SemanticResult)
        assert len(result.segments) == 1
        assert result.segments[0].summary == "全文"
        assert result.segments[0].start_text == "这是一段测试文本"

    @patch("core.segmenter.OpenAI")
    def test_whisper_result_input(self, mock_openai_cls: MagicMock):
        """测试接受 WhisperResult 作为输入"""
        from core.segmenter import Segmenter
        from models.schemas import WhisperResult

        whisper_result = WhisperResult(
            text="你好世界",
            segments=[],
            duration=1.0,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "segments": [
                    {
                        "index": 0,
                        "summary": "问候",
                        "start_text": "你好",
                        "end_text": "世界",
                    }
                ]
            },
            ensure_ascii=False,
        )

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        segmenter = Segmenter(api_key="test_key")
        result = segmenter.segment(whisper_result)

        assert isinstance(result, SemanticResult)
        assert len(result.segments) == 1


class TestSegmentText:
    """测试 segment_text 快捷函数"""

    @patch("core.segmenter.Segmenter.segment")
    def test_segment_text_convenience(self, mock_segment: MagicMock):
        """测试 segment_text 快捷函数"""
        from core.segmenter import segment_text

        expected = SemanticResult(
            segments=[
                SemanticSegment(index=0, summary="测试", start_text="a", end_text="b")
            ]
        )
        mock_segment.return_value = expected

        result = segment_text("test text")

        assert result == expected
        mock_segment.assert_called_once()
