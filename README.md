# Surveillance Video Event Detection Pipeline

Offline, modular video-intelligence pipeline for surveillance and driver-behavior analysis. It runs locally and integrates real models for detection and transcription, plus fatigue analytics and alert generation.

## What It Does

1. Extracts frames from video.
2. Runs YOLO detections (with confidence filtering).
3. Builds temporal segments.
4. Clips video segments.
5. Runs fatigue analytics on frames.
6. Transcribes segment audio.
7. Generates alerts and a human-readable report.
8. Generates Qwen-based per-clip and whole-video summaries.

## Project Structure

```text
main.py
pipelines/
  alerts.py
  clipper.py
  detect.py
  ingest.py
  pose_fatigue.py
  report.py
  segmenter.py
  transcriber.py
output/
  clips/
  detections.json
  frames/
  pose_fatigue.json
  report.txt
  segments.json
  alerts.json
  transcripts/
  qwen/
```

## Quickstart

### Prerequisites

- Python 3.8+
- FFmpeg on PATH

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```powershell
python main.py input_video.mp4 output
```

## Key Configuration (.env)

Model and runtime:

- `YOLO_MODEL_PATH` path to YOLO model
- `WHISPER_MODEL_PATH` whisper model path or model name
- `QWEN_API_BASE_URL` OpenAI-compatible Qwen endpoint
- `QWEN_MODEL` preferred Qwen model name
- `QWEN_MODEL_CANDIDATES` fallback candidate list tried in order
- `FRAME_RATE` sampled FPS
- `DETECTION_CONF_THRESHOLD` minimum confidence for detections

Segmentation tuning:

- `SEGMENT_GAP` max frame gap to keep same segment
- `MIN_SEGMENT_FRAMES` minimum segment length to keep
- `MAX_SEGMENT_FRAMES` optional hard cap for splitting (set `0` to disable fixed-size splitting)
- `EVENT_LABELS` comma-separated event labels used for event-based clipping, or `*` for all detected events
- `MIN_EVENT_SCORE` minimum event score used by the segment builder
- `MIN_EVENT_SEGMENT_FRAMES` minimum segment length specifically for event mode
- `EVENT_PADDING_FRAMES` frame padding added before/after each detected event window
- `EVENT_OCCURRENCE_BY_LABEL` when `1`, builds separate segments per event label occurrence (default `1`)
- `EVENT_MERGE_PADDED_OVERLAPS` when `1`, merges overlapping padded segments (default `0` to keep each occurrence as its own clip)
- `CLIP_SIGNIFICANT_EVENTS_ONLY` when `1`, clip only anomaly-relevant event labels (default `1`)
- `SIGNIFICANT_EVENT_LABELS` comma-separated anomaly-relevant labels (default: `cell phone,phone,laptop`)
- `REPORT_SIGNIFICANT_EVENTS_ONLY` when `1`, report detection analytics for significant labels only (default `1`)
- `USE_POSE_FOR_SIGNIFICANT_EVENTS` when `1`, include pose/fatigue events as clip-worthy anomalies (default `1`)
- `SIGNIFICANT_FATIGUE_FLAGS` fatigue indicators treated as significant (default: `microsleep,asleep,slouch,head_nod,yawn`)
- `HIGH_PRIORITY_EVENT_LABELS` labels forced to stay isolated as separate clips even when nearby windows overlap (default: `fatigue_microsleep,fatigue_asleep`)

Alerting:

- `FATIGUE_ALERT_FRAME_RATIO` fatigue ratio threshold for high alert
- `MAX_MICROSLEEP_EVENTS` max tolerated microsleep frames
- `MAX_YAWN_EVENTS` max tolerated yawn frames
- `HIGH_RISK_LABELS` comma-separated labels that trigger behavior alerts

## Output Files

- `output/detections.json` YOLO detections
- `output/segments.json` segment boundaries
- `output/clips/` clipped videos
- `output/pose_fatigue.json` per-frame fatigue metrics
- `output/alerts.json` generated alerts and summary
- `output/transcripts/transcripts_index.json` transcript index
- `output/report.txt` consolidated text report
- `output/qwen/clip_summaries.json` per-clip Qwen summaries (raw record)
- `output/qwen/clip_summaries.md` per-clip Qwen summaries in Markdown
- `output/qwen/whole_video_summary.md` whole-video Qwen summary in Markdown
- `output/qwen/qwen_summary_manifest.json` summary manifest and model metadata

## Reporting and Alerts

The report now includes:

- Overall counts (frames, detections, segments)
- Detection confidence analytics (min/avg/max, P50/P90/P95, top labels)
- Fatigue metrics (blink, microsleep, yawn, nod, slouch)
- Segment transcript references
- Alert summary with severity labels
- Per-segment risk summary (severity, fatigue score, high-risk hits)

`alerts.json` now includes:

- Global alerts for the full video
- `segment_alerts` entries mapped by segment (`segment_id`, `start_frame`, `end_frame`)

`qwen/` now includes:

- `clip_summaries.json` one summary per transcript clip
- `clip_summaries.md` all clip summaries rendered as Markdown
- `whole_video_summary.md` an executive summary for the whole run (Markdown)
- `qwen_summary_manifest.json` metadata about the model/base URL used

## Notes

- If detections span most frames, clips may still be long; tune `DETECTION_CONF_THRESHOLD`, `SEGMENT_GAP`, and `MIN_SEGMENT_FRAMES`.
- Current tuned defaults in `.env` are set for shorter/cleaner clips on typical real videos:
  - `DETECTION_CONF_THRESHOLD=0.45`
  - `SEGMENT_GAP=2`
  - `MIN_SEGMENT_FRAMES=3`
  - `MAX_SEGMENT_FRAMES=0`
  - `EVENT_LABELS=*`
  - `MIN_EVENT_SCORE=0.35`
  - `MIN_EVENT_SEGMENT_FRAMES=1`
  - `EVENT_PADDING_FRAMES=1`
  - `EVENT_OCCURRENCE_BY_LABEL=1`
  - `EVENT_MERGE_PADDED_OVERLAPS=0`
  - `CLIP_SIGNIFICANT_EVENTS_ONLY=1`
  - `SIGNIFICANT_EVENT_LABELS=cell phone,phone,laptop`
  - `REPORT_SIGNIFICANT_EVENTS_ONLY=1`
  - `USE_POSE_FOR_SIGNIFICANT_EVENTS=1`
  - `SIGNIFICANT_FATIGUE_FLAGS=microsleep,asleep,slouch,head_nod,yawn`
  - `HIGH_PRIORITY_EVENT_LABELS=fatigue_microsleep,fatigue_asleep`
  - `FATIGUE_ALERT_FRAME_RATIO=0.10`
- Keep secrets out of source control and use local `.env` values.
- For Qwen summaries, set `QWEN_API_BASE_URL` and `QWEN_MODEL` if your endpoint differs from the default OpenAI-compatible layout.
- If one Qwen model name is unavailable, the pipeline automatically tries the next candidate in `QWEN_MODEL_CANDIDATES`.

## License

MIT
