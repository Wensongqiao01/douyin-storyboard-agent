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

## 部署（FastAPI + Vue 版本）

### 数据与代码分离（服务器必读）

代码是无状态的，可随意 `git pull` 更新或整目录重建；数据必须放在代码目录之外：

```bash
sudo mkdir -p /data/douyin-agent/output
```

`.env` 中配置（不设置则默认落在项目目录内，仅限本地开发）：

```
DB_PATH=/data/douyin-agent/app.db
OUTPUT_BASE_DIR=/data/douyin-agent/output
```

备份：SQLite 备份就是拷贝 `app.db` 一个文件，建议定时拷到其他机器。

### 首次部署

1. `pip install -r requirements.txt`
2. `cd frontend && npm install && npm run build && cd ..`
3. `.env` 中配置：`JWT_SECRET`（强随机值，可用 `openssl rand -hex 32` 生成）、`DEEPSEEK_API_KEY`、`DOUYIN_COOKIE`、`DB_PATH`、`OUTPUT_BASE_DIR`
   - 2核4G 服务器建议再加 `WHISPER_MODEL_SIZE=tiny`
4. 创建账号：`python scripts/create_user.py <用户名> <密码>`
5. 启动：`uvicorn server.main:app --host 0.0.0.0 --port 7860`

### 更新代码

```bash
git pull
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
# 重启 uvicorn 即可，/data 下的数据库和视频不受影响
```

### 说明

- 任务串行执行（内存 FIFO 队列），服务重启后进行中/排队任务不会恢复，需重新提交
- 关闭服务会硬中断正在执行的任务（daemon 线程），残留的中间文件由 TTL 清理兜底
- 视频/音频文件保留 3 天后自动清理（`VIDEO_TTL_DAYS` 可调），分镜结果永久保留
- 旧版 Gradio 入口 `python app.py` 仍可用，与新服务互不影响
