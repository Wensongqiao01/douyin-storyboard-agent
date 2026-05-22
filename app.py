"""Gradio Web 界面

提供视频分镜分析的用户交互界面，支持单链接分析和批量分析。
"""
import html
import re
from pathlib import Path

import gradio as gr
from loguru import logger

from config import config
from core.pipeline import batch_run_pipeline, batch_run_pipeline_stream, run_pipeline
from models.schemas import BatchResult, FusedScene, TaskResult, TaskStatus


# ====== 霓虹赛博风全局样式 ======
# 注意：Gradio 6 会把所有 CSS 颜色值转成 rgb() 格式，但这不影响功能。
# 所有选择器不要依赖 Gradio 内部类名（随时可能变），尽量用属性选择器和标签名。
NEON_CSS = """
/* ========== 全局基础层 ========== */
html, body, .gradio-container, .gradio-container * {
    color: #d0d0e0 !important;
}
body, .gradio-container {
    background: #0a0a14 !important;
}

/* ========== 标题 / 头部 Banner ========== */
h1, h2, h3, h4, h5, h6,
.markdown-text h1, .markdown-text h2, .markdown-text h3,
.markdown-text h4, .markdown-text h5, .markdown-text h6 {
    background: linear-gradient(90deg, #00f5ff, #a855f7) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important}
.markdown-text p, .markdown-text span, .markdown-text div {
    color: #b0b0c8 !important;
}

/* ========== 标签 / 说明文字 ========== */
label, .label-text, span.label, .gr-form-text, .gr-block gr-box,
.gr-input-label, .info, .description {
    color: #7a7aaa !important;
    font-weight: 500 !important;
}

/* ========== 文本框 / 输入框 / 数字输入 / 下拉框 ========== */
input, textarea, select,
.gr-box input, .gr-box textarea, .gr-box select {
    background: #0f0f24 !important;
    border: 1px solid #2a1a4a !important;
    color: #e0e0e0 !important;
    border-radius: 8px !important;
}
input:focus, textarea:focus, select:focus {
    border-color: #00f5ff !important;
    box-shadow: 0 0 12px rgba(0, 245, 255, 0.15) !important;
    outline: none !important;
}
input::placeholder, textarea::placeholder {
    color: #4a4a6a !important;
}

/* ========== 主按钮 ========== */
button#start-analysis, button#start-batch,
button.gr-button.gr-button--primary,
.gr-button.primary {
    background: linear-gradient(135deg, #00f5ff, #a855f7) !important;
    border: none !important;
    color: #000 !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
button#start-analysis:hover, button#start-batch:hover,
button.gr-button.gr-button--primary:hover {
    box-shadow: 0 0 24px rgba(0, 245, 255, 0.3) !important;
    transform: translateY(-1px) !important;
}
/* 次要按钮（灰色） */
button.gr-button:not(.gr-button--primary) {
    background: #1a1a35 !important;
    border: 1px solid #2a1a4a !important;
    color: #b0b0c8 !important;
    border-radius: 8px !important;
}
button.gr-button:not(.gr-button--primary):hover {
    border-color: #00f5ff !important;
    color: #00f5ff !important;
}

/* ========== 选项卡 / 标签页 ========== */
button[role="tab"] {
    color: #7a7aaa !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
}
button[role="tab"][aria-selected="true"] {
    color: #00f5ff !important;
    border-bottom: 2px solid #00f5ff !important;
}
button[role="tab"]:hover {
    color: #a855f7 !important;
}

/* ========== 折叠面板 ========== */
.gr-accordion, details {
    background: linear-gradient(135deg, #0f0f24, #1a0a2e) !important;
    border: 1px solid #2a1a4a !important;
    border-radius: 8px !important;
}
.gr-accordion summary, details summary {
    color: #7a7aaa;
    font-weight: 500;
    padding: 10px 14px;
}

/* ========== 卡片 / 面板 / 容器 ========== */
.gr-box, .panel, .card, .contain, .block,
.gr-form, .gr-panel, .gr-group {
    background: linear-gradient(135deg, #0f0f24, #1a0a2e) !important;
    border: 1px solid #2a1a4a !important;
    border-radius: 12px !important;
}

/* ========== 滑块 ========== */
input[type="range"] {
    accent-color: #00f5ff !important;
}
input[type="range"]::-webkit-slider-runnable-track {
    background: #2a1a4a !important;
    border-radius: 4px !important;
}
input[type="range"]::-webkit-slider-thumb {
    background: #00f5ff !important;
    border: none !important;
    border-radius: 50% !important;
}

/* ========== 复选框 / 单选框 ========== */
input[type="checkbox"], input[type="radio"] {
    accent-color: #a855f7 !important;
}
input[type="checkbox"] + label, input[type="radio"] + label {
    color: #b0b0c8 !important;
}

/* ========== 进度条 ========== */
progress, .gr-progress {
    background: #0f0f24 !important;
    border: 1px solid #2a1a4a !important;
    border-radius: 8px !important;
}
progress::-webkit-progress-bar {
    background: #0f0f24 !important;
    border-radius: 8px !important;
}
progress::-webkit-progress-value {
    background: linear-gradient(90deg, #00f5ff, #a855f7) !important;
    border-radius: 8px !important;
}

/* ========== 文件上传 ========== */
.gr-upload, .gr-file {
    background: linear-gradient(135deg, #0f0f24, #1a0a2e) !important;
    border: 1px dashed #2a1a4a !important;
    border-radius: 8px !important;
    color: #7a7aaa !important;
}
.gr-upload:hover, .gr-file:hover {
    border-color: #00f5ff !important;
}

/* ========== 数据表格 / 数据集 ========== */
.gr-dataframe, table, .gr-table {
    background: #0a0a14 !important;
    border: 1px solid #2a1a4a !important;
}
.gr-dataframe th, table th, .gr-table th {
    background: #0f0f24 !important;
    color: #a855f7 !important;
    border-bottom: 2px solid #2a1a4a !important;
}
.gr-dataframe td, table td, .gr-table td {
    color: #b0b0c8 !important;
    border-bottom: 1px solid #2a1a4a !important;
}

/* ========== 提示 / 信息 / 警告 ========== */
.gr-info, .message.info {
    background: #0f0f24 !important;
    border: 1px solid #00f5ff40 !important;
    color: #b0b0c8 !important;
}
.gr-warning, .message.warning {
    background: linear-gradient(135deg, #0f0f24, #1a0a2e) !important;
    border: 1px solid #ff00aa40 !important;
    color: #ff00aa !important;
}
.gr-error, .message.error {
    background: linear-gradient(135deg, #0f0f24, #1a0a2e) !important;
    border: 1px solid #ff0040 !important;
    color: #ff4466 !important;
}

/* ========== 页脚 ========== */
footer, .footer, .gr-footer {
    color: #4a4a6a !important;
    font-size: 0.8em !important;
}

/* ========== 滚动条 ========== */
::-webkit-scrollbar {
    width: 8px !important;
    height: 8px !important;
}
::-webkit-scrollbar-track {
    background: #0a0a14 !important;
}
::-webkit-scrollbar-thumb {
    background: #2a1a4a !important;
    border-radius: 4px !important;
}
::-webkit-scrollbar-thumb:hover {
    background: #a855f7 !important;
}

/* ========== 选择高亮 ========== */
::selection {
    background: #a855f740 !important;
    color: #fff !important;
}
"""

_URL_PATTERN = re.compile(r"https?://[^\s。，）)]+")

def _extract_url(text: str) -> str | None:
    """从输入文本中提取第一个链接

    抖音分享文本可能包含表情、文字和链接，
    此函数自动提取其中的 URL。
    """
    if not text or not text.strip():
        return None
    text = text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    match = _URL_PATTERN.search(text)
    if match:
        url = match.group(0).rstrip("/")
        logger.info("从分享文本中提取到链接: {}", url)
        return url
    return None


def _format_time(seconds: float) -> str:
    """将秒格式化为 mm:ss"""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def _build_html_result(result: TaskResult) -> str:
    """构建结果 HTML（单链接）— 霓虹赛博风"""
    if result.status == TaskStatus.ERROR:
        return f'<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">❌ 任务失败：{html.escape(result.error_message)}</div>'

    if not result.scenes:
        return '<div style="color:#7a7aaa;padding:16px;text-align:center;">未检测到分镜</div>'

    total_duration = result.scenes[-1].end_time - result.scenes[0].start_time
    cards = ""
    for scene in result.scenes:
        cut_badge = ""
        if scene.has_scene_cut:
            cut_badge = '<span style="background:#00f5ff20;color:#00f5ff;font-size:0.75em;padding:2px 8px;border-radius:4px;">有切点</span>'
        cards += f"""
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                <span style="font-weight:bold;font-size:1.1em;background:linear-gradient(90deg,#00f5ff,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">#{scene.index + 1}</span>
                <span style="color:#7a7aaa;font-size:0.9em;">{_format_time(scene.start_time)} ~ {_format_time(scene.end_time)}</span>
                {cut_badge}
            </div>
            <div style="font-size:1.05em;font-weight:500;color:#e0e0e0;margin-bottom:4px;">{html.escape(scene.summary)}</div>
            <div style="color:#7a7aaa;font-size:0.9em;line-height:1.6;">{html.escape(scene.text)}</div>
        </div>
        """
    header = f'<div style="color:#7a7aaa;margin-bottom:16px;padding:8px 12px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #00f5ff20;border-radius:6px;">共 <span style="color:#00f5ff;font-weight:600;">{len(result.scenes)}</span> 个分镜 · 总时长 {_format_time(total_duration)}</div>'

    return header + cards


def _build_batch_html_result(result: BatchResult) -> str:
    """构建批量结果 HTML（霓虹赛博风）"""
    if result.total == 0:
        return '<div style="color:#7a7aaa;padding:16px;text-align:center;">未输入有效的链接</div>'

    # 汇总统计
    total_min = int(result.total_duration // 60)
    total_sec = int(result.total_duration % 60)
    summary = f"""
    <div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;">
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#7a7aaa;margin-bottom:4px;">总任务</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#e0e0e0;">{result.total}</span>
        </div>
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #22c55e40;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#7a7aaa;margin-bottom:4px;">成功</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#22c55e;">{result.succeeded}</span>
        </div>
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#7a7aaa;margin-bottom:4px;">失败</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#ff00aa;">{result.failed}</span>
        </div>
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#7a7aaa;margin-bottom:4px;">总时长</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#e0e0e0;">{total_min}:{total_sec:02d}</span>
        </div>
    </div>
    """

    # 每个任务是一个可折叠 details
    cards = ""
    for idx, r in enumerate(result.results):
        task_label = f"#{idx + 1}"
        if r.status == TaskStatus.ERROR:
            cards += f"""
            <details style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;margin-bottom:16px;overflow:hidden;">
                <summary style="padding:14px 16px;cursor:pointer;user-select:none;list-style:inside;">
                    <div style="display:inline-flex;align-items:center;gap:10px;width:100%;">
                        <span style="font-size:0.8em;color:#7a7aaa;">▶</span>
                        <span style="font-weight:700;color:#e0e0e0;min-width:28px;">{task_label}</span>
                        <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(r.url)}</span>
                        <span style="font-size:0.75em;padding:2px 8px;border-radius:4px;font-weight:600;background:#ff00aa20;color:#ff00aa;border:1px solid #ff00aa40;">失败</span>
                    </div>
                </summary>
                <div style="padding:0 16px 16px;border-top:1px solid #2a1a4a;">
                    <div style="color:#ff00aa;font-size:0.9em;padding:12px 0;">错误：{html.escape(r.error_message or "")}</div>
                </div>
            </details>
            """
        else:
            total_duration = 0
            if r.scenes:
                total_duration = r.scenes[-1].end_time - r.scenes[0].start_time

            table_rows = ""
            for scene in r.scenes:
                cut_mark = "🪓" if scene.has_scene_cut else ""
                table_rows += f"""
                <tr>
                    <td style="color:#00f5ff;font-weight:600;white-space:nowrap;padding:10px 12px;border-bottom:1px solid #2a1a4a;">#{scene.index + 1}</td>
                    <td style="color:#7a7aaa;white-space:nowrap;padding:10px 12px;border-bottom:1px solid #2a1a4a;">{_format_time(scene.start_time)} ~ {_format_time(scene.end_time)}</td>
                    <td style="color:#e0e0e0;font-weight:500;padding:10px 12px;border-bottom:1px solid #2a1a4a;">{html.escape(scene.summary)}</td>
                    <td style="color:#7a7aaa;padding:10px 12px;border-bottom:1px solid #2a1a4a;">{html.escape(scene.text)}</td>
                    <td style="text-align:center;padding:10px 12px;border-bottom:1px solid #2a1a4a;">{cut_mark}</td>
                </tr>
                """

            cards += f"""
            <details style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;margin-bottom:16px;overflow:hidden;">
                <summary style="padding:14px 16px;cursor:pointer;user-select:none;list-style:inside;">
                    <div style="display:inline-flex;align-items:center;gap:10px;width:100%;">
                        <span style="font-size:0.8em;color:#7a7aaa;">▶</span>
                        <span style="font-weight:700;color:#e0e0e0;min-width:28px;">{task_label}</span>
                        <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(r.url)}</span>
                        <span style="color:#7a7aaa;font-size:0.8em;white-space:nowrap;"><span style="color:#00f5ff;">{len(r.scenes)}</span> 个分镜 · {_format_time(total_duration)}</span>
                    </div>
                </summary>
                <div style="padding:0 16px 16px;border-top:1px solid #2a1a4a;">
                    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:0.9em;">
                        <thead>
                            <tr>
                                <th style="background:#0a0a14;color:#a855f7;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #2a1a4a;white-space:nowrap;">#</th>
                                <th style="background:#0a0a14;color:#a855f7;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #2a1a4a;white-space:nowrap;">时间</th>
                                <th style="background:#0a0a14;color:#a855f7;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #2a1a4a;white-space:nowrap;">摘要</th>
                                <th style="background:#0a0a14;color:#a855f7;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #2a1a4a;white-space:nowrap;">文字</th>
                                <th style="background:#0a0a14;color:#a855f7;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #2a1a4a;white-space:nowrap;">切点</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </details>
            """

    return summary + cards


def _build_progressive_batch_html(
    completed: dict[int, TaskResult],
    total: int,
    urls: list[str],
) -> str:
    """构建渐进式批量结果 HTML（霓虹赛博风）

    每完成一个任务就调用一次，实时展示进度。

    Args:
        completed: 已完成的任务字典 {索引: TaskResult}
        total: 总任务数
        urls: 原始 URL 列表
    """
    done_count = len(completed)
    percent = int(done_count / total * 100) if total > 0 else 0

    # 进度条
    progress_bar = f"""
    <div style="margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;color:#7a7aaa;font-size:0.85em;margin-bottom:6px;">
            <span>处理进度</span>
            <span>{done_count}/{total} · {percent}%</span>
        </div>
        <div style="background:#0f0f24;border-radius:8px;height:12px;overflow:hidden;border:1px solid #2a1a4a;">
            <div style="width:{percent}%;height:100%;background:linear-gradient(90deg,#00f5ff,#a855f7);border-radius:8px;transition:width 0.3s;"></div>
        </div>
    </div>
    """

    # 统计
    success_count = sum(
        1 for r in completed.values() if r.status == TaskStatus.DONE
    )
    fail_count = sum(
        1 for r in completed.values() if r.status == TaskStatus.ERROR
    )
    stats = f"""
    <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:8px 16px;text-align:center;flex:1;min-width:80px;">
            <span style="font-size:0.75em;color:#7a7aaa;display:block;">成功</span>
            <span style="font-size:1.3em;font-weight:bold;color:#22c55e;">{success_count}</span>
        </div>
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:8px 16px;text-align:center;flex:1;min-width:80px;">
            <span style="font-size:0.75em;color:#7a7aaa;display:block;">失败</span>
            <span style="font-size:1.3em;font-weight:bold;color:#ff00aa;">{fail_count}</span>
        </div>
        <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:8px 16px;text-align:center;flex:1;min-width:80px;">
            <span style="font-size:0.75em;color:#7a7aaa;display:block;">剩余</span>
            <span style="font-size:1.3em;font-weight:bold;color:#7a7aaa;">{total - done_count}</span>
        </div>
    </div>
    """

    # 任务卡片
    cards = ""
    for i in range(total):
        url = urls[i] if i < len(urls) else ""
        if i in completed:
            r = completed[i]
            if r.status == TaskStatus.ERROR:
                cards += f"""
                <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;padding:14px 16px;margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="color:#ff00aa;font-weight:bold;">✕</span>
                        <span style="font-weight:600;color:#e0e0e0;min-width:24px;">#{i+1}</span>
                        <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(url)}</span>
                        <span style="font-size:0.75em;padding:2px 8px;border-radius:4px;font-weight:600;background:#ff00aa20;color:#ff00aa;border:1px solid #ff00aa40;">失败</span>
                    </div>
                    <div style="margin-top:8px;color:#ff00aa;font-size:0.85em;padding-left:34px;">{html.escape(r.error_message or "")}</div>
                </div>
                """
            elif r.status == TaskStatus.DONE:
                total_dur = 0
                if r.scenes:
                    total_dur = r.scenes[-1].end_time - r.scenes[0].start_time
                cards += f"""
                <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #22c55e40;border-radius:8px;padding:14px 16px;margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="color:#22c55e;font-weight:bold;">✓</span>
                        <span style="font-weight:600;color:#e0e0e0;min-width:24px;">#{i+1}</span>
                        <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(url)}</span>
                        <span style="color:#7a7aaa;font-size:0.8em;"><span style="color:#00f5ff;font-weight:600;">{len(r.scenes)}</span> 个分镜 · {_format_time(total_dur)}</span>
                    </div>
                </div>
                """
            else:
                cards += f"""
                <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:14px 16px;margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="color:#7a7aaa;font-weight:bold;">?</span>
                        <span style="font-weight:600;color:#e0e0e0;min-width:24px;">#{i+1}</span>
                        <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(url)}</span>
                        <span style="font-size:0.75em;padding:2px 8px;border-radius:4px;font-weight:600;background:#2a1a4a;color:#7a7aaa;">未知</span>
                    </div>
                </div>
                """
        else:
            cards += f"""
            <div style="background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #2a1a4a;border-radius:8px;padding:14px 16px;margin-bottom:8px;opacity:0.45;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="color:#7a7aaa;">⏳</span>
                    <span style="font-weight:600;color:#7a7aaa;min-width:24px;">#{i+1}</span>
                    <span style="color:#7a7aaa;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(url)}</span>
                    <span style="font-size:0.75em;padding:2px 8px;border-radius:4px;background:#2a1a4a;color:#7a7aaa;">等待中</span>
                </div>
            </div>
            """

    return progress_bar + stats + cards


def analyze(url: str, align_window: float, scene_threshold: float) -> str:
    """分析入口函数"""
    extracted = _extract_url(url)
    if not extracted:
        return '<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">未检测到视频链接，请粘贴抖音分享链接</div>'

    logger.info("开始分析: {}", extracted)
    try:
        result = run_pipeline(
            extracted,
            fuse_align_window=align_window if align_window > 0 else None,
            scene_threshold=scene_threshold if scene_threshold > 0 else None,
        )
        return _build_html_result(result)
    except Exception as e:
        logger.error("分析失败: {}", e)
        return f'<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">分析失败：{e}</div>'


def batch_analyze(urls_text: str, max_workers: int, align_window: float, scene_threshold: float) -> str:
    """批量分析入口函数"""
    if not urls_text or not urls_text.strip():
        return '<div style="color:#7a7aaa;padding:16px;text-align:center;">请输入视频链接，每行一个</div>'

    raw_lines = [line.strip() for line in urls_text.strip().split("\n") if line.strip()]
    urls: list[str] = []
    skipped = 0
    for line in raw_lines:
        url = _extract_url(line)
        if url:
            urls.append(url)
        else:
            skipped += 1
    if skipped:
        logger.warning("批量分析: {} 行未能提取到链接", skipped)
    if not urls:
        return '<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">未从输入中检测到有效链接</div>'
    if len(urls) > 50:
        urls = urls[:50]

    try:
        result = batch_run_pipeline(
            urls,
            max_workers=max_workers,
            fuse_align_window=align_window if align_window > 0 else None,
            scene_threshold=scene_threshold if scene_threshold > 0 else None,
        )
        return _build_batch_html_result(result)
    except Exception as e:
        logger.error("批量分析失败: {}", e)
        return f'<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">批量分析失败：{e}</div>'


def batch_analyze_stream(
    urls_text: str,
    max_workers: int,
    align_window: float,
    scene_threshold: float,
):
    """流式批量分析入口（生成器）

    实时展示每个任务的完成进度，最终输出完整的批量结果。
    """
    if not urls_text or not urls_text.strip():
        yield '<div style="color:#7a7aaa;padding:16px;text-align:center;">请输入视频链接，每行一个</div>'
        return

    raw_lines = [line.strip() for line in urls_text.strip().split("\n") if line.strip()]
    urls: list[str] = []
    for line in raw_lines:
        url = _extract_url(line)
        if url:
            urls.append(url)
    if not urls:
        yield '<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">未从输入中检测到有效链接</div>'
        return
    if len(urls) > 50:
        urls = urls[:50]

    total = len(urls)

    # 初始状态：全待处理
    yield _build_progressive_batch_html({}, total, urls)

    try:
        last_completed: dict[int, TaskResult] = {}
        for completed, _ in batch_run_pipeline_stream(
            urls,
            max_workers=max_workers,
            fuse_align_window=align_window if align_window > 0 else None,
            scene_threshold=scene_threshold if scene_threshold > 0 else None,
        ):
            last_completed = completed
            yield _build_progressive_batch_html(completed, total, urls)

        # 流结束后构建完整 BatchResult
        succeeded = [
            r for r in last_completed.values() if r.status == TaskStatus.DONE
        ]
        failed = [
            r for r in last_completed.values() if r.status == TaskStatus.ERROR
        ]
        total_dur = 0.0
        for r in succeeded:
            if r.scenes:
                total_dur += r.scenes[-1].end_time - r.scenes[0].start_time

        ordered = [last_completed.get(i) for i in range(total)]
        valid = [r for r in ordered if r is not None]

        result = BatchResult(
            total=len(valid),
            succeeded=len(succeeded),
            failed=len(failed),
            total_duration=total_dur,
            results=valid,
        )
        yield _build_batch_html_result(result)
    except Exception as e:
        logger.error("批量流式分析失败: {}", e)
        yield f'<div style="color:#ff00aa;padding:16px;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border:1px solid #ff00aa40;border-radius:8px;">批量分析失败：{e}</div>'


with gr.Blocks(title="视频分镜分析") as demo:
    demo.queue(default_concurrency_limit=1)

    gr.Markdown(
        """
    # 🎬 视频分镜分析

    输入抖音视频链接，自动提取语音、检测场景、生成结构化的分镜列表。
    """
    )

    with gr.Tabs():
        with gr.Tab("单链接分析"):
            # 输入区
            with gr.Row():
                url_input = gr.Textbox(
                    label="视频链接",
                    placeholder="请输入抖音视频分享链接...",
                    scale=4,
                )
                run_btn = gr.Button("开始分析", variant="primary", scale=1, min_width=120, elem_id="start-analysis")

            # 高级设置
            with gr.Accordion("高级设置", open=False):
                with gr.Row():
                    align_window_slider = gr.Slider(
                        minimum=0,
                        maximum=10,
                        value=config.fuse_align_window,
                        step=0.5,
                        label="对齐窗口（秒）",
                        info="语义边界匹配场景切点的最大时间差。设为 0 表示不限制。",
                    )
                    scene_threshold_slider = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=config.scene_detect_threshold,
                        step=1,
                        label="场景检测阈值",
                        info="画面变化灵敏度，值越小越敏感。设为 0 使用默认值。",
                    )

            gr.Markdown("&nbsp;")  # 间距

            # 结果区
            # sanitize_html=False 是必须的：Gradio 6.x 在 True 时会剥离我们构造的 HTML 结构和样式。
            # XSS 风险已通过 _build_html_result / _build_batch_html_result 中所有用户输入都
            # 经过 html.escape() 处理来消除。
            result_html = gr.HTML(label="分析结果", sanitize_html=False)

            run_btn.click(
                fn=lambda: '<div style="color:#7a7aaa;padding:32px 16px;text-align:center;font-size:1.1em;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border-radius:8px;border:1px solid #2a1a4a;">⏳ 正在分析视频，请耐心等待（通常需要 2-5 分钟）...</div>',
                outputs=result_html,
            ).then(
                fn=analyze,
                inputs=[url_input, align_window_slider, scene_threshold_slider],
                outputs=result_html,
            )

            url_input.submit(
                fn=lambda: '<div style="color:#7a7aaa;padding:32px 16px;text-align:center;font-size:1.1em;background:linear-gradient(135deg,#0f0f24,#1a0a2e);border-radius:8px;border:1px solid #2a1a4a;">⏳ 正在分析视频，请耐心等待（通常需要 2-5 分钟）...</div>',
                outputs=result_html,
            ).then(
                fn=analyze,
                inputs=[url_input, align_window_slider, scene_threshold_slider],
                outputs=result_html,
            )

        with gr.Tab("批量分析（最多 50 条）"):
            # 输入区
            batch_input = gr.Textbox(
                label="视频链接列表",
                placeholder="每行一个抖音视频链接...\nhttps://v.douyin.com/xxx/\nhttps://www.douyin.com/jingxuan?modal_id=xxx\n...",
                lines=8,
                max_lines=20,
            )
            batch_btn = gr.Button("开始批量分析", variant="primary", elem_id="start-batch")

            # 批量设置（紧跟在按钮下方，在结果之前）
            with gr.Accordion("批量设置", open=False):
                with gr.Row():
                    batch_max_workers = gr.Slider(
                        minimum=1,
                        maximum=8,
                        value=config.max_workers,
                        step=1,
                        label="并行数",
                        info=f"同时处理的任务数。根据 CPU 核心数自动计算={config.max_workers}。",
                    )
                    batch_align_window = gr.Slider(
                        minimum=0,
                        maximum=10,
                        value=config.fuse_align_window,
                        step=0.5,
                        label="对齐窗口（秒）",
                    )
                    batch_scene_threshold = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=config.scene_detect_threshold,
                        step=1,
                        label="场景检测阈值",
                    )

            gr.Markdown("&nbsp;")  # 间距

            # 结果区
            batch_result_html = gr.HTML(label="批量分析结果", sanitize_html=False)

            batch_btn.click(
                fn=batch_analyze_stream,
                inputs=[batch_input, batch_max_workers, batch_align_window, batch_scene_threshold],
                outputs=batch_result_html,
            )


if __name__ == "__main__":
    import os
    import logging
    logging.basicConfig(level=logging.INFO)
    os.environ["PATH"] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + os.environ.get("PATH", "")

    # 确保本地流量绕过系统代理（防止 Privoxy 等代理拦截 Gradio 内部请求）
    for var in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(var, "")
        entries = set(current.replace(",", " ").split())
        before = len(entries)
        entries.update(["localhost", "127.0.0.1"])
        if len(entries) > before:
            os.environ[var] = ",".join(sorted(entries))

    # 日志文件：所有 loguru 输出同时写入 logs/app.log
    logger.add(str(Path(__file__).resolve().parent / "logs" / "app.log"), encoding="utf-8", rotation="10 MB", retention=7)

    # 移除手动主题初始化——改用 demo.launch()，它能正确处理主题和 CSS
    import threading
    import urllib.request

    def _trigger_startup_events():
        """服务器启动后触发 Gradio 的 startup-events，确保队列处理正确初始化。"""
        import time
        for attempt in range(5):
            time.sleep(3)
            try:
                urllib.request.urlopen("http://127.0.0.1:7860/gradio_api/startup-events")
                print("[startup] /startup-events 触发成功，队列处理已启动")
                return
            except Exception as e:
                print(f"[startup] 尝试 {attempt + 1}/5 失败: {e}")
        print("[startup] 所有尝试均失败，队列可能未初始化")

    threading.Thread(target=_trigger_startup_events, daemon=True).start()
    # 使用 launch() 代替 uvicorn.run() —— 自动处理主题/CSS 初始化和队列启动
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        css=NEON_CSS,
        inbrowser=True,
        show_error=True,
    )
