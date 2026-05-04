"""画面场景检测模块

使用 PySceneDetect 检测视频中的场景切换点（镜头切变）。
"""

from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from scenedetect import ContentDetector, SceneManager, open_video
except ImportError:
    open_video = None  # type: ignore[assignment]
    SceneManager = None  # type: ignore[assignment]
    ContentDetector = None  # type: ignore[assignment]

from config import config
from models.schemas import SceneCut, SceneCutsResult


class SceneDetector:
    """PySceneDetect 场景检测器"""

    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold or config.scene_detect_threshold

    def detect(self, video_path: str) -> SceneCutsResult:
        """检测视频场景切点

        Args:
            video_path: 输入视频文件路径

        Returns:
            SceneCutsResult 包含切点列表和总帧数

        Raises:
            FileNotFoundError: 视频文件不存在
            RuntimeError: 场景检测失败
        """
        if not Path(video_path).exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        if open_video is None or SceneManager is None:
            raise RuntimeError("PySceneDetect 未安装")

        logger.info("开始场景检测: {} (threshold={})", video_path, self.threshold)
        try:
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self.threshold))
            scene_manager.detect_scenes(video)
            cut_list = scene_manager.get_cut_list()
        except Exception as e:
            logger.error("场景检测失败: {}", e)
            raise RuntimeError(f"场景检测失败: {e}") from e

        cuts = [
            SceneCut(
                time=cut.get_seconds(),
                frame=cut.frame_num,
            )
            for cut in (cut_list or [])
        ]

        total_frames = video.duration.frame_num if video.duration else 0

        logger.info("场景检测完成: {} 个切点, {} 帧", len(cuts), total_frames)
        return SceneCutsResult(cuts=cuts, total_frames=total_frames)


def detect_scenes(
    video_path: str,
    threshold: Optional[float] = None,
) -> SceneCutsResult:
    """快捷函数：检测视频场景切点

    Args:
        video_path: 输入视频文件路径
        threshold: 检测阈值，越小越敏感

    Returns:
        SceneCutsResult 场景检测结果
    """
    detector = SceneDetector(threshold=threshold)
    return detector.detect(video_path)
