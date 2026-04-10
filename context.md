# Project Context (LLM Handoff)

## 1. What this project is
This repository implements an offline video-intelligence pipeline for railway locopilot monitoring.
It processes a video end-to-end and generates:
- detections
- event-based segments and clips
- fatigue/posture analytics
- alerts
- transcripts
- a consolidated report
- Qwen-powered summaries (per-clip and whole-video) in Markdown

Primary goal: provide actionable safety monitoring outputs from surveillance-like video input.

## 2. Current high-level status
The pipeline is functional and runs successfully with exit code 0 using the workspace virtual environment.

Most recent verified behavior:
- Ingest, detect, segment, clip, fatigue analysis, alerts, transcribe, report all complete.
- Qwen remote summaries are working with model fallback.
- Summary outputs are now forced/normalized to Markdown format.

## 3. Repository structure
Top-level:
- main.py: orchestrates the complete pipeline
- README.md: setup and runtime docs
- requirements.txt: Python dependencies
- video_intelligence_prd.md: product requirements reference
- output/: generated artifacts
- pipelines/: processing modules
- tests/: unit tests

Core pipeline modules in pipelines/:
- ingest.py: frame extraction via FFmpeg
- detect.py: YOLO detection and class/score handling
- segmenter.py: event-driven segment generation
- clipper.py: FFmpeg clipping from segment windows
- pose_fatigue.py: OpenCV-based fatigue/posture metrics
- alerts.py: global + per-segment alerts
- transcriber.py: Whisper transcription
- report.py: human-readable report generation
- qwen_summary.py: per-clip + whole-video LLM summarization
- utils.py: shared helper functions (dirs/json/frame parsing)

## 4. End-to-end pipeline flow
1. Read .env defaults in main.py.
2. Clear stale run artifacts (frames, clips).
3. Extract frames from input video.
4. Run detections and save output/detections.json.
5. Build event segments and save output/segments.json.
6. Clip segments into output/clips/.
7. Run fatigue/posture analysis into output/pose_fatigue.json.
8. Generate alerts into output/alerts.json.
9. Transcribe clips into output/transcripts/.
10. Generate consolidated report at output/report.txt.
11. Generate Qwen summaries in output/qwen/.

## 5. Important implementation decisions already made
- Real model wiring is in place for YOLO + Whisper (not placeholder-only pipeline).
- MediaPipe fatigue approach was replaced with a more stable OpenCV-based fatigue/posture analyzer.
- Segmentation moved from fixed-window behavior to event-driven segmentation with thresholds and padding.
- Label mapping issues in detection were fixed so segment filtering uses correct labels.
- Clipper defaults to reliable encoding mode to avoid malformed outputs.
- Shared helpers were centralized in pipelines/utils.py to reduce duplication.
- Qwen summarization supports model fallback candidates and remote endpoint compatibility.
- Qwen output formatting was updated to Markdown, including cleanup of reasoning/fenced/JSON-style model output.

## 6. Qwen summary output contract (latest)
Generated under output/qwen/:
- clip_summaries.json: per-clip records with qwen_summary field
- clip_summaries.md: human-readable Markdown per clip
- whole_video_summary.md: final whole-video Markdown summary
- qwen_summary_manifest.json: model/base URL metadata and output paths

Notes:
- qwen_summary.py now prompts for Markdown explicitly.
- If model still returns JSON or fenced text, normalization converts it to Markdown sections.
- Legacy whole_video_summary.txt is removed during generation to prevent stale-format confusion.

## 7. Runtime/config knobs used in this project
Configured through .env (do not commit secrets):
- Detection/model: YOLO_MODEL_PATH, WHISPER_MODEL_PATH, DETECTION_CONF_THRESHOLD
- Sampling/segmentation: FRAME_RATE, SEGMENT_GAP, MIN_SEGMENT_FRAMES, MAX_SEGMENT_FRAMES
- Event clipping: EVENT_LABELS, MIN_EVENT_SCORE, MIN_EVENT_SEGMENT_FRAMES, EVENT_PADDING_FRAMES
- Alerting: FATIGUE_ALERT_FRAME_RATIO, MAX_MICROSLEEP_EVENTS, MAX_YAWN_EVENTS, HIGH_RISK_LABELS
- Qwen: QWEN_API_KEY, QWEN_API_BASE_URL, QWEN_MODEL, QWEN_MODEL_CANDIDATES

## 8. Current outputs in this workspace snapshot
Observed in output/:
- alerts.json
- clips/
- detections.json
- frames/
- pose_fatigue.json
- qwen/
- report.txt
- segments.json
- transcripts/

Current transcript index points to one clip:
- output/clips/segment_001.mp4
- output/transcripts/segment_001.txt

## 9. How to run
From repo root:
1. Create/activate virtual environment.
2. Install dependencies from requirements.txt.
3. Run:
   python main.py input.mp4 output

Recommended in this workspace:
- Use .venv/Scripts/python.exe explicitly to avoid interpreter/package mismatch.

## 10. Known caveats / operational notes
- If detections are dense across many frames, segments/clips can still be long.
- Tuning confidence and segmentation thresholds remains the main lever for clip granularity.
- Endpoint/model availability for Qwen depends on provider account and model access.
- Keep .env local and private (API keys/tokens).

## 11. Suggested next steps for any new LLM/engineer
1. Validate output quality on multiple videos (input.mp4, input6.mp4, sample.mp4, sample2.mp4).
2. Tune EVENT_* and DETECTION_CONF_THRESHOLD per use case for better clip precision.
3. Improve prompt templates for domain-specific reporting language (rail operations SOP style).
4. Add tests for qwen_summary normalization paths (JSON/fenced/reasoning cleanup).
5. Add regression checks that assert Markdown outputs are always produced.

## 12. Quick continuation checklist
When continuing work, first verify:
- main.py pipeline exits successfully
- output/qwen/whole_video_summary.md exists and is Markdown
- output/qwen/clip_summaries.md exists and is Markdown
- qwen_summary_manifest.json shows expected model/base_url/used_remote
