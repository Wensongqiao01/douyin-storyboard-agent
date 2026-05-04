<!-- Generated: 2026-05-01 | Files scanned: 48 (app) + 70 (douyin-downloader) | Token estimate: ~800 -->

# Architecture

## Project Type
Single Python application — Gradio web UI orchestrating a video analysis pipeline.

## System Diagram

```
User (Browser)
    │  http://127.0.0.1:7860
    ▼
┌─────────────────┐
│   app.py        │  Gradio Web UI (Blocks)
│   (entry point) │
└────────┬────────┘
         │  analyze(url, ...)
         ▼
┌─────────────────┐
│  core/pipeline  │  Orchestration layer
│  .run()         │  ↓ 6 sequential stages
└────────┬────────┘
         │
    ┌────┼────┬────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼    ▼
  下载  音频  转写  语义  检测  融合
  │     │     │    │    │    │
  ▼     ▼     ▼    ▼    ▼    ▼
 mp4   wav  json  json  json  result
 文件  文件  缓存  缓存  缓存  输出
```

## Six-Stage Pipeline Flow

```
URL ──► download_video() ──► original.mp4
        core/downloader.py     (douyin-downloader → yt-dlp)

original.mp4 ──► AudioExtractor.extract() ──► audio.wav
                  core/audio_extractor.py

audio.wav ──► Transcriber.transcribe() ──► whisper_raw.json
               core/transcriber.py          (Whisper word timestamps)

whisper_raw ──► Segmenter.segment() ──► semantic_raw.json
                 core/segmenter.py          (DeepSeek semantic segments)

original.mp4 ──► SceneDetector.detect() ──► scene_cuts_raw.json
                  core/scene_detector.py     (PySceneDetect cut points)

3 JSONs ──► fuse_scenes() ──► FusedScene[]
              core/fuser.py                 (scene cuts + semantics + word timestamps)
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fusion strategy | semantics as skeleton, cuts as boundaries | Semantic segments define intent, scene cuts refine precise timestamps |
| Download engine | dual (primary + fallback) | douyin-downloader may fail; yt-dlp auto-fallback |
| Intermediate cache | JSON files in output/{task_id}/intermediate/ | Debug fusion logic without re-running pipeline |
| Download timeout | 120s + CREATE_NEW_PROCESS_GROUP | Windows subprocess timeout fix |
| UI independence | core/ has zero UI imports | core/ works with any frontend (Gradio/FastAPI/CLI) |

## Layer Boundaries

```
┌──────────────────────────────────────┐
│  app.py            (UI layer)        │  ← depends on core/, models/, config
├──────────────────────────────────────┤
│  core/pipeline.py  (orchestration)   │  ← depends on core/*, models/, utils/, config
│  core/*.py         (business logic)  │
├──────────────────────────────────────┤
│  utils/            (helpers)         │  ← depends on models/, config
│  models/schemas.py (data contracts)  │  ← zero dependencies
│  config.py         (settings)        │  ← zero dependencies (pydantic-settings)
└──────────────────────────────────────┘
```
