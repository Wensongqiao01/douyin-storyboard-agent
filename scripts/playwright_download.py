"""基于 Playwright 的抖音视频下载脚本

使用真实 Chromium 浏览器绕过抖音反爬，通过拦截页面 API 响应获取视频地址。
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from playwright.sync_api import BrowserContext, expect, sync_playwright

from config import config

# 抖音视频详情 API 路径模式
API_PATTERN = re.compile(r"/aweme/v1/web/aweme/detail/")
# 视频播放地址 key
PLAY_ADDR_KEY = "play_addr"


def parse_cookie(cookie_str: str) -> list[dict]:
    """将 DOUYIN_COOKIE 格式的 cookie 字符串转为 Playwright 需要的格式

    Args:
        cookie_str: 分号分隔的 "key=value" cookie 字符串

    Returns:
        Playwright add_cookies 需要的格式
    """
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


def extract_video_url_from_detail(detail_data: dict) -> str | None:
    """从视频详情响应中提取无水印视频下载地址

    Args:
        detail_data: /aweme/v1/web/aweme/detail/ 接口返回的 JSON 数据

    Returns:
        视频下载 URL 或 None
    """
    try:
        aweme_detail = detail_data.get("aweme_detail", {})
        if not aweme_detail:
            logger.warning("响应中没有 aweme_detail")
            return None

        # 尝试多个可能的视频地址字段
        # 1. video.play_addr.url_list (最高清无水印)
        play_addr = aweme_detail.get("video", {}).get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            # 通常第一个是最高清的
            logger.info("从 play_addr.url_list 获取视频地址")
            return url_list[0]

        # 2. video.play_addr_highest.url_list
        play_addr_highest = aweme_detail.get("video", {}).get("play_addr_highest", {})
        url_list_highest = play_addr_highest.get("url_list", [])
        if url_list_highest:
            logger.info("从 play_addr_highest.url_list 获取视频地址")
            return url_list_highest[0]

        # 3. video.bit_rate[0].play_addr.url_list
        bit_rate = aweme_detail.get("video", {}).get("bit_rate", [])
        if bit_rate and len(bit_rate) > 0:
            url_list_bit = bit_rate[0].get("play_addr", {}).get("url_list", [])
            if url_list_bit:
                logger.info("从 bit_rate[0].play_addr.url_list 获取视频地址")
                return url_list_bit[0]

        # 4. 备选：video.download_addr.url_list
        download_addr = aweme_detail.get("video", {}).get("download_addr", {})
        url_list_dl = download_addr.get("url_list", [])
        if url_list_dl:
            logger.info("从 download_addr.url_list 获取视频地址")
            return url_list_dl[0]

    except (KeyError, IndexError, TypeError) as e:
        logger.warning("解析视频地址失败: {}", e)

    return None


def download_video_with_playwright(
    url: str,
    output_path: str,
    cookie_str: str | None = None,
    timeout: int = 60000,
) -> str:
    """使用 Playwright 下载抖音视频

    通过真实 Chromium 浏览器加载视频页面，拦截详情 API 响应获取视频地址，
    然后用 requests 下载视频文件。

    Args:
        url: 抖音视频链接（支持短链接和完整链接）
        output_path: 视频保存路径
        cookie_str: 抖音 cookie，默认从 config 读取
        timeout: 页面加载超时（毫秒）

    Returns:
        下载后的视频文件路径

    Raises:
        RuntimeError: 获取视频地址或下载失败
    """
    if cookie_str is None:
        cookie_str = config.douyin_cookie

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    video_url: str | None = None
    detail_response_data: dict | None = None

    with sync_playwright() as p:
        logger.info("启动 Chromium 浏览器...")
        browser = p.chromium.launch(
            headless=True,
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

        # 设置 cookie
        if cookie_str:
            cookies = parse_cookie(cookie_str)
            context.add_cookies(cookies)
            logger.info("已设置 {} 个 cookie", len(cookies))

        page = context.new_page()

        # 拦截包含视频详情的 API 响应
        api_response_data: dict | None = None

        def on_response(response):
            """监听网络响应，捕获视频详情 API 返回"""
            nonlocal api_response_data
            if API_PATTERN.search(response.url):
                logger.info("捕获到视频详情 API 响应: {}", response.url)
                try:
                    data = response.json()
                    api_response_data = data
                    logger.info("API 响应状态码: {}", response.status)
                except Exception as e:
                    logger.warning("解析 API 响应 JSON 失败: {}", e)

        page.on("response", on_response)

        # 解析短链接（如果是的话）
        if "v.douyin.com" in url:
            logger.info("解析短链接: {}", url)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # 短链接会 302，等待页面跳转到完整 URL
            time.sleep(2)

        final_url = page.url
        logger.info("最终页面 URL: {}", final_url)

        # 如果已经是完整页面 URL，直接加载
        if "v.douyin.com" not in final_url and "/video/" not in final_url:
            # 从原始 URL 提取视频 ID
            video_id_match = re.search(r"/(\d+)/?", url)
            if video_id_match:
                video_id = video_id_match.group(1)
                final_url = f"https://www.douyin.com/video/{video_id}"
                logger.info("构造完整视频页面 URL: {}", final_url)

        logger.info("加载视频页面: {}", final_url)
        page.goto(final_url, wait_until="domcontentloaded", timeout=30000)

        # 等待 API 响应或页面加载
        start_time = time.time()
        while time.time() - start_time < timeout / 1000:
            if api_response_data is not None:
                video_url = extract_video_url_from_detail(api_response_data)
                if video_url:
                    detail_response_data = api_response_data
                    break

            # 也尝试从页面 DOM 提取
            page_html = page.content()
            # 尝试查找 RENDER_DATA 或 __INITIAL_STATE__
            for pattern in [
                r'id="RENDER_DATA"[^>]*>([^<]+)<',
                r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            ]:
                match = re.search(pattern, page_html)
                if match:
                    logger.info("在页面 HTML 中找到内嵌数据")
                    break

            time.sleep(1)
            logger.info("等待 API 响应... ({}s)", int(time.time() - start_time))

        browser.close()

    if not video_url:
        raise RuntimeError("未能从页面获取视频地址")

    logger.info("获取到视频地址: {}", video_url)

    # 下载视频文件
    import urllib.request

    logger.info("开始下载视频到: {}", output_path)
    try:
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
    except Exception as e:
        raise RuntimeError(f"下载视频文件失败: {e}") from e

    logger.info("视频下载成功: {} ({:.1f} MB)", output_path, os.path.getsize(output_path) / 1024 / 1024)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Playwright 抖音视频下载")
    parser.add_argument("-u", "--url", default="https://v.douyin.com/QZi4s_vOKRg/", help="抖音视频链接")
    parser.add_argument("-o", "--output", default="", help="输出路径")
    args = parser.parse_args()

    output = args.output or str(Path(__file__).resolve().parent.parent / "output" / "playwright_test" / "video.mp4")
    try:
        result = download_video_with_playwright(args.url, output)
        print(f"\n✓ 下载成功: {result}")
    except Exception as e:
        print(f"\n✗ 下载失败: {e}")
        sys.exit(1)
