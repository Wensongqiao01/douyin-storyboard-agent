"""分镜导出工具：SRT / Markdown / CSV / 视频片段"""

import csv
import io
import subprocess
import zipfile
from pathlib import Path

from models.schemas import FusedScene


def _fmt_srt_time(seconds: float) -> str:
    """秒 → SRT 时间格式 HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_mmss(seconds: float) -> str:
    """秒 → MM:SS"""
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def scenes_to_srt(scenes: list[FusedScene]) -> str:
    """将分镜列表导出为 SRT 字幕格式字符串"""
    blocks = [
        f"{i}\n{_fmt_srt_time(sc.start_time)} --> {_fmt_srt_time(sc.end_time)}\n{sc.text}"
        for i, sc in enumerate(scenes, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


def scenes_to_markdown(scenes: list[FusedScene], title: str = "分镜稿") -> str:
    """将分镜列表导出为 Markdown 表格格式字符串"""
    lines = [
        f"# {title}",
        "",
        "| 序号 | 开始 | 结束 | 摘要 | 文字内容 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sc in scenes:
        text = sc.text.replace("|", "\\|").replace("\n", " ")
        summary = sc.summary.replace("|", "\\|")
        lines.append(
            f"| {sc.index + 1} | {_fmt_mmss(sc.start_time)} "
            f"| {_fmt_mmss(sc.end_time)} | {summary} | {text} |"
        )
    return "\n".join(lines) + "\n"


def scenes_to_csv(scenes: list[FusedScene]) -> str:
    """将分镜列表导出为 CSV 格式字符串"""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["序号", "开始时间", "结束时间", "摘要", "文字内容"])
    for sc in scenes:
        writer.writerow(
            [sc.index + 1, sc.start_time, sc.end_time, sc.summary, sc.text]
        )
    return buf.getvalue()


def export_clips(video_path: str, scenes: list[FusedScene], out_dir: str) -> str:
    """用 ffmpeg 按分镜切割视频并打包 zip，返回 zip 路径

    -c copy 不重编码，速度快；切点可能有 ±1 关键帧误差，剪辑师可接受。
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for sc in scenes:
        clip_path = Path(out_dir) / f"scene_{sc.index + 1:02d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(sc.start_time), "-to", str(sc.end_time),
            "-i", video_path, "-c", "copy", str(clip_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    zip_path = Path(out_dir) / "clips.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sorted(Path(out_dir).glob("scene_*.mp4")):
            zf.write(f, f.name)
    return str(zip_path)
