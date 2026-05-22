"""自动提取抖音 Cookie 脚本

使用 Playwright 打开抖音登录页，用户扫码登录后自动提取 Cookie 写入 .env。
"""

import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"


def _read_env() -> dict[str, str]:
    """读取当前 .env 内容"""
    env_vars: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()
    return env_vars


def _write_env(env_vars: dict[str, str]) -> None:
    """写回 .env，保留注释"""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    output: list[str] = []
    written_keys: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            output.append(line)
            continue
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in env_vars:
                output.append(f"{key}={env_vars[key]}")
                written_keys.add(key)
            else:
                output.append(line)
        else:
            output.append(line)

    for key, value in env_vars.items():
        if key not in written_keys:
            output.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


def _cookies_to_string(cookies: list[dict]) -> str:
    """将 Playwright cookies 转为分号分隔的 key=value 格式"""
    pairs = []
    for c in cookies:
        if c["name"] and c["value"]:
            pairs.append(f"{c['name']}={c['value']}")
    return ";".join(pairs)


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 未安装 Playwright，请先运行「首次安装.bat」")
        input("按 Enter 退出...")
        sys.exit(1)

    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")

    env_vars = _read_env()

    print("=" * 50)
    print("  抖音 Cookie 自动提取工具")
    print("=" * 50)
    print()
    print("即将打开浏览器窗口，请在浏览器中扫码登录你的抖音账号。")
    print("登录成功后 Cookie 将自动保存，无需手动操作。")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto("https://www.douyin.com", wait_until="domcontentloaded")

        print("⏳ 等待登录...请使用抖音扫码登录")
        print("（登录后自动检测，无需其他操作）")

        # 轮询检测登录状态：sessionid 出现表示已登录
        session_id = None
        for _ in range(600):  # 最多等 10 分钟
            time.sleep(1)
            cookies = context.cookies()
            for c in cookies:
                if c["name"] in ("sessionid", "uid"):
                    session_id = c
                    break
            if session_id:
                break

        if not session_id:
            print("❌ 登录超时（10分钟），请重新运行本工具")
            browser.close()
            input("按 Enter 退出...")
            sys.exit(1)

        all_cookies = context.cookies()
        cookie_str = _cookies_to_string(all_cookies)
        browser.close()

    env_vars["DOUYIN_COOKIE"] = cookie_str
    _write_env(env_vars)

    print(f"✅ 成功提取 {len(all_cookies)} 个 Cookie，已保存到 .env")
    print(f"   文件位置: {ENV_PATH}")
    input("按 Enter 退出...")


if __name__ == "__main__":
    main()
