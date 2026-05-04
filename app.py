"""Gradio Web 界面

提供视频分镜分析的用户交互界面，支持单链接分析和批量分析。
"""
import html
import re

import gradio as gr
from loguru import logger

from config import config
from core.pipeline import batch_run_pipeline, run_pipeline
from models.schemas import BatchResult, FusedScene, TaskResult, TaskStatus


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
    """构建结果 HTML（单链接）"""
    if result.status == TaskStatus.ERROR:
        return f'<div style="color:#dc2626;padding:16px;background:#fef2f2;border-radius:8px;">❌ 任务失败：{result.error_message}</div>'

    if not result.scenes:
        return '<div style="color:#6b7280;padding:16px;text-align:center;">未检测到分镜</div>'

    total_duration = result.scenes[-1].end_time - result.scenes[0].start_time
    cards = ""
    for scene in result.scenes:
        cut_badge = ""
        if scene.has_scene_cut:
            cut_badge = '<span style="background:#dbeafe;color:#1d4ed8;font-size:0.75em;padding:2px 8px;border-radius:4px;">有切点</span>'
        cards += f"""
        <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                <span style="font-weight:bold;font-size:1.1em;color:#1f2937;">#{scene.index + 1}</span>
                <span style="color:#6b7280;font-size:0.9em;">{_format_time(scene.start_time)} ~ {_format_time(scene.end_time)}</span>
                {cut_badge}
            </div>
            <div style="font-size:1.1em;font-weight:500;color:#111827;margin-bottom:4px;">{html.escape(scene.summary)}</div>
            <div style="color:#4b5563;font-size:0.9em;line-height:1.5;">{html.escape(scene.text)}</div>
        </div>
        """
    header = f'<div style="font-size:1em;color:#374151;margin-bottom:16px;padding:8px 12px;background:#f0fdf4;border-radius:6px;">共 {len(result.scenes)} 个分镜 · 总时长 {_format_time(total_duration)}</div>'

    return header + cards


def _build_batch_html_result(result: BatchResult) -> str:
    """构建批量结果 HTML（表格布局 + 折叠手风琴，纯内联样式）"""
    if result.total == 0:
        return '<div style="color:#6b7280;padding:16px;text-align:center;">未输入有效的链接</div>'

    # 汇总统计
    total_min = int(result.total_duration // 60)
    total_sec = int(result.total_duration % 60)
    summary = f"""
    <div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;">
        <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#6b7280;margin-bottom:4px;">总任务</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#111827;">{result.total}</span>
        </div>
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#6b7280;margin-bottom:4px;">成功</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#111827;">{result.succeeded}</span>
        </div>
        <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#6b7280;margin-bottom:4px;">失败</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#111827;">{result.failed}</span>
        </div>
        <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:12px 24px;text-align:center;flex:1;min-width:100px;">
            <span style="display:block;font-size:0.8em;color:#6b7280;margin-bottom:4px;">总时长</span>
            <span style="display:block;font-size:1.5em;font-weight:bold;color:#111827;">{total_min}:{total_sec:02d}</span>
        </div>
    </div>
    """

    # 每个任务是一个可折叠 details
    cards = ""
    for idx, r in enumerate(result.results):
        task_label = f"#{idx + 1}"
        if r.status == TaskStatus.ERROR:
            cards += f"""
            <details style="background:#fff;border:1px solid #fca5a5;border-radius:8px;margin-bottom:16px;overflow:hidden;background:#fef2f2;">
                <summary style="display:flex;align-items:center;gap:10px;padding:14px 16px;cursor:pointer;font-weight:500;user-select:none;">
                    <span style="font-size:0.8em;color:#9ca3af;">▶</span>
                    <span style="font-weight:700;color:#1f2937;min-width:28px;">{task_label}</span>
                    <span style="color:#6b7280;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(r.url)}</span>
                    <span style="font-size:0.75em;padding:2px 8px;border-radius:4px;font-weight:600;background:#fef2f2;color:#dc2626;border:1px solid #fca5a5;">失败</span>
                </summary>
                <div style="padding:0 16px 16px;border-top:1px solid #e5e7eb;">
                    <div style="color:#dc2626;font-size:0.9em;padding:12px 0;">错误：{html.escape(r.error_message or "")}</div>
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
                    <td style="color:#6b7280;font-weight:600;white-space:nowrap;padding:10px 12px;border-bottom:1px solid #e5e7eb;">#{scene.index + 1}</td>
                    <td style="color:#6b7280;white-space:nowrap;padding:10px 12px;border-bottom:1px solid #e5e7eb;">{_format_time(scene.start_time)} ~ {_format_time(scene.end_time)}</td>
                    <td style="color:#111827;font-weight:500;padding:10px 12px;border-bottom:1px solid #e5e7eb;">{html.escape(scene.summary)}</td>
                    <td style="color:#4b5563;padding:10px 12px;border-bottom:1px solid #e5e7eb;">{html.escape(scene.text)}</td>
                    <td style="text-align:center;padding:10px 12px;border-bottom:1px solid #e5e7eb;">{cut_mark}</td>
                </tr>
                """

            cards += f"""
            <details style="background:#fff;border:1px solid #dee2e6;border-radius:8px;margin-bottom:16px;overflow:hidden;">
                <summary style="display:flex;align-items:center;gap:10px;padding:14px 16px;cursor:pointer;font-weight:500;user-select:none;">
                    <span style="font-size:0.8em;color:#9ca3af;">▶</span>
                    <span style="font-weight:700;color:#1f2937;min-width:28px;">{task_label}</span>
                    <span style="color:#6b7280;font-size:0.85em;word-break:break-all;flex:1;">{html.escape(r.url)}</span>
                    <span style="color:#6b7280;font-size:0.8em;white-space:nowrap;">{len(r.scenes)} 个分镜 · {_format_time(total_duration)}</span>
                </summary>
                <div style="padding:0 16px 16px;border-top:1px solid #e5e7eb;">
                    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:0.9em;">
                        <thead>
                            <tr>
                                <th style="background:#f3f4f6;color:#374151;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;white-space:nowrap;">#</th>
                                <th style="background:#f3f4f6;color:#374151;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;white-space:nowrap;">时间</th>
                                <th style="background:#f3f4f6;color:#374151;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;white-space:nowrap;">摘要</th>
                                <th style="background:#f3f4f6;color:#374151;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;white-space:nowrap;">文字</th>
                                <th style="background:#f3f4f6;color:#374151;font-weight:600;padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;white-space:nowrap;">切点</th>
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


def analyze(url: str, align_window: float, scene_threshold: float) -> str:
    """分析入口函数"""
    extracted = _extract_url(url)
    if not extracted:
        return '<div style="color:#dc2626;padding:16px;background:#fef2f2;border-radius:8px;">未检测到视频链接，请粘贴抖音分享链接</div>'

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
        return f'<div style="color:#dc2626;padding:16px;background:#fef2f2;border-radius:8px;">分析失败：{e}</div>'


def batch_analyze(urls_text: str, max_workers: int, align_window: float, scene_threshold: float) -> str:
    """批量分析入口函数"""
    if not urls_text or not urls_text.strip():
        return '<div style="color:#6b7280;padding:16px;text-align:center;">请输入视频链接，每行一个</div>'

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
        return '<div style="color:#dc2626;padding:16px;background:#fef2f2;border-radius:8px;">未从输入中检测到有效链接</div>'
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
        return f'<div style="color:#dc2626;padding:16px;background:#fef2f2;border-radius:8px;">批量分析失败：{e}</div>'


with gr.Blocks(title="视频分镜分析") as demo:
    demo.theme = gr.themes.Default()
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
                run_btn = gr.Button("开始分析", variant="primary", scale=1, min_width=120)

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
                fn=lambda: '<div style="color:#374151;padding:32px 16px;text-align:center;font-size:1.1em;background:#f0f9ff;border-radius:8px;border:1px solid #bae6fd;">⏳ 正在分析视频，请耐心等待（通常需要 2-5 分钟）...</div>',
                outputs=result_html,
            ).then(
                fn=analyze,
                inputs=[url_input, align_window_slider, scene_threshold_slider],
                outputs=result_html,
            )

            url_input.submit(
                fn=lambda: '<div style="color:#374151;padding:32px 16px;text-align:center;font-size:1.1em;background:#f0f9ff;border-radius:8px;border:1px solid #bae6fd;">⏳ 正在分析视频，请耐心等待（通常需要 2-5 分钟）...</div>',
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
            batch_btn = gr.Button("开始批量分析", variant="primary")

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
                fn=lambda: '<div style="color:#374151;padding:32px 16px;text-align:center;font-size:1.1em;background:#f0f9ff;border-radius:8px;border:1px solid #bae6fd;">⏳ 正在批量分析，请耐心等待...</div>',
                outputs=batch_result_html,
            ).then(
                fn=batch_analyze,
                inputs=[batch_input, batch_max_workers, batch_align_window, batch_scene_threshold],
                outputs=batch_result_html,
            )


if __name__ == "__main__":
    import os
    import logging
    logging.basicConfig(level=logging.INFO)
    os.environ["PATH"] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + os.environ.get("PATH", "")

    # 日志文件：所有 loguru 输出同时写入 logs/app.log
    logger.add("logs/app.log", encoding="utf-8", rotation="10 MB", retention=7)

    # 手动初始化 Gradio 6 运行环境（uvicorn.run(demo.app) 跳过 launch() 的初始化）
    import hashlib
    demo.theme_css = demo.theme._get_theme_css()
    demo.stylesheets = demo.theme._stylesheets
    theme_hasher = hashlib.sha256()
    theme_hasher.update(demo.theme_css.encode("utf-8"))
    demo.theme_hash = theme_hasher.hexdigest()

    import threading
    import urllib.request

    def _trigger_startup_events():
        """服务器启动后触发 Gradio 的 startup-events，确保队列处理正确初始化。"""
        import time
        time.sleep(2)
        try:
            urllib.request.urlopen("http://127.0.0.1:7860/gradio_api/startup-events")
            print("[startup] /startup-events 触发成功，队列处理已启动")
        except Exception as e:
            print(f"[startup] 触发 /startup-events 失败: {e}")

    threading.Thread(target=_trigger_startup_events, daemon=True).start()

    import uvicorn
    uvicorn.run(
        demo.app,
        host="127.0.0.1",
        port=7860,
        log_level="info",
    )
