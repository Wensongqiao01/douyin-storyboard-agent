"""tests/test_exporters.py — 分镜导出格式"""

from models.schemas import FusedScene
from utils.exporters import scenes_to_csv, scenes_to_markdown, scenes_to_srt

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
