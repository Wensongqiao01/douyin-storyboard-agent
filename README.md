# 抖音视频分镜分析 Agent

输入抖音视频链接，自动完成**语音转文字 → 语义分镜 → 画面场景检测 → 融合对齐**，输出带精确时间戳的结构化分镜结果。

## 功能

- 抖音视频自动下载（三引擎降级策略：douyin-downloader → yt-dlp → Playwright）
- Faster-Whisper 语音转文字 + 字级时间戳
- DeepSeek 语义分镜（按内容主题分段）
- PySceneDetect 画面硬切点检测
- 语义边界与画面切点智能融合对齐
- DeepSeek ASR 纠错后处理（修正同音字、漏字等识别错误）
- Gradio Web 界面，直观展示分镜结果

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

确保系统已安装 **ffmpeg**:

```bash
# Windows
winget install ffmpeg
# 或从 https://ffmpeg.org/download.html 手动安装

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 2. 配置

复制 `.env.example` 为 `.env`，填写配置：

```bash
cp .env.example .env
```

| 配置项 | 说明 | 是否必填 |
|--------|------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（[获取](https://platform.deepseek.com/)） | **是** |
| `DOUYIN_COOKIE` | 抖音 Cookie（某些视频需要登录态） | 可选 |
| `WHISPER_DEVICE` | Whisper 运行设备（`cpu` 或 `cuda`） | 默认 `cpu` |

### 3. 启动

```bash
python app.py
```

浏览器打开 `http://127.0.0.1:7860`，粘贴抖音视频链接即可开始分析。

## 项目结构

```
├── app.py                  # Gradio Web 界面
├── config.py               # 配置管理（pydantic-settings）
├── requirements.txt        # Python 依赖
├── .env                    # 密钥配置（不提交 git）
├── .env.example            # 配置模板
├── CLAUDE.md               # 项目开发文档
│
├── core/                   # 核心业务逻辑（不依赖 UI）
│   ├── pipeline.py         # 任务编排流水线
│   ├── downloader.py       # 三引擎视频下载
│   ├── audio_extractor.py  # ffmpeg 音频提取
│   ├── transcriber.py      # Faster-Whisper 语音转写
│   ├── scene_detector.py   # PySceneDetect 画面检测
│   ├── segmenter.py        # DeepSeek 语义分镜
│   ├── text_cleaner.py     # DeepSeek ASR 纠错后处理
│   └── fuser.py            # 融合对齐
│
├── models/
│   └── schemas.py          # Pydantic 数据模型
│
├── utils/
│   ├── text_matcher.py     # 文字模糊匹配
│   └── file_helpers.py     # 文件操作工具
│
├── tests/                  # 测试（109 个，覆盖率 >80%）
│
└── output/                 # 输出目录（自动生成）
    └── {task_id}/
        ├── video/
        ├── audio/
        ├── intermediate/   # 中间结果缓存
        ├── result.json     # 融合后最终结果
        └── report.md       # 可读性报告
```

## 技术栈

| 组件 | 工具库 | 用途 |
|------|--------|------|
| 视频下载 | douyin-downloader + yt-dlp + Playwright | 三引擎降级下载 |
| 音视频处理 | ffmpeg-python | 提取音频 |
| 语音转文字 | faster-whisper | 音频 → 文字 + 时间戳 |
| 画面切换检测 | scenedetect[opencv] | 检测视频硬切点 |
| 语义分镜 | DeepSeek API | 按语义拆分 |
| ASR 纠错 | DeepSeek API | 修正同音字/漏字/多字 |
| 文字模糊匹配 | rapidfuzz | 引用文本 → 时间戳 |
| Web 界面 | Gradio | 交互页面 |
| 数据校验 | Pydantic v2 | 类型与约束 |
| 日志 | loguru | 日志输出 |
| 重试 | tenacity | 网络请求重试 |

## 融合策略

以 DeepSeek 语义分段为骨架，以 PySceneDetect 画面切点为边界锚点，以 Whisper 字级时间戳为时间映射基准：

1. 语义分段确定场景的语义边界（文字层面）
2. 语义边界 ±1s 内存在画面切点 → 对齐到切点
3. 不存在切点 → 保持语义边界
4. 保证分镜时间不重叠

## 开发

```bash
# 运行测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=. --cov-report=term-missing

# 查看覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

## License

MIT
