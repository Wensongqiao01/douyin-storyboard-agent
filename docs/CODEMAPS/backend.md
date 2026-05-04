<!-- Generated: 2026-05-01 | Files scanned: 48 | Token estimate: ~600 -->

# Backend Architecture

## Entry Point
`app.py` → `core.pipeline.run_pipeline()` (sync, Gradio thread pool)

## Module Map

### Core Pipeline (`core/pipeline.py`)
```
Pipeline.__init__(downloader, audio_extractor, transcriber, segmenter, scene_detector, fuser)
Pipeline.run(url) → TaskResult
run_pipeline(url, ...) → TaskResult    # convenience wrapper
```

### Downloader (`core/downloader.py`)
```
download_video(url, output_path, cookie) → str    # file path
Strategy: douyin-downloader (subprocess) → yt-dlp (Python) auto-fallback
Timeout: 120s with CREATE_NEW_PROCESS_GROUP (Windows)
```

### Audio Extractor (`core/audio_extractor.py`)
```
AudioExtractor.__init__(sample_rate=16000)
AudioExtractor.extract(video_path, output_path) → str    # wav file path
Tool: ffmpeg-python
```

### Transcriber (`core/transcriber.py`)
```
Transcriber.__init__(model_size="base", device="cpu")
Transcriber.transcribe(audio_path) → WhisperResult
Engine: faster-whisper (CTranslate2)
Output: word-level timestamps
```

### Scene Detector (`core/scene_detector.py`)
```
SceneDetector.__init__(threshold=30.0)
SceneDetector.detect(video_path) → SceneCutsResult
Engine: PySceneDetect (ContentDetector)
```

### Segmenter (`core/segmenter.py`)
```
Segmenter.__init__(api_key, model="deepseek-chat")
Segmenter.segment(whisper_result) → SemanticResult
Engine: DeepSeek API via OpenAI SDK (tenacity retry)
```

### Fuser (`core/fuser.py`)
```
fuse_scenes(semantic_result, scene_result, whisper_result, align_window) → list[FusedScene]
Strategy: semantic segments as skeleton, scene cuts as boundary refinement
```

## Utils (`utils/`)

| File | Key Functions |
|------|---------------|
| `file_helpers.py` | `generate_task_id()`, `ensure_dir()`, `get_task_paths()`, `cleanup_task()` |
| `text_matcher.py` | `find_text_timestamp()`, `match_boundary()` — rapidfuzz fuzzy matching |

## Config (`config.py`)
```
AppConfig (pydantic-settings, reads .env)
  Fields: douyin_cookie, whisper_model_size, whisper_device, deepseek_api_key,
          deepseek_model, scene_detect_threshold, output_base_dir,
          fuse_align_window, export_scene_clips
```

## Data Models (`models/schemas.py`)
```
TaskStatus (enum): PENDING → DOWNLOADING → TRANSCRIBING → DETECTING → SEGMENTING → FUSING → DONE | ERROR
WordTimestamp: word + start + end (seconds)
WhisperResult: text + segments[WordTimestamp] + duration
SceneCut: time + frame
SceneCutsResult: cuts[SceneCut] + total_frames
SemanticSegment: index + summary + start_text + end_text
SemanticResult: segments[SemanticSegment]
FusedScene: index + start_time + end_time + summary + text + has_scene_cut
TaskResult: task_id + status + title + scenes[FusedScene] + error_message
```
