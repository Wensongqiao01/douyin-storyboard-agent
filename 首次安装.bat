@echo off
chcp 65001 >nul
title 抖音分镜工具 - 首次安装

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ============================================
echo    抖音分镜工具 v1.0 — 首次安装
echo ============================================
echo.

REM ==== 检测 Python ====
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未检测到 Python
    echo.
    echo 请先安装 Python 3.11 或更高版本，安装时勾选 "Add Python to PATH"：
    echo   https://www.python.org/downloads/
    echo.
    echo 安装完成后重新运行本脚本。
    pause
    exit /b 1
)

python -c "import sys; v=sys.version_info; exit(0 if v>=(3,11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 版本过低（需要 3.11+）
    pause
    exit /b 1
)

echo ✅ Python 版本检测通过
echo.

REM ==== 创建虚拟环境 ====
if not exist venv\ (
    echo 📦 创建 Python 虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo ✅ 虚拟环境已存在
)
echo.

call venv\Scripts\activate.bat

REM ==== 升级 pip ====
echo 📦 升级 pip...
python -m pip install --upgrade pip -q
if %errorlevel% neq 0 (
    echo ⚠️  pip 升级失败，继续安装...
)
echo.

REM ==== 安装 Python 依赖 ====
echo 📦 安装 Python 依赖（可能需要 3-5 分钟）...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✅ Python 依赖安装完成
echo.

REM ==== 下载 ffmpeg ====
echo 📦 检查 ffmpeg...
if exist bin\ffmpeg.exe (
    echo ✅ ffmpeg 已存在
) else (
    echo 正在下载 ffmpeg（约 60MB，下载速度取决于网络）...
    if not exist bin mkdir bin

    powershell -Command "& {try { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%TEMP%\ffmpeg.zip' -UseBasicParsing; exit 0 } catch { exit 1 }}"

    if %errorlevel% neq 0 (
        echo ⚠️  自动下载失败，请手动下载 ffmpeg
        echo   1. 打开 https://www.gyan.dev/ffmpeg/builds/
        echo   2. 下载 ffmpeg-release-essentials.zip
        echo   3. 解压后把 ffmpeg.exe 复制到 bin\ 目录
        pause
    ) else (
        powershell -Command "& { $ProgressPreference='SilentlyContinue'; Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath '%TEMP%\ffmpeg_extract' -Force; exit 0 }"

        REM 从解压目录中找到 ffmpeg.exe
        for /d %%i in (%TEMP%\ffmpeg_extract\ffmpeg-*) do (
            copy "%%i\bin\ffmpeg.exe" "bin\ffmpeg.exe" >nul
        )

        if exist bin\ffmpeg.exe (
            echo ✅ ffmpeg 已下载到 bin\ffmpeg.exe
        ) else (
            echo ⚠️  ffmpeg 解压失败，请手动下载
        )

        del "%TEMP%\ffmpeg.zip" 2>nul
        rmdir /s /q "%TEMP%\ffmpeg_extract" 2>nul
    )
)
echo.

REM ==== 安装 Playwright 浏览器 ====
echo 📦 安装 Playwright 浏览器引擎...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo ❌ Playwright 浏览器安装失败
    echo   可以稍后手动运行: python -m playwright install chromium
    pause
    exit /b 1
)
echo ✅ Playwright 浏览器安装完成
echo.

REM ==== 创建 .env 配置 ====
if not exist .env (
    echo 创建 .env 配置文件...
    (
        echo # 抖音分镜工具配置
        echo.
        echo # DeepSeek API 密钥（必填，联系管理员获取）
        echo DEEPSEEK_API_KEY=你的API密钥
        echo.
        echo # 抖音 Cookie（运行「获取抖音Cookie.bat」自动填写）
        echo DOUYIN_COOKIE=
        echo.
        echo # Whisper 语音模型设备（cpu=通用/cuda=NVIDIA显卡加速）
        echo WHISPER_DEVICE=cpu
        echo.
        echo # HuggingFace 镜像地址（国内用户建议开启，加速模型下载）
        echo HF_ENDPOINT=https://hf-mirror.com
    ) > .env
    echo ✅ 已创建 .env 模板
    echo.
    echo ⚠️  需要编辑 .env 填入 DeepSeek API Key 才能使用
    echo.
) else (
    echo ✅ .env 已存在
)
echo.

REM ==== 完成 ====
echo ============================================
echo    ✅  首次安装完成！
echo ============================================
echo.
echo   接下来请按顺序操作：
echo.
echo   1. 编辑 .env 文件
echo      - 把 DEEPSEEK_API_KEY 设为管理员给你的密钥
echo      - 如有 NVIDIA 显卡，把 WHISPER_DEVICE 改为 cuda
echo.
echo   2. 双击「获取抖音Cookie.bat」
echo      - 自动打开浏览器，扫码登录抖音
echo      - Cookie 自动保存，无需手动操作
echo.
echo   3. 以后双击「启动工具.bat」即可使用
echo.
pause
