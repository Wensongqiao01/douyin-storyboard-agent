"""端到端测试：登录 → 工作台 → 登出

运行前提：
1. 已有账号（python scripts/create_user.py e2e_user e2e_pass123）
2. 前端已 build，uvicorn server.main:app --port 7860 已启动
运行：PYTHONIOENCODING=utf-8 python test_e2e_server.py
"""

from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:7860"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # 未登录访问 dashboard → 重定向到 /login
        page.goto(f"{BASE}/dashboard")
        page.wait_for_url("**/login")

        # 错误密码 → 留在登录页
        page.fill('input[type="text"]', "e2e_user")
        page.fill('input[type="password"]', "wrong")
        page.click('button[type="submit"]')
        page.wait_for_timeout(1500)
        assert "/login" in page.url, "错误密码后应留在登录页"

        # 正确登录 → 进入工作台
        page.fill('input[type="password"]', "e2e_pass123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard")

        # 工作台标题可见
        heading = page.locator("h1")
        expect(heading).to_be_visible()
        expect(heading).to_contain_text("工作台")

        browser.close()
        print("E2E 全部通过")


if __name__ == "__main__":
    main()
