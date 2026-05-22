@echo off
chcp 65001 >nul
title 抖音分镜工具

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM 将 bin 目录加入 PATH，使 ffmpeg 可用
set "PATH=%CD%\bin;%PATH%"

if not exist venv\ (
    echo ❌ 未检测到虚拟环境，请先运行「首次安装.bat」
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo 🚀 启动抖音分镜工具...
echo.
echo 浏览器打开后如果显示空白，请手动刷新页面
echo 关闭浏览器窗口或按 Ctrl+C 可停止服务
echo.

python app.py

echo.
echo 服务已停止。
pause
