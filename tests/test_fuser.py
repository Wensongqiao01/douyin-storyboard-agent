"""测试融合对齐模块"""
import pytest

from models.schemas import (
    FusedScene,
    SceneCut,
    SceneCutsResult,
    SemanticResult,
    SemanticSegment,
    WhisperResult,
    WordTimestamp,
)


class TestFuser:
    """测试 Fuser"""

    def test_fuse_basic(self):
        """测试基本的融合对齐"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="开场", start_text="大家好", end_text="今天"
                ),
                SemanticSegment(
                    index=1, summary="正题", start_text="今天我们来", end_text="再见"
                ),
            ]
        )
        scenes = SceneCutsResult(
            cuts=[SceneCut(time=3.0, frame=90)],
            total_frames=300,
        )
        whisper = WhisperResult(
            text="大家好今天我们来再见",
            segments=[
                WordTimestamp(word="大家好", start=0.0, end=1.5),
                WordTimestamp(word="今天我们来", start=1.5, end=3.0),
                WordTimestamp(word="再见", start=3.0, end=4.0),
            ],
            duration=4.0,
        )

        fuser = Fuser()
        result = fuser.fuse(semantic, scenes, whisper)

        assert len(result) == 2
        assert result[0].index == 0
        assert result[0].summary == "开场"
        assert result[0].start_time == 0.0
        assert result[0].end_time == 1.5
        assert result[0].text == "大家好"

        assert result[1].index == 1
        assert result[1].summary == "正题"
        assert result[1].start_time == 1.5
        assert result[1].end_time == 4.0
        assert result[1].text == "今天我们来再见"

    def test_fuse_with_scene_cut_alignment(self):
        """测试场景切点对齐"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="引言", start_text="哈喽", end_text="进入"
                ),
                SemanticSegment(
                    index=1, summary="主体", start_text="今天", end_text="谢谢"
                ),
            ]
        )
        scenes = SceneCutsResult(
            cuts=[SceneCut(time=2.0, frame=60)],
            total_frames=300,
        )
        whisper = WhisperResult(
            text="哈喽大家今天谢谢",
            segments=[
                WordTimestamp(word="哈喽", start=0.0, end=0.5),
                WordTimestamp(word="大家", start=0.5, end=1.5),
                WordTimestamp(word="今天", start=1.5, end=2.5),
                WordTimestamp(word="谢谢", start=2.5, end=3.5),
            ],
            duration=3.5,
        )

        fuser = Fuser(align_window=1.0)
        result = fuser.fuse(semantic, scenes, whisper)

        # 语义边界可能在 1.5s，场景切点在 2.0s，在 1.0s 窗口内，应对齐到切点
        assert len(result) == 2
        assert result[0].end_time == 2.0
        assert result[0].has_scene_cut is True

    def test_fuse_scene_cut_outside_window(self):
        """测试场景切点超出对齐窗口"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="前段", start_text="开始", end_text="中间"
                ),
                SemanticSegment(
                    index=1, summary="后段", start_text="继续", end_text="结束"
                ),
            ]
        )
        scenes = SceneCutsResult(
            cuts=[SceneCut(time=10.0, frame=300)],
            total_frames=600,
        )
        whisper = WhisperResult(
            text="开始中间继续结束",
            segments=[
                WordTimestamp(word="开始", start=0.0, end=1.0),
                WordTimestamp(word="中间", start=1.0, end=2.0),
                WordTimestamp(word="继续", start=2.0, end=3.0),
                WordTimestamp(word="结束", start=3.0, end=4.0),
            ],
            duration=4.0,
        )

        fuser = Fuser(align_window=0.5)
        result = fuser.fuse(semantic, scenes, whisper)

        # 语义边界在 2.0s，场景切点在 10.0s，超出 0.5s 窗口
        assert result[0].end_time == 2.0
        assert result[0].has_scene_cut is False

    def test_fuse_no_scene_cuts(self):
        """测试无场景切点"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="唯一标题", start_text="文", end_text="章"
                ),
            ]
        )
        scenes = SceneCutsResult(cuts=[], total_frames=300)
        whisper = WhisperResult(
            text="文章",
            segments=[
                WordTimestamp(word="文", start=0.0, end=0.5),
                WordTimestamp(word="章", start=0.5, end=1.0),
            ],
            duration=1.0,
        )

        fuser = Fuser()
        result = fuser.fuse(semantic, scenes, whisper)

        assert len(result) == 1
        assert result[0].summary == "唯一标题"
        assert result[0].has_scene_cut is False

    def test_fuse_single_segment_fallback(self):
        """测试单个分镜（无匹配边界时使用全文时间）"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="全文", start_text="无匹配", end_text="文本"
                ),
            ]
        )
        scenes = SceneCutsResult(cuts=[], total_frames=300)
        whisper = WhisperResult(
            text="完全不同的文字内容",
            segments=[
                WordTimestamp(word="完全", start=0.0, end=0.5),
                WordTimestamp(word="不同", start=0.5, end=1.0),
            ],
            duration=1.0,
        )

        fuser = Fuser()
        result = fuser.fuse(semantic, scenes, whisper)

        # start_text 和 end_text 无法匹配时，使用全文起止时间
        assert len(result) == 1
        assert result[0].start_time == 0.0
        assert result[0].end_time == 1.0

    def test_fuse_with_confidence(self):
        """测试有 scene_cut 标记的 should have_scene_cut=True"""
        from core.fuser import Fuser

        semantic = SemanticResult(
            segments=[
                SemanticSegment(
                    index=0, summary="A", start_text="A", end_text="B"
                ),
                SemanticSegment(
                    index=1, summary="B段", start_text="B", end_text="C"
                ),
            ]
        )
        scenes = SceneCutsResult(
            cuts=[SceneCut(time=1.0, frame=30)],
            total_frames=300,
        )
        whisper = WhisperResult(
            text="ABC",
            segments=[
                WordTimestamp(word="A", start=0.0, end=0.3),
                WordTimestamp(word="B", start=0.3, end=0.6),
                WordTimestamp(word="C", start=0.6, end=1.0),
            ],
            duration=1.0,
        )

        fuser = Fuser(align_window=0.5)
        result = fuser.fuse(semantic, scenes, whisper)

        assert len(result) == 2
        assert result[0].end_time == 0.6
        # confident 边界不切时间，但场景切点在窗口内仍标记 has_scene_cut
        assert result[0].has_scene_cut is True

    def test_fuse_empty_segments(self):
        """测试空分镜列表"""
        from core.fuser import Fuser

        semantic = SemanticResult(segments=[])
        scenes = SceneCutsResult(cuts=[], total_frames=0)
        whisper = WhisperResult(text="", segments=[], duration=0.0)

        fuser = Fuser()
        result = fuser.fuse(semantic, scenes, whisper)

        assert result == []


class TestFuseScenes:
    """测试 fuse_scenes 快捷函数"""

    def test_fuse_scenes_convenience(self):
        """测试 fuse_scenes 快捷函数"""
        from core.fuser import fuse_scenes

        semantic = SemanticResult(segments=[])
        scenes = SceneCutsResult(cuts=[], total_frames=0)
        whisper = WhisperResult(text="", segments=[], duration=0.0)

        result = fuse_scenes(semantic, scenes, whisper)
        assert result == []
