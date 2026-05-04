"""测试文字模糊匹配工具"""
import pytest

from models.schemas import WordTimestamp
from utils.text_matcher import (
    find_text_timestamp,
    match_boundary,
)


def make_words(pairs: list[tuple[str, float, float]]) -> list[WordTimestamp]:
    """辅助函数：快速创建 WordTimestamp 列表"""
    return [WordTimestamp(word=w, start=s, end=e) for w, s, e in pairs]


class TestFindTextTimestamp:
    """测试文字片段查找时间戳"""

    WORDS = make_words([
        ("大家好", 0.0, 1.0),
        ("欢迎", 1.0, 1.5),
        ("来到", 1.5, 2.0),
        ("今天的", 2.0, 2.5),
        ("视频", 2.5, 3.0),
        ("今天", 3.0, 3.5),
        ("我们", 3.5, 4.0),
        ("聊一下", 4.0, 4.5),
        ("人工智能", 4.5, 5.5),
        ("这个话题", 5.5, 6.5),
    ])

    def test_exact_match(self):
        """测试精确匹配文字"""
        result = find_text_timestamp("大家好欢迎来到今天的视频", self.WORDS)
        assert result is not None
        assert result["start"] == 0.0
        assert result["end"] == 3.0

    def test_partial_match(self):
        """测试部分匹配"""
        result = find_text_timestamp("欢迎来到", self.WORDS)
        assert result is not None
        assert result["start"] == 1.0
        assert result["end"] == 2.0

    def test_fuzzy_match_with_typo(self):
        """测试模糊匹配（有小差异）"""
        result = find_text_timestamp("大家好欢迎来到今天的视屏", self.WORDS)
        assert result is not None
        assert result["start"] >= 0.0

    def test_no_match_returns_none(self):
        """测试完全不匹配返回 None"""
        result = find_text_timestamp("完全不相关的内容", self.WORDS)
        assert result is None

    def test_empty_text_returns_none(self):
        """测试空文字返回 None"""
        result = find_text_timestamp("", self.WORDS)
        assert result is None

    def test_empty_words_returns_none(self):
        """测试空词表返回 None"""
        result = find_text_timestamp("大家好", [])
        assert result is None

    def test_single_word_match(self):
        """测试单个词匹配"""
        result = find_text_timestamp("人工智能", self.WORDS)
        assert result is not None
        assert result["start"] == 4.5
        assert result["end"] == 5.5


class TestMatchBoundary:
    """测试边界文字匹配"""

    WORDS = make_words([
        ("大家好", 0.0, 1.0),
        ("欢迎", 1.0, 1.5),
        ("来到", 1.5, 2.0),
        ("今天的", 2.0, 2.5),
        ("视频", 2.5, 3.0),
    ])

    def test_match_start_boundary(self):
        """测试匹配起始边界"""
        result = match_boundary("大家好", self.WORDS, direction="start")
        assert result is not None
        assert result == 0.0

    def test_match_end_boundary(self):
        """测试匹配结束边界"""
        result = match_boundary("视频", self.WORDS, direction="end")
        assert result is not None
        assert result == 3.0

    def test_fuzzy_boundary_match(self):
        """测试模糊匹配边界"""
        result = match_boundary("大家好欢迎", self.WORDS, direction="start")
        assert result is not None
        assert result == 0.0

    def test_invalid_direction_raises(self):
        """测试无效方向参数抛出异常"""
        with pytest.raises(ValueError):
            match_boundary("大家好", self.WORDS, direction="invalid")
