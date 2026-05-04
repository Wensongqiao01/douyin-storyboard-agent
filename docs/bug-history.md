# 项目 Bug 历史记录

抖音视频分镜 Agent 开发中遇到并修复的问题总结。

---

## 1. 视频下载引擎失败

### 1.1 所有下载引擎均失败

**症状:** 无论短链接还是标准链接，所有三个下载引擎全部失败，输出"所有下载引擎均失败"。

**排查过程:**
- douyin-downloader 引擎：超时或 Cookie 无效
- yt-dlp 引擎：同样需要 Cookie，且需要 Netscape 格式的 Cookie 文件（不是原始 Cookie 字符串）
- Playwright 引擎：页面加载成功但 API 拦截未捕获到响应

**根因:** 多个因素叠加：
1. douyin-downloader 依赖的 Cookie 不完整（缺少 `passport_csrf_token`、`ttwid` 等关键字段）
2. yt-dlp 的 Cookie 临时文件过期时间设为 `0` 会被视为已过期
3. 抖音反爬机制返回 `aweme_detail: null` + `filter_reason: "core_dep"`，即使 `status_code: 0`

**修复:** `core/downloader.py`
- yt-dlp Cookie 写为 Netscape 格式，过期时间设为 2030 年（`expiry=0` 会被视为过期）
- Playwright 增加 `RENDER_DATA` 回退方案：当 API 拦截不到响应时，从页面 HTML 的 `RENDER_DATA` 中递归搜索 `aweme_detail`
- 三层引擎（douyin-downloader → yt-dlp → Playwright）串联降级

**文件:** `core/downloader.py:41-73`（Cookie 文件写入）, `:370-403`（RENDER_DATA 回退）

---

### 1.2 精选页链接下载失败

**症状:** 用户通过 `https://www.douyin.com/?recommend=1` 或 `https://www.douyin.com/jingxuan?modal_id=xxx` 链接提交，所有引擎失败。

**根因:** 抖音精选页不是标准视频页面，没有 `aweme_detail` API 响应。Playwright 加载的是推荐流页面，而非单个视频。

**修复:** `core/downloader.py:340-345` — 检测 `modal_id=` 参数，自动转换为标准视频页 URL：
```python
video_url_page = f"https://www.douyin.com/video/{modal_id}"
```

**文件:** `core/downloader.py:340-345`

---

### 1.3 Windows GBK 编码导致 rich 库崩溃

**症状:** douyin-downloader 子进程因 `UnicodeEncodeError: 'gbk' codec can't encode character` 崩溃。错误字符是 rich 库输出的 `✓` (U+2713) 和 `✗` (U+2717)。

**根因:** Windows 终端默认编码为 GBK，而 rich 库输出 Unicode 符号无法被 GBK 编码。

**修复:** `core/downloader.py:127-129` — 子进程环境变量强制 UTF-8：
```python
env.setdefault("PYTHONIOENCODING", "utf-8")
env.setdefault("TERM", "xterm-256color")
```

**文件:** `core/downloader.py:127-129`, `douyin-downloader/cli/progress_display.py:250,256`

---

### 1.4 douyin-downloader 报告成功但未找到 MP4

**症状:** douyin-downloader 子进程退出码为 `0`，但在预期目录中找不到 `.mp4` 文件。

**根因:** douyin-downloader 输出文件位置与代码预期不一致，或 URL 本身无可下载视频。

**修复:** `core/downloader.py:156-166` — 在下载目录中递归查找 MP4 文件，找不到则明确报错。

**文件:** `core/downloader.py:156-166`

---

## 2. Gradio 6.x 兼容性问题

### 2.1 CSS 参数 API 变更

**症状:** `gr.Blocks(css=CSS)` 在 Gradio 6.x 上报错。

**根因:** Gradio 6.x 将 `css` 参数从 `Blocks` 构造函数移到了 `launch()` 方法。

**修复:** 将 `css` 参数从 `gr.Blocks(css=CSS)` 改为 `demo.launch(css=CSS, ...)`。

**文件:** `app.py:551`

---

### 2.2 SSE API 端点变更

**症状:** 使用旧版 `/api/predict/` 端点调用失败。

**根因:** Gradio 6.x 将 API 端点从 `/api/predict/` 改为 `/gradio_api/call/{api_name}`，并改用 SSE 流式调用方式。

**修复:** 更新 API 调用适配新端点格式，使用 SSE event_id 轮询 `/gradio_api/call/{api_name}/output` 获取结果。

---

### 2.3 Windows 启动异常（假阳性）

**症状:** `demo.launch()` 在 Windows 上报错，但 uvicorn 实际已在运行。

**根因:** Gradio 6.x 的 `startup-events` 检查在 Windows 上有兼容性问题，会误报异常。

**修复:** `app.py:549-568` — 将 launch 放入守护线程，通过轮询端口 7860 判断服务是否就绪：
```python
t = threading.Thread(target=_launch, daemon=True)
t.start()
# 轮询端口直到就绪
```

**文件:** `app.py:549-568`

---

### 2.4 HTML sanitization 剥离自定义元素

**症状:** 批量分析结果显示任务数量和分镜数量，但不显示结构化分镜表格。`<details>`、`<summary>`、`<table>` 元素全部消失。

**根因:** Gradio 6.x 的 `gr.HTML` 组件默认 `sanitize_html=True`，会剥离非白名单的 HTML 元素和属性。

**修复:** `app.py` 中两个 `gr.HTML` 组件添加 `sanitize_html=False`，同时使用 `html.escape()` 对所有动态文本内容做转义，防止 XSS：
```python
result_html = gr.HTML(label="分析结果", sanitize_html=False)
batch_result_html = gr.HTML(label="批量分析结果", sanitize_html=False)
```

**文件:** `app.py:398,426`（添加 `sanitize_html=False`）, `app.py:67-68,352-353`（添加 `html.escape()`）

---

## 3. 语义分镜问题

### 3.1 DeepSeek 返回缺失 end_text 字段

**症状:** 批量处理时，第二条视频的 segmentation 阶段因 `pydantic.ValidationError` 崩溃，导致整个 batch 任务部分失败。错误信息：`end_text field required (type=missing)`。

**根因:** DeepSeek API 返回的语义分段中，部分 segment 缺少 `end_text` 字段（边界情况，通常是最后一个或分段密集时）。

**修复:** `core/segmenter.py:100-115` — 两重防护：
1. `seg_data.setdefault("end_text", seg_data.get("start_text", ""))` — 用 `start_text` 兜底
2. 外层 `try/except` 捕获 `ValidationError`，如果解析失败则回退为单个全文分段

```python
seg_data.setdefault("end_text", seg_data.get("start_text", ""))
...
except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as e:
    # 回退为单个分段
```

**文件:** `core/segmenter.py:100-101`, `core/segmenter.py:104-115`

---

### 3.2 FusedScene 时间校验边界

**症状:** 潜在风险：`start_time > end_time` 导致数据校验失败。

**根因:** 融合算法中，当语义边界紧邻且端时间匹配不精确时，可能出现开始时间大于结束时间。

**修复:** `models/schemas.py:103-107` — 添加 `model_validator` 校验。`core/fuser.py:94` — 使用 `min(end_ts, next_start)` 防止时间越界。

**文件:** `models/schemas.py:103-107`, `core/fuser.py:94`

---

## 4. 批量分析 UI 问题

### 4.1 结构化分镜不显示（多层嵌套问题）

**症状:** 用户反复报告批量分析结果"看不到结构化分镜脚本"——只有任务标签和分镜数量，没有具体内容。

**排查过程:**
1. 初次怀疑：数据模型未正确填充 → 检查 fuser.py 确认 FusedScene 字段有值 ✓
2. 改用 details/summary 折叠布局 → 用户仍看不到
3. 发现 Gradio sanitize_html 剥离了 details 元素 → 修复合 sanitize_html=False
4. CSS 也用了新的 task-details/scene-table 样式

**最终根因:** Gradio 6.x 的 HTML sanitizer 默认开启，导致所有自定义 HTML 结构被剥离。加上旧的 CSS 样式与新的 HTML 结构不匹配。

**修复方案（最终）:**
- `sanitize_html=False` 放行自定义 HTML
- `html.escape()` 确保内容安全
- `<details>` 手风琴 + `<table>` 表格布局展示分镜
- CSS 完整替换为手风琴/表格样式

**文件:** `app.py` — `_build_batch_html_result()` 函数、CSS 定义、gr.HTML 参数

---

## 5. 系统兼容性问题

### 5.1 ffmpeg PATH 解析

**症状:** `shutil.which("ffmpeg")` 能找到项目目录下的 ffmpeg.exe，但 `subprocess.Popen("ffmpeg")` 找不到。

**根因:** Python 的 `subprocess` 不使用与 `shutil.which` 完全相同的 PATH 解析逻辑。

**修复:** `core/audio_extractor.py:28-43` — 手动将项目目录加入 `PATH` 环境变量。`app.py:545` — 入口处也做了同样处理。

**文件:** `core/audio_extractor.py:28-43`, `app.py:545`

---

### 5.2 douyin-downloader 配置路径

**症状:** douyin-downloader 的 `run.py` 内部执行了 `os.chdir(project_root)`，导致相对路径的 `-c config.yml` 找不到配置文件。

**修复:** 传入 `-c` 参数时使用配置文件的绝对路径。

**文件:** `core/downloader.py:108-111`

---

## 附录：修复汇总

| # | 问题 | 严重度 | 涉及文件 | 修复类型 |
|---|------|--------|----------|----------|
| 1 | 所有下载引擎失败 | 严重 | `core/downloader.py` | Cookie 格式 + RENDER_DATA 回退 |
| 2 | 精选页链接下载失败 | 高 | `core/downloader.py` | modal_id → 标准视频页转换 |
| 3 | Windows GBK 编码崩溃 | 高 | `core/downloader.py` | 环境变量强制 UTF-8 |
| 4 | douyin-downloader 无 MP4 | 中 | `core/downloader.py` | 递归查找 + 明确报错 |
| 5 | Gradio CSS API 变更 | 高 | `app.py` | css 参数移至 launch() |
| 6 | Gradio SSE API 变更 | 高 | (API 调用层) | 适配新端点格式 |
| 7 | Gradio Windows 假阳性 | 低 | `app.py` | 守护线程 + 端口轮询 |
| 8 | HTML sanitization 剥离元素 | 严重 | `app.py` | sanitize_html=False + html.escape |
| 9 | DeepSeek 缺失 end_text | 高 | `core/segmenter.py` | setdefault 兜底 + try/except |
| 10 | FusedScene 时间越界 | 低 | `models/schemas.py`, `core/fuser.py` | model_validator + min() 约束 |
| 11 | 批量 UI 不展示分镜 | 严重 | `app.py` | sanitize_html + HTML 结构 + CSS 重写 |
| 12 | ffmpeg PATH 问题 | 中 | `core/audio_extractor.py` | 手动 PATH 追加 |
| 13 | douyin-downloader 配置路径 | 低 | `core/downloader.py` | 绝对路径配置 |
