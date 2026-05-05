# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 抖音视频分镜 Agent

## 项目目标

构建一个自动化 Agent，输入抖音视频链接，输出带精确时间戳的分镜文字稿及视频片段。全程使用免费/开源资源实现。

**核心流程：**

```
抖音链接 → 视频下载 → 音频提取 → 语音转文字 → 画面切点检测 → 语义分镜 → 融合对齐 → 分镜结果
```

## 常用命令

| 用途 | 命令 |
|------|------|
| 启动 Gradio 界面 | `python app.py` |
| 运行所有单元测试 | `pytest tests/ -v` |
| 运行单个测试 | `pytest tests/test_fuser.py -v` |
| 带覆盖率运行 | `pytest tests/ -v --cov=. --cov-report=term-missing` |
| Playwright E2E 测试 | `PYTHONIOENCODING=utf-8 python test_playwright.py` |
| lint 检查 | `ruff check .` |
| 格式化 | `black .` |

## 最终项目结构

```
douyin-agent/
├── app.py                      # Gradio 入口
├── config.py                   # 配置（pydantic-settings + .env）
├── .env                        # API Key 等敏感信息
├── requirements.txt            # Python 依赖
├── README.md                   # 安装部署说明
│
├── core/
│   ├── __init__.py
│   ├── pipeline.py             # 编排层：全流程调度（含 batch 并行）
│   ├── downloader.py           # 三引擎下载（douyin-downloader → yt-dlp → Playwright）
│   ├── audio_extractor.py      # ffmpeg 音频提取
│   ├── transcriber.py          # Faster-Whisper 语音转文字
│   ├── scene_detector.py       # PySceneDetect 画面切换检测
│   ├── segmenter.py            # DeepSeek 语义分镜
│   └── fuser.py                # 融合对齐
│
├── models/
│   └── schemas.py              # Pydantic 数据模型（9 个模型）
│
├── utils/
│   ├── text_matcher.py         # 文字→时间戳模糊匹配（rapidfuzz）
│   └── file_helpers.py         # 文件操作工具
│
├── douyin-downloader/          # git clone，.gitignore 排除
│
├── tests/
│   ├── test_config.py          # 各模块单元测试
│   ├── test_downloader.py
│   ├── test_fuser.py
│   ├── test_pipeline.py
│   ├── test_schemas.py
│   ├── test_integration.py
│   └── ...
│
└── output/
    └── {task_id}/
        ├── video/original.mp4
        ├── audio/audio.wav
        ├── intermediate/       # 中间结果缓存
        │   ├── whisper_raw.json
        │   ├── scene_cuts_raw.json
        │   └── semantic_raw.json
        ├── result.json
        └── report.md
```

## 技术栈

| 组件 | 工具库 | 用途 |
|------|--------|------|
| 视频下载 | douyin-downloader + yt-dlp + Playwright（三引擎降级） | 抖音视频下载 |
| 音视频处理 | ffmpeg-python | 从视频中提取音频 |
| 语音转文字 | faster-whisper | 音频转文字 + 字级时间戳 |
| 画面切换检测 | scenedetect[opencv] | 检测视频画面硬切点 |
| 语义分镜 | DeepSeek API（openai SDK） | 按语义拆分文字稿 |
| 文字模糊匹配 | rapidfuzz | DeepSeek 引用文本 ↔ Whisper 时间戳 |
| 界面 | Gradio 6.x | Web 界面（两标签页：单条 + 批量） |
| 数据结构 | Pydantic v2 | 类型定义和数据校验 |
| 日志 | loguru | 统一日志输出 |
| 重试 | tenacity | 网络请求指数退避重试 |
| 配置 | python-dotenv | .env 管理密钥 |

## 核心架构设计

### 融合策略（fuser.py 核心逻辑）

```
以 DeepSeek 语义分段为骨架
以 PySceneDetect 画面切点为边界精确化锚点
以 Whisper 字级时间戳为时间映射基准
```

- scene_cuts 在语义边界 ±1s 内存在切点 → 对齐到切点
- 不存在切点 → 保持语义边界
- `export_scene_clips` 开关控制是否需要实际切割视频文件

### 可迭代性设计

`core/` 下所有模块是纯业务逻辑，**不依赖任何 UI 框架**（Gradio/FastAPI/...）。迁移时 `core/` 一个文件不用改。

### 中间结果缓存

所有原始模型输出写入 `output/{task_id}/intermediate/`，调试 fuser.py 时可直接加载缓存。

### 下载引擎降级链

```
douyin-downloader (subprocess + Node.js)
  → yt-dlp (Python binding, 带 cookie)
    → Playwright (浏览器自动化, 含 RENDER_DATA 回退)
```

## 重要约定与已知陷阱

### Windows 特有

- **GBK 编码问题**：subprocess 可能因 GBK 编码崩溃。所有子进程调用需设置 `PYTHONIOENCODING=utf-8` 环境变量；Playwright E2E 测试也需同理。
- **ffmpeg PATH 不一致**：`shutil.which("ffmpeg")` 能找到不等于 `subprocess.Popen` 能找到。手动把 ffmpeg 目录追加到 `os.environ["PATH"]`。

### Gradio 6.x 兼容性

- **CSS 参数迁移**：`gr.Blocks(css=...)` 不再支持，需改为 `demo.launch(css=...)`。
- **HTML 清理**：`gr.HTML` 默认 `sanitize_html=True`，自定义 HTML/JS 会被剥离。设为 `sanitize_html=False` 并用 `html.escape()` 转义用户内容防 XSS。
- **Hex 颜色转换**：Gradio 6.x 会自动把 CSS 中的十六进制颜色转为 `rgb()` 格式（如 `#0a0a14` → `rgb(10, 10, 20)`），断言时需注意。
- **SSE API**：Gradio 6.x 使用 SSE 流式 API（`/gradio_api/call/{api_name}`），不再支持 `/api/predict/`。

### 下载引擎

- **Cookie 格式**：必须导出为 **Netscape cookie 格式**，不能用 JSON 格式。`expires` 字段必须为未来时间戳（设为 2030 年解决过期问题）。
- **精选页链接**：抖音精选页 URL 包含 `modal_id` 参数，需提取并拼接为标准视频页 URL `https://www.douyin.com/video/{modal_id}`。
- **RENDER_DATA 回退**：当 API 接口被反爬时，PlaywrightEngine 从 HTML 中提取 `RENDER_DATA` 脚本内容做降级。
- **Windows 进程终止**：超时终止子进程时使用 `CREATE_NEW_PROCESS_GROUP` 标志 + `os.killpg()` 确保杀掉整个进程树。

### 语义分镜（segmenter）

- **end_text 缺失**：DeepSeek API 返回的分段可能缺少 `end_text` 字段，导致 Pydantic `ValidationError`。需在外层捕获异常，回退为全文分段（`setdefault` + try/except）。
- **后续修复检查点**：在调试模式下输出 `end_text` 缺失信息，确保 `fuser.py` 的 `_compute_times()` 函数能正确处理缺失值。

### 前端显示

- **不要用 `display:flex` 在 `<summary>` 上**：Chromium 已知 bug，会导致 `<details>` 原生点击切换失效。改为在 `<summary>` 内部加一层 `<div>` 做 flex 布局。
- **批量分镜默认展开**：批量分析结果中的分镜卡片默认应处于展开状态（`open` 属性），否则用户看不到结构化内容。
- **使用 `page.evaluate()`**：Playwright 测试中不要用 `ElementHandle.evaluate()`，元素 detached 时会报错。统一用 `page.evaluate()`，内部用 CSS 选择器定位。

## 开发顺序

### 阶段一：地基（无外部依赖）
1. `config.py` — 配置定义
2. `models/schemas.py` — 数据模型
3. `utils/file_helpers.py` — 文件工具
4. `utils/text_matcher.py` — 文字模糊匹配

### 阶段二：核心模块
5. `core/downloader.py` — 三引擎下载
6. `core/audio_extractor.py` — ffmpeg 提取音频
7. `core/transcriber.py` — Faster-Whisper 转写
8. `core/scene_detector.py` — 画面切点检测
9. `core/segmenter.py` — DeepSeek 语义分镜
10. `core/fuser.py` — 融合对齐

### 阶段三：串联
11. `core/pipeline.py` — 编排层
12. 整体端到端测试

### 阶段四：界面
13. `app.py` — Gradio 界面
14. 部署文档 + README

## 开发原则

1. **不询问确认，直接按上述顺序逐步执行**，每一步完成后自动进入下一步。
2. 每个模块完成后进行基本的功能验证。
3. 遇到阻塞时先尝试自行解决，确实无法解决时再询问。
4. 所有代码注释用中文。
5. 函数必须有类型注解。
6. 密钥统一通过 .env 管理，不硬编码。
7. 先写逻辑再写界面，确保核心功能完整。
