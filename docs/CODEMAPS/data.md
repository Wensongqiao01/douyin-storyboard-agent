<!-- Generated: 2026-05-01 | Files scanned: 48 | Token estimate: ~400 -->

# Data Architecture

## Storage Strategy
**File-based, zero databases.** Each pipeline run creates an isolated task directory.

## Output Directory Structure
```
output/
└── {task_id}/
    ├── video/
    │   └── original.mp4          # downloaded video
    ├── audio/
    │   └── audio.wav             # extracted audio (16kHz mono)
    ├── intermediate/
    │   ├── whisper_raw.json      # WhisperResult (word timestamps)
    │   ├── scene_cuts_raw.json   # SceneCutsResult (cut points)
    │   └── semantic_raw.json     # SemanticResult (DeepSeek segments)
    ├── result.json               # TaskResult (final fused scenes)
    └── report.md                 # human-readable report (TODO)
```

## Data Flow (per task)

```
Input:  URL (string)
        │
Stage1:  original.mp4          ──► written by downloader
Stage2:  audio.wav             ──► written by ffmpeg
Stage3:  whisper_raw.json      ──► written by Transcriber
Stage4:  semantic_raw.json     ──► written by Segmenter
Stage5:  scene_cuts_raw.json   ──► written by SceneDetector
Stage6:  FusedScene[]          ──► returned in TaskResult
```

## Pydantic Models (Data Contracts)

```
                         ┌──────────────┐
                         │  TaskResult   │
                         │  (final out)  │
                         └──────┬───────┘
                                │ contains list of
                         ┌──────▼───────┐
                  ┌──────│  FusedScene  │
                  │      └──────────────┘
         ┌────────┴────────┐         ┌──────────┴──────────┐
         ▼                              ▼
┌──────────────────┐          ┌───────────────────┐
│  WhisperResult   │          │  SceneCutsResult  │
│  + WordTimestamp │          │  + SceneCut       │
└──────────────────┘          └───────────────────┘
         │
         ▼
┌──────────────────┐
│  SemanticResult  │
│  + SemanticSegm  │
└──────────────────┘
```

## Task ID Format
`YYYYMMDD_HHMMSS_XXXXX` — timestamp + 5-char random hex suffix.
Example: `20260501_221717_f6802`

## File Sizes (estimated)
| File | Size | Notes |
|------|------|-------|
| original.mp4 | 5-50 MB | Douyin video |
| audio.wav | 1-10 MB | 16kHz mono PCM |
| whisper_raw.json | 10-100 KB | word-level timestamps |
| scene_cuts_raw.json | 1-10 KB | cut points |
| semantic_raw.json | 1-5 KB | semantic segments |
