"""tests/test_exporters.py — 分镜导出格式"""

from unittest.mock import patch

import pytest

from models.schemas import FusedScene
from utils.exporters import export_clips, scenes_to_csv, scenes_to_markdown, scenes_to_srt

SCENES = [
    FusedScene(
        index=0, start_time=0.0, end_time=25.5,
        summary="开场", text="大家好", has_scene_cut=True,
    ),
    FusedScene(
        index=1, start_time=25.5, end_time=61.02,
        summary="产品介绍", text="这是新品", has_scene_cut=False,
    ),
]


def test_scenes_to_srt_format():
    srt = scenes_to_srt(SCENES)
    blocks = srt.strip().split("\n\n")
    assert len(blocks) == 2
    assert blocks[0].splitlines() == [
        "1",
        "00:00:00,000 --> 00:00:25,500",
        "大家好",
    ]
    assert "00:00:25,500 --> 00:01:01,020" in blocks[1]


def test_scenes_to_markdown_contains_title_and_rows():
    md = scenes_to_markdown(SCENES, title="发布会")
    assert md.startswith("# 发布会")
    assert "| 1 | 00:00 | 00:25 | 开场 | 大家好 |" in md


def test_scenes_to_csv_has_header_and_rows():
    rows = scenes_to_csv(SCENES).strip().splitlines()
    assert rows[0] == "序号,开始时间,结束时间,摘要,文字内容"
    assert rows[1].startswith("1,0.0,25.5,开场")
    assert len(rows) == 3


class _MockCompletedProcess:
    """模拟 subprocess.CompletedProcess"""

    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


def test_export_clips_ffmpeg_stderr_in_exception(tmp_path: object) -> None:
    """ffmpeg 失败时异常信息应包含 stderr 尾部内容"""
    fake_video = tmp_path / "video.mp4"  # type: ignore[attr-defined]
    fake_video.write_text("fake")
    out_dir = str(tmp_path / "clips")  # type: ignore[attr-defined]
    scenes = [SCENES[0]]

    with patch("utils.exporters.subprocess.run") as mock_run:
        mock_run.return_value = _MockCompletedProcess(
            returncode=1,
            stderr="[error] Invalid ffmpeg argument\n",
        )
        with patch("utils.exporters._ensure_ffmpeg"):
            with patch("utils.exporters.Path.mkdir"):
                with pytest.raises(RuntimeError) as exc_info:
                    export_clips(str(fake_video), scenes, out_dir)

    assert "ffmpeg 切割分镜 1 失败" in str(exc_info.value)
    assert "[error] Invalid ffmpeg argument" in str(exc_info.value)
