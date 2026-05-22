"""视频下载三引擎

策略：
1. 首选 douyin-downloader（subprocess 调用）
2. 自动降级到 yt-dlp（Python 绑定）
3. 末位降级到 Playwright（真实浏览器，绕开反爬）

使用 config 中的 cookie 进行身份验证。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Optional

from loguru import logger

from config import config

# yt-dlp 可能未安装，放在 try/except 中
try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore[assignment]

# Playwright 可能未安装
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]

# 下载超时（秒）
DOWNLOAD_TIMEOUT = 120


def _write_cookie_tempfile(cookie: str) -> str:
    """将 cookie 字符串写入临时 Netscape 格式文件"""
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="douyin_cookies_")
    future_expiry = 1893456000  # 2030-01-01
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for pair in cookie.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            for domain in (".douyin.com",):
                f.write(f"{domain}\tTRUE\t/\tTRUE\t{future_expiry}\t{key}\t{value}\n")
    return path


def _cleanup_cookie_tempfile(path: str) -> None:
    """安全删除临时 cookie 文件"""
    try:
        os.unlink(path)
    except OSError:
        pass


class DouyinDownloaderEngine:
    """douyin-downloader 引擎（主）"""

    DOUYIN_SCRIPT = Path(__file__).resolve().parent.parent / "douyin-downloader" / "run.py"

    def download(self, url: str, output_path: str, cookie: str = "") -> str:
        """使用 douyin-downloader 下载视频"""
        if not self.DOUYIN_SCRIPT.exists():
            raise RuntimeError(
                f"douyin-downloader 脚本不存在: {self.DOUYIN_SCRIPT}，"
                f"请执行 git clone 到项目根目录"
            )

        download_root = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(download_root, exist_ok=True)

        # 注意：不传 -c 参数，让 v2.0.0 使用默认 douyin-downloader/config.yml
        # （run.py 会 chdir 到 douyin-downloader/ 目录）
        cmd = [
            sys.executable, str(self.DOUYIN_SCRIPT),
            "-u", url,
            "-p", download_root,
        ]

        logger.info("开始 douyin-downloader 下载: {}", url)

        env = os.environ.copy()
        if cookie:
            env["DOUYIN_COOKIE"] = cookie
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("TERM", "xterm-256color")

        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": DOWNLOAD_TIMEOUT,
            "env": env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        try:
            result = subprocess.run(cmd, **kwargs)
        except subprocess.TimeoutExpired:
            logger.error("douyin-downloader 超时（{}s）: {}", DOWNLOAD_TIMEOUT, url)
            raise RuntimeError(
                f"douyin-downloader 下载超时（{DOWNLOAD_TIMEOUT} 秒），"
                f"请检查 Cookie 是否有效或网络连接"
            )

        if result.returncode != 0:
            logger.error("douyin-downloader 失败 (stderr): {}", result.stderr)
            logger.error("douyin-downloader 失败 (stdout): {}", result.stdout)
            raise RuntimeError(f"douyin-downloader 下载失败: {result.stderr or result.stdout}")

        # v2.0.0 可能按作者建子目录，递归搜索 MP4
        mp4_files = []
        try:
            for f in Path(download_root).rglob("*.mp4"):
                mp4_files.append(str(f))
        except OSError as e:
            raise RuntimeError(f"读取下载目录失败: {e}") from e

        if not mp4_files:
            raise RuntimeError(
                f"douyin-downloader 报告成功但未找到 MP4 文件（{download_root}）"
            )

        mp4_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        actual_file = mp4_files[0]
        if len(mp4_files) > 1:
            logger.warning("找到多个 MP4 文件，使用最新的: {}", actual_file)

        if os.path.abspath(actual_file) != os.path.abspath(output_path):
            shutil.move(actual_file, output_path)

        logger.info("douyin-downloader 下载成功: {}", output_path)
        return output_path


class YtDlpEngine:
    """yt-dlp 引擎（降级）"""

    def download(self, url: str, output_path: str, cookie: str = "") -> str:
        """使用 yt-dlp 下载视频"""
        if yt_dlp is None:
            raise RuntimeError("yt-dlp 未安装，请执行 pip install yt-dlp")

        ydl_opts: dict = {
            "outtmpl": output_path,
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
        }

        cookie_file = None
        if cookie:
            cookie_file = _write_cookie_tempfile(cookie)
            ydl_opts["cookiefile"] = cookie_file

        logger.info("开始 yt-dlp 下载: {}", url)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.error("yt-dlp 下载失败: {}", e)
            raise RuntimeError(f"yt-dlp 下载失败: {e}") from e
        finally:
            if cookie_file:
                _cleanup_cookie_tempfile(cookie_file)

        logger.info("yt-dlp 下载成功: {}", output_path)
        return output_path


def _parse_cookie_for_playwright(cookie_str: str) -> list[dict]:
    """将 DOUYIN_COOKIE 格式转为 Playwright add_cookies 需要的格式"""
    cookies = []
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        cookies.append({
            "name": key.strip(),
            "value": value.strip(),
            "domain": ".douyin.com",
            "path": "/",
        })
    return cookies


def _extract_video_url_from_detail(detail_data: dict) -> str | None:
    """从抖音视频详情 API 响应中提取无水印视频地址"""
    try:
        aweme_detail = detail_data.get("aweme_detail", {})
        if not aweme_detail:
            return None

        play_addr = aweme_detail.get("video", {}).get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            return url_list[0]

        play_addr_highest = aweme_detail.get("video", {}).get("play_addr_highest", {})
        url_list_highest = play_addr_highest.get("url_list", [])
        if url_list_highest:
            return url_list_highest[0]

        bit_rate = aweme_detail.get("video", {}).get("bit_rate", [])
        if bit_rate:
            url_list_bit = bit_rate[0].get("play_addr", {}).get("url_list", [])
            if url_list_bit:
                return url_list_bit[0]

        download_addr = aweme_detail.get("video", {}).get("download_addr", {})
        url_list_dl = download_addr.get("url_list", [])
        if url_list_dl:
            return url_list_dl[0]
    except (KeyError, IndexError, TypeError):
        pass
    return None


def _find_aweme_detail(obj, depth=0):
    """递归搜索 aweme_detail 字段"""
    if depth > 20:
        return None
    if isinstance(obj, dict):
        if "aweme_detail" in obj:
            return obj["aweme_detail"]
        for v in obj.values():
            result = _find_aweme_detail(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_aweme_detail(item, depth + 1)
            if result:
                return result
    return None


class PlaywrightEngine:
    """Playwright 引擎（末位降级）—— 通过真实浏览器绕过反爬"""

    API_PATTERN = re.compile(r"/aweme/v1/web/aweme/detail/")

    def download(self, url: str, output_path: str, cookie: str = "") -> str:
        """使用 Playwright 驱动真实 Chromium 下载抖音视频"""
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright 未安装，请执行 pip install playwright && python -m playwright install chromium"
            )

        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        video_url: str | None = None

        with sync_playwright() as p:
            logger.info("启动 Chromium 浏览器...")
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )

            if cookie:
                cookies = _parse_cookie_for_playwright(cookie)
                context.add_cookies(cookies)
                logger.debug("Playwright 已设置 {} 个 cookie", len(cookies))

            page = context.new_page()
            page.on("console", lambda msg: logger.debug("[浏览器] {}", msg.text))

            # 检测精选页链接，转为标准视频页 URL
            jingxuan_match = re.search(r'modal_id=(\d+)', url)
            if jingxuan_match:
                modal_id = jingxuan_match.group(1)
                video_url_page = f"https://www.douyin.com/video/{modal_id}"
                logger.info("检测到精选页链接，转为标准视频页: {} -> {}", url, video_url_page)
                url = video_url_page

            # 标准页面加载流程（通过 expect_response 捕获 API 响应）
            if not video_url:
                API_TIMEOUT_MS = 150000
                from urllib.parse import unquote

                try:
                    with page.expect_response(
                        lambda r: self.API_PATTERN.search(r.url) is not None,
                        timeout=API_TIMEOUT_MS,
                    ) as response_info:
                        if "v.douyin.com" in url:
                            logger.info("解析短链接: {}", url)
                        else:
                            logger.info("加载视频页面: {}", url)
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    resp = response_info.value
                    api_response_data = resp.json()
                    video_url = _extract_video_url_from_detail(api_response_data)
                    logger.info("API 响应到达（status={}），提取视频地址: {}", resp.status, bool(video_url))
                except Exception as e:
                    logger.warning("等待 API 响应超时或失败（{}ms）: {}", API_TIMEOUT_MS, e)
                    # 尝试从页面 HTML 中的 RENDER_DATA 提取
                    try:
                        html = page.content()
                        match = re.search(r'id="RENDER_DATA"[^>]*>([^<]+)<', html)
                        if match:
                            decoded = match.group(1).replace("\\u003C", "<").replace("\\u003E", ">").replace("\\u0026", "&")
                            render_data = json.loads(unquote(decoded))
                            logger.debug("RENDER_DATA 顶层 keys: {}", list(render_data.keys()))
                            aweme_detail = _find_aweme_detail(render_data)
                            if aweme_detail:
                                video_url = _extract_video_url_from_detail({"aweme_detail": aweme_detail})
                                logger.info("从 RENDER_DATA 提取到视频地址: {}", bool(video_url))
                            else:
                                logger.warning("RENDER_DATA 中未找到 aweme_detail")
                    except Exception as ex:
                        logger.warning("从 HTML 提取视频地址失败: {}", ex)

            browser.close()

        if not video_url:
            raise RuntimeError("Playwright 未能获取到视频地址（页面可能被反爬拦截）")

        logger.info("获取到视频地址，开始下载...")

        req = urllib.request.Request(
            video_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.douyin.com/",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(output_path, "wb") as f:
                    f.write(resp.read())
        except Exception as e:
            raise RuntimeError(f"下载视频文件失败: {e}") from e

        file_size = os.path.getsize(output_path)
        logger.info("Playwright 下载成功: {} ({:.1f} MB)", output_path, file_size / 1024 / 1024)
        return output_path


def download_video(
    url: str,
    output_path: str,
    cookie: Optional[str] = None,
) -> str:
    """下载抖音视频（双引擎自动降级）

    Args:
        url: 抖音视频链接
        output_path: 视频保存路径
        cookie: 抖音 cookie，默认从 config 读取

    Returns:
        下载后的视频文件路径

    Raises:
        ValueError: URL 或输出路径为空
        RuntimeError: 所有下载引擎均失败
    """
    if not url:
        raise ValueError("URL 不能为空")
    if not output_path:
        raise ValueError("输出路径不能为空")

    if cookie is None:
        cookie = config.douyin_cookie

    engines: list[tuple[str, DouyinDownloaderEngine | YtDlpEngine | PlaywrightEngine]] = [
        ("douyin-downloader", DouyinDownloaderEngine()),
        ("yt-dlp", YtDlpEngine()),
        ("playwright", PlaywrightEngine()),
    ]

    last_error: Optional[Exception] = None
    engine_errors: list[str] = []
    for name, engine in engines:
        try:
            return engine.download(url, output_path, cookie)
        except Exception as e:
            logger.warning("{} 下载失败（尝试下一个引擎）: {}", name, e)
            engine_errors.append(f"{name}: {e}")
            last_error = e

    error_detail = " | ".join(engine_errors)
    logger.error("所有下载引擎均失败: [{}]", error_detail)
    raise RuntimeError(f"所有下载引擎均失败（{error_detail}）") from last_error
