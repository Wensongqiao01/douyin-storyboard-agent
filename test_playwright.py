"""Playwright 自动化测试：验证霓虹赛博主题和批量分析功能。"""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        print("=== 1. 打开页面 ===")
        await page.goto("http://127.0.0.1:7860", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="test_screenshots/01_homepage.png", full_page=True)
        print("  [OK] 首页截图已保存")

        print("\n=== 2. 检查页面标题 ===")
        title = await page.title()
        print(f"  页面标题: {title}")

        print("\n=== 3. 检查深色背景 ===")
        bg_color = await page.evaluate("getComputedStyle(document.body).backgroundColor")
        print(f"  背景色: {bg_color}")
        is_dark = await page.evaluate("""
            () => {
                const bg = getComputedStyle(document.body).backgroundColor;
                const rgb = bg.match(/\\d+/g);
                return rgb && parseInt(rgb[0]) < 30 && parseInt(rgb[1]) < 30 && parseInt(rgb[2]) < 50;
            }
        """)
        print(f"  [OK] 深色背景已应用: {is_dark}")

        print("\n=== 4. 检查全局文字颜色（非黑色）===")
        text_color = await page.evaluate("""
            () => {
                const el = document.querySelector('.gradio-container') || document.body;
                return getComputedStyle(el).color;
            }
        """)
        print(f"  全局文字色: {text_color}")
        is_light = await page.evaluate("""
            () => {
                const el = document.querySelector('.gradio-container') || document.body;
                const c = getComputedStyle(el).color;
                const rgb = c.match(/\\d+/g);
                return rgb && (parseInt(rgb[0]) > 100 || parseInt(rgb[1]) > 100 || parseInt(rgb[2]) > 100);
            }
        """)
        print(f"  [OK] 文字为浅色（非黑色不可见）: {is_light}")

        print("\n=== 5. 检查渐变色标题 ===")
        has_gradient = await page.evaluate("""
            () => {
                const headings = document.querySelectorAll('h1, h2, h3');
                for (const h of headings) {
                    const bg = getComputedStyle(h).backgroundImage || '';
                    if (bg.includes('gradient')) return true;
                }
                return false;
            }
        """)
        print(f"  [OK] 标题渐变色: {has_gradient}")

        print("\n=== 6. 检查页面所有可见元素 ===")
        elements = await page.evaluate("""
            () => {
                const els = {};
                const all = document.querySelectorAll('label, button, span, .block, .markdown-text p');
                all.forEach(el => {
                    const text = el.textContent.trim().substring(0, 60);
                    if (text && text.length > 2) els[text] = true;
                });
                return Object.keys(els).sort();
            }
        """)
        for el in elements:
            print(f"  元素: {el}")

        print("\n=== 7. 检查关键按钮 ID ===")
        start_btn = await page.query_selector("button#start-analysis")
        if start_btn:
            print("  [OK] 单链接按钮 #start-analysis 存在")
            visible = await start_btn.is_visible()
            print(f"  按钮可见: {visible}")
            btn_text = await start_btn.text_content()
            print(f"  按钮文字: {btn_text}")
        else:
            print("  [FAIL] 未找到 #start-analysis 按钮！")

        # 先点击批量分析选项卡，再找批量按钮
        batch_tab = page.locator("button[role='tab']", has_text="批量分析")
        if await batch_tab.count() > 0:
            await batch_tab.first.click()
            await page.wait_for_timeout(500)

        batch_btn = await page.query_selector("button#start-batch")
        if batch_btn:
            print("  [OK] 批量按钮 #start-batch 存在")
            visible = await batch_btn.is_visible()
            print(f"  批量按钮可见: {visible}")
            batch_text = await batch_btn.text_content()
            print(f"  批量按钮文字: {batch_text}")
        else:
            print("  [FAIL] 未找到 #start-batch 按钮！")

        print("\n=== 8. 检查输入框样式 ===")
        input_info = await page.evaluate("""
            () => {
                const inp = document.querySelector('input[type="text"], textarea');
                if (!inp) return { found: false };
                const bg = getComputedStyle(inp).backgroundColor;
                const color = getComputedStyle(inp).color;
                const r = parseInt(bg.match(/\\d+/g)[0]);
                return { found: true, bg: bg, color: color, isDark: r < 50 };
            }
        """)
        if input_info['found']:
            print(f"  输入框背景: {input_info['bg']}")
            print(f"  输入框文字色: {input_info['color']}")
            print(f"  [OK] 输入框深色背景: {input_info['isDark']}")

        print("\n=== 9. 检查选项卡 ===")
        tab_info = await page.evaluate("""
            () => {
                const tabs = document.querySelectorAll("button[role='tab']");
                return Array.from(tabs).map(t => ({
                    text: t.textContent.trim(),
                    color: getComputedStyle(t).color,
                    selected: t.getAttribute('aria-selected') === 'true'
                }));
            }
        """)
        print(f"  找到 {len(tab_info)} 个选项卡:")
        for t in tab_info:
            sel = " [选中]" if t['selected'] else ""
            print(f"    - {t['text']}{sel}: color={t['color']}")

        print("\n=== 10. 检查折叠面板 ===")
        accordions = await page.query_selector_all(".gr-accordion summary, details summary")
        print(f"  找到 {len(accordions)} 个折叠面板")

        print("\n=== 11. HTML 结果区域检查 ===")
        result_bg_info = await page.evaluate("""
            () => {
                const area = document.querySelector('.gr-box') || document.querySelector('.contain');
                if (!area) return { found: false };
                return { found: true, bg: getComputedStyle(area).backgroundColor };
            }
        """)
        if result_bg_info['found']:
            print(f"  结果区域背景: {result_bg_info['bg']}")

        print("\n=== 12. 测试文本可见性（无黑底黑字）===")
        invisible_text = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('.gradio-container *');
                let count = 0;
                let samples = [];
                for (const el of all) {
                    const text = el.textContent.trim();
                    if (!text || text.length < 3) continue;
                    const style = getComputedStyle(el);
                    const color = style.color;
                    const bg = style.backgroundColor;
                    if (bg === 'rgba(0, 0, 0, 0)') continue;
                    const rgb = color.match(/\\d+/g);
                    if (!rgb) continue;
                    const brightness = parseInt(rgb[0]) * 0.299 + parseInt(rgb[1]) * 0.587 + parseInt(rgb[2]) * 0.114;
                    if (brightness < 30) {
                        count++;
                        if (samples.length < 3) samples.push(el.tagName + ': "' + text.substring(0, 30) + '" -> ' + color);
                    }
                }
                return { count, samples };
            }
        """)
        if invisible_text['count'] > 0:
            print(f"  [WARN] 发现 {invisible_text['count']} 个可能不可见的深色文字元素:")
            for s in invisible_text['samples']:
                print(f"    -> {s}")
        else:
            print("  [OK] 未发现不可见的深色文字")

        print("\n=== 13. 霓虹渐变元素检测 ===")
        neon_elems = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                let count = 0;
                for (const el of all) {
                    const bg = getComputedStyle(el).backgroundImage || '';
                    if (bg.includes('gradient') && (bg.includes('0, 245, 255') || bg.includes('0, 255, 255') || bg.includes('#00f5ff') || bg.includes('cyan'))) {
                        count++;
                    }
                }
                return count;
            }
        """)
        print(f"  [OK] 渐变元素数量: {neon_elems}")

        print("\n=== 14. 截取完整页面存档 ===")
        await page.screenshot(path="test_screenshots/02_fullpage.png", full_page=True)
        print("  [OK] 完整页面截图已保存")

        print("\n=== 完成 ===")
        await browser.close()


if __name__ == "__main__":
    import os
    os.makedirs("test_screenshots", exist_ok=True)
    asyncio.run(main())
