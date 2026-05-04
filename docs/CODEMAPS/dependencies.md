<!-- Generated: 2026-05-01 | Files scanned: 48 | Token estimate: ~500 -->

# Dependencies

## External Services

| Service | Auth | Usage | Module |
|---------|------|-------|--------|
| DeepSeek API | `deepseek_api_key` (.env) | Semantic segmentation | `core/segmenter.py` |
| Douyin CDN | `douyin_cookie` (.env) | Video download | `core/downloader.py` |

No other external services. Whisper runs locally (CPU/CUDA).

## Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `gradio` | >=5.0 | Web UI |
| `faster-whisper` | >=1.1 | Speech-to-text (CTranslate2) |
| `scenedetect[opencv]` | >=1.0 | Video scene cut detection |
| `ffmpeg-python` | >=0.2 | Audio extraction |
| `openai` | >=1.0 | DeepSeek API client |
| `pydantic` | >=2.0 | Data models |
| `pydantic-settings` | >=2.0 | Config management (.env) |
| `rapidfuzz` | >=3.0 | Fuzzy text matching |
| `yt-dlp` | >=2024.12 | Video download fallback engine |
| `loguru` | >=0.7 | Logging |
| `tenacity` | >=8.0 | API retry with exponential backoff |
| `python-dotenv` | >=1.0 | .env loading |
| `pytest` / `pytest-cov` | >=8.0 / >=5.0 | Testing |

## System Dependencies

| Tool | Usage | Installed |
|------|-------|-----------|
| `ffmpeg.exe` | Audio extraction | ✅ (bundled in project root) |
| Python 3.11+ | Runtime | ✅ |

## Git Submodule

| Repository | Path | Purpose |
|------------|------|---------|
| [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader) | `douyin-downloader/` | Primary Douyin download engine (subprocess) |

douyin-downloader itself depends on: `httpx`, `curl_cffi`, `aiofiles`, `pillow`, `rich`, `flask`
→ See `douyin-downloader/requirements.txt` for full list.

## Test Dependencies

| Command | Files |
|---------|-------|
| `pytest tests/` | `tests/test_*.py` (12 test files, 109 tests) |
| `pytest --cov=core --cov=utils --cov=models` | Coverage tracked |
