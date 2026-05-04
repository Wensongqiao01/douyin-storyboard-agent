# 抖音视频分镜 Agent

## 项目目标

构建一个自动化 Agent，输入抖音视频链接，输出带精确时间戳的分镜文字稿及视频片段。全程使用免费/开源资源实现。

**核心流程：**

```
抖音链接 → 视频下载 → 音频提取 → 语音转文字 → 画面切点检测 → 语义分镜 → 融合对齐 → 分镜结果
```

## 最终项目结构

```
douyin-agent/
├── app.py                      # Gradio 入口
├── config.py                   # 配置（分区管理）
├── .env                        # API Key 等敏感信息
├── requirements.txt            # Python 依赖
├── README.md                   # 安装部署说明
│
├── core/
│   ├── __init__.py
│   ├── pipeline.py             # 编排层：全流程调度
│   ├── downloader.py           # 双引擎下载（douyin-downloader → yt-dlp 自动降级）
│   ├── audio_extractor.py      # ffmpeg 音频提取
│   ├── transcriber.py          # Faster-Whisper 语音转文字
│   ├── scene_detector.py       # PySceneDetect 画面切换检测
│   ├── segmenter.py            # DeepSeek 语义分镜
│   └── fuser.py                # 融合对齐（以语义分段为骨架，以画面切点精确化边界）
│
├── models/
│   ├── __init__.py
│   └── schemas.py              # Pydantic 数据模型
│
├── utils/
│   ├── __init__.py
│   ├── text_matcher.py         # 文字→时间戳模糊匹配
│   └── file_helpers.py         # 文件操作
│
├── douyin-downloader/          # git clone，.gitignore 排除
│   └── run.py
│
└── output/
    └── {task_id}/
        ├── video/
        │   ├── original.mp4
        │   └── scene_001.mp4 ...  # config.py 中 export_scene_clips 控制是否生成
        ├── audio/
        │   └── audio.wav
        ├── intermediate/       # 中间结果缓存，调试 fuser 时可跳过前面步骤
        │   ├── whisper_raw.json
        │   ├── scene_cuts_raw.json
        │   └── semantic_raw.json
        ├── result.json         # 融合后最终结果
        └── report.md           # 可读性报告
```

## 技术栈

| 组件 | 工具库 | 用途 |
|------|--------|------|
| 视频下载 | douyin-downloader + yt-dlp（双引擎降级） | 抖音视频下载 |
| 音视频处理 | ffmpeg-python | 从视频中提取音频 |
| 语音转文字 | faster-whisper | 音频转文字 + 字级时间戳 |
| 画面切换检测 | scenedetect[opencv] | 检测视频画面硬切点 |
| 语义分镜 | DeepSeek API（openai SDK） | 按语义拆分文字稿 |
| 文字模糊匹配 | rapidfuzz | DeepSeek 引用文本 ↔ Whisper 时间戳 |
| 界面 | Gradio | 简易 H5 页面 |
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

`core/` 下所有模块是纯业务逻辑，**不依赖任何 UI 框架**（Gradio/FastAPI/...）。

- 方案一（当前）：app.py (Gradio) → core/* → 结果展示
- 方案二（未来迭代）：api.py (FastAPI) → core/* → JSON 响应

迁移时 `core/` 一个文件不用改。

### 中间结果缓存

所有原始模型输出写入 `output/{task_id}/intermediate/`，调试 fuser.py 时可直接加载缓存，跳过 downloader → transcriber 等耗时步骤。

## 开发顺序（14 步）

### 阶段一：地基（无外部依赖）

1. `config.py` — 配置分区定义
2. `models/schemas.py` — 所有 Pydantic 数据模型
3. `utils/file_helpers.py` — 文件操作工具
4. `utils/text_matcher.py` — 文字模糊匹配

### 阶段二：核心模块

5. `core/downloader.py` — 双引擎下载
6. `core/audio_extractor.py` — ffmpeg 提取音频
7. `core/transcriber.py` — Faster-Whisper 转写
8. `core/scene_detector.py` — PySceneDetect 画面切点
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
