"""测试画面场景检测模块"""
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import SceneCut, SceneCutsResult


class TestSceneDetector:
    """测试 SceneDetector"""

    @patch("core.scene_detector.open_video")
    @patch("core.scene_detector.SceneManager")
    @patch("core.scene_detector.ContentDetector")
    @patch("core.scene_detector.Path.exists")
    def test_successful_detection(
        self,
        mock_exists: MagicMock,
        mock_detector_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_open_video: MagicMock,
        tmp_path,
    ):
        """测试成功检测场景切点"""
        from core.scene_detector import SceneDetector

        video_path = str(tmp_path / "video.mp4")
        mock_exists.return_value = True

        # 模拟切点
        mock_cut1 = MagicMock()
        mock_cut1.get_seconds.return_value = 5.0
        mock_cut1.frame_num = 150

        mock_cut2 = MagicMock()
        mock_cut2.get_seconds.return_value = 12.5
        mock_cut2.frame_num = 375

        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm
        mock_sm.get_cut_list.return_value = [mock_cut1, mock_cut2]

        mock_video = MagicMock()
        mock_video.duration.frame_num = 600
        mock_open_video.return_value = mock_video

        detector = SceneDetector(threshold=30.0)
        result = detector.detect(video_path)

        assert isinstance(result, SceneCutsResult)
        assert len(result.cuts) == 2
        assert result.cuts[0].time == 5.0
        assert result.cuts[0].frame == 150
        assert result.cuts[1].time == 12.5
        assert result.cuts[1].frame == 375
        assert result.total_frames == 600

        mock_detector_cls.assert_called_once_with(threshold=30.0)
        mock_sm.add_detector.assert_called_once()
        mock_sm.detect_scenes.assert_called_once_with(mock_video)
        mock_sm.get_cut_list.assert_called_once()

    @patch("core.scene_detector.open_video")
    @patch("core.scene_detector.SceneManager")
    @patch("core.scene_detector.ContentDetector")
    @patch("core.scene_detector.Path.exists")
    def test_no_cuts_detected(
        self,
        mock_exists: MagicMock,
        mock_detector_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_open_video: MagicMock,
        tmp_path,
    ):
        """测试没有检测到场景切点"""
        from core.scene_detector import SceneDetector

        video_path = str(tmp_path / "video.mp4")
        mock_exists.return_value = True

        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm
        mock_sm.get_cut_list.return_value = []

        mock_video = MagicMock()
        mock_video.duration.frame_num = 300
        mock_open_video.return_value = mock_video

        detector = SceneDetector()
        result = detector.detect(video_path)

        assert isinstance(result, SceneCutsResult)
        assert len(result.cuts) == 0
        assert result.total_frames == 300

    @patch("core.scene_detector.Path.exists")
    def test_video_not_found(self, mock_exists: MagicMock, tmp_path):
        """测试视频文件不存在"""
        from core.scene_detector import SceneDetector

        video_path = str(tmp_path / "nonexistent.mp4")
        mock_exists.return_value = False

        detector = SceneDetector()
        with pytest.raises(FileNotFoundError, match="视频文件不存在"):
            detector.detect(video_path)

    @patch("core.scene_detector.open_video")
    @patch("core.scene_detector.SceneManager")
    @patch("core.scene_detector.ContentDetector")
    @patch("core.scene_detector.Path.exists")
    def test_detection_failure(
        self,
        mock_exists: MagicMock,
        mock_detector_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_open_video: MagicMock,
        tmp_path,
    ):
        """测试场景检测失败"""
        from core.scene_detector import SceneDetector

        video_path = str(tmp_path / "video.mp4")
        mock_exists.return_value = True
        mock_sm_cls.side_effect = Exception("OpenCV error")

        detector = SceneDetector()
        with pytest.raises(RuntimeError, match="场景检测失败"):
            detector.detect(video_path)

    @patch("core.scene_detector.open_video")
    @patch("core.scene_detector.SceneManager")
    @patch("core.scene_detector.ContentDetector")
    @patch("core.scene_detector.Path.exists")
    def test_custom_threshold(
        self,
        mock_exists: MagicMock,
        mock_detector_cls: MagicMock,
        mock_sm_cls: MagicMock,
        mock_open_video: MagicMock,
        tmp_path,
    ):
        """测试自定义检测阈值"""
        from core.scene_detector import SceneDetector

        video_path = str(tmp_path / "video.mp4")
        mock_exists.return_value = True

        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm
        mock_sm.get_cut_list.return_value = []

        mock_video = MagicMock()
        mock_video.duration.frame_num = 300
        mock_open_video.return_value = mock_video

        detector = SceneDetector(threshold=50.0)
        detector.detect(video_path)

        mock_detector_cls.assert_called_once_with(threshold=50.0)


class TestDetectScenes:
    """测试 detect_scenes 快捷函数"""

    @patch("core.scene_detector.SceneDetector.detect")
    def test_detect_scenes_convenience(self, mock_detect: MagicMock, tmp_path):
        """测试 detect_scenes 快捷函数"""
        from core.scene_detector import detect_scenes

        video_path = str(tmp_path / "video.mp4")
        expected = SceneCutsResult(
            cuts=[SceneCut(time=5.0, frame=150)],
            total_frames=300,
        )
        mock_detect.return_value = expected

        result = detect_scenes(video_path)

        assert result == expected
        mock_detect.assert_called_once()
