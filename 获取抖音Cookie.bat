@echo off
chcp 65001 >nul
title 抖音 Cookie 提取

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

if not exist venv\ (
    echo ❌ 未检测到虚拟环境，请先运行「首次安装.bat」
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ============================================
echo    抖音 Cookie 自动提取
echo ============================================
echo.
echo 即将打开浏览器窗口。
echo 如果已登录抖音，Cookie 会自动提取。
echo 如果未登录，请使用抖音 App 扫码登录。
echo.

python scripts/get_douyin_cookie.py
