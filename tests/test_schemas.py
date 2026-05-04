"""测试数据模型"""
import pytest
from pydantic import ValidationError

from models.schemas import (
    TaskStatus,
    WordTimestamp,
    WhisperResult,
    SceneCut,
    SceneCutsResult,
    SemanticSegment,
    SemanticResult,
    FusedScene,
    TaskResult,
)


class TestTaskStatus:
    """测试任务状态枚举"""

    def test_has_required_states(self):
        """测试包含必要的状态值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.DOWNLOADING.value == "downloading"
        assert TaskStatus.TRANSCRIBING.value == "transcribing"
        assert TaskStatus.DETECTING.value == "detecting"
        assert TaskStatus.SEGMENTING.value == "segmenting"
        assert TaskStatus.FUSING.value == "fusing"
        assert TaskStatus.DONE.value == "done"
        assert TaskStatus.ERROR.value == "error"


class TestWordTimestamp:
    """测试字级时间戳模型"""

    def test_valid_word_timestamp(self):
        """测试合法输入"""
        wt = WordTimestamp(word="你好", start=0.0, end=0.5)
        assert wt.word == "你好"
        assert wt.start == 0.0
        assert wt.end == 0.5

    def test_start_greater_than_end_raises(self):
        """测试 start > end 时抛出异常"""
        with pytest.raises(ValidationError):
            WordTimestamp(word="你好", start=1.0, end=0.5)

    def test_negative_start_raises(self):
        """测试负数 start 抛出异常"""
        with pytest.raises(ValidationError):
            WordTimestamp(word="你好", start=-0.1, end=0.5)


class TestWhisperResult:
    """测试 Whisper 转写结果模型"""

    def test_valid_whisper_result(self):
        """测试合法输入"""
        words = [
            WordTimestamp(word="你好", start=0.0, end=0.5),
            WordTimestamp(word="世界", start=0.5, end=1.0),
        ]
        result = WhisperResult(text="你好世界", segments=words, duration=1.0)
        assert result.text == "你好世界"
        assert len(result.segments) == 2
        assert result.duration == 1.0

    def test_empty_segments(self):
        """测试空 segments"""
        result = WhisperResult(text="", segments=[], duration=0.0)
        assert result.text == ""
        assert result.segments == []


class TestSceneCut:
    """测试场景切点模型"""

    def test_valid_scene_cut(self):
        """测试合法输入"""
        cut = SceneCut(time=10.5, frame=300)
        assert cut.time == 10.5
        assert cut.frame == 300

    def test_negative_frame_raises(self):
        """测试负数 frame 抛出异常"""
        with pytest.raises(ValidationError):
            SceneCut(time=10.5, frame=-1)


class TestSceneCutsResult:
    """测试场景切点结果模型"""

    def test_valid_scene_cuts_result(self):
        """测试合法输入"""
        cuts = [
            SceneCut(time=5.0, frame=150),
            SceneCut(time=10.0, frame=300),
        ]
        result = SceneCutsResult(cuts=cuts, total_frames=600)
        assert len(result.cuts) == 2
        assert result.total_frames == 600

    def test_empty_cuts(self):
        """测试空切点列表"""
        result = SceneCutsResult(cuts=[], total_frames=600)
        assert result.cuts == []


class TestSemanticSegment:
    """测试语义分镜模型"""

    def test_valid_semantic_segment(self):
        """测试合法输入"""
        segment = SemanticSegment(
            index=0,
            summary="开场介绍",
            start_text="大家好",
            end_text="我们开始吧",
        )
        assert segment.index == 0
        assert segment.summary == "开场介绍"

    def test_missing_summary(self):
        """测试缺少 summary 时抛出异常"""
        with pytest.raises(ValidationError):
            SemanticSegment(
                index=0,
                start_text="大家好",
                end_text="我们开始吧",
            )


class TestSemanticResult:
    """测试语义分镜结果模型"""

    def test_valid_semantic_result(self):
        """测试合法输入"""
        segments = [
            SemanticSegment(
                index=0, summary="开场", start_text="大家好", end_text="开始吧"
            ),
            SemanticSegment(
                index=1, summary="正文", start_text="首先", end_text="最后"
            ),
        ]
        result = SemanticResult(segments=segments)
        assert len(result.segments) == 2

    def test_segments_out_of_order_raises(self):
        """测试分镜 index 不连续时抛出异常"""
        segments = [
            SemanticSegment(
                index=0, summary="开场", start_text="大家好", end_text="开始吧"
            ),
            SemanticSegment(
                index=2, summary="跳过1", start_text="首先", end_text="最后"
            ),
        ]
        with pytest.raises(ValidationError):
            SemanticResult(segments=segments)


class TestFusedScene:
    """测试融合分镜模型"""

    def test_valid_fused_scene(self):
        """测试合法输入"""
        scene = FusedScene(
            index=0,
            start_time=0.0,
            end_time=8.5,
            summary="开场介绍",
            text="大家好，欢迎来到今天的视频",
            has_scene_cut=True,
        )
        assert scene.start_time == 0.0
        assert scene.end_time == 8.5
        assert scene.has_scene_cut is True

    def test_no_scene_cut(self):
        """测试无画面切点"""
        scene = FusedScene(
            index=0,
            start_time=0.0,
            end_time=5.0,
            summary="开场",
            text="大家好",
            has_scene_cut=False,
        )
        assert scene.has_scene_cut is False


class TestTaskResult:
    """测试任务结果模型"""

    def test_valid_task_result(self):
        """测试完整任务结果"""
        scene = FusedScene(
            index=0,
            start_time=0.0,
            end_time=5.0,
            summary="开场",
            text="大家好",
            has_scene_cut=False,
        )
        result = TaskResult(
            task_id="test-001",
            status=TaskStatus.DONE,
            title="测试视频标题",
            scenes=[scene],
        )
        assert result.task_id == "test-001"
        assert result.status == TaskStatus.DONE
        assert len(result.scenes) == 1

    def test_error_result_no_scenes(self):
        """测试错误状态无分镜"""
        result = TaskResult(
            task_id="test-002",
            status=TaskStatus.ERROR,
            title="",
            scenes=[],
            error_message="下载失败",
        )
        assert result.error_message == "下载失败"
        assert result.scenes == []

    def test_default_error_message(self):
        """测试默认 error_message 为 None"""
        scene = FusedScene(
            index=0,
            start_time=0.0,
            end_time=5.0,
            summary="开场",
            text="大家好",
            has_scene_cut=False,
        )
        result = TaskResult(
            task_id="test-003",
            status=TaskStatus.DONE,
            title="测试",
            scenes=[scene],
        )
        assert result.error_message is None
