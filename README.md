# Railway Safety Video Intelligence

An offline video-intelligence product for railway driver monitoring.

It turns a raw video into operational evidence: event clips, fatigue signals, alerts, transcripts, and a readable report. The pipeline runs locally and is designed to help surface unsafe driving behavior, attention lapses, and suspicious in-cab actions quickly.

## Product Value

- Identify safety-critical moments in long surveillance-style video.
- Convert raw footage into short, reviewable clips.
- Highlight behavior concerns such as slouching, fatigue, microsleep, and distracting object use.
- Produce summaries that are easy to review by operations, safety, or compliance teams.
- Keep the workflow offline-first, with optional Qwen summaries when a compatible endpoint is available.

## What The Product Delivers

The pipeline produces a complete review package from a single input video:

- extracted frames
- event detections
- event-based segments and clips
- pose and fatigue metrics
- alert summaries
- transcripts for each clip
- a final human-readable report
- Qwen-generated clip and whole-video summaries in Markdown

## End-to-End Flow

1. Load runtime defaults from `.env`.
2. Extract video frames at the configured sample rate.
3. Run object detection with confidence filtering.
4. Analyze pose and fatigue signals frame by frame.
5. Build event windows from significant behavior and safety events.
6. Clip each event window into a separate video file.
7. Transcribe clip audio.
8. Generate alerts and a final report.
9. Produce Qwen summaries for clip-level and whole-video review.

## How It Works

The current pipeline is centered on three review categories:

- Safety distractions: phone, laptop, and similar in-cab objects.
- Driver fatigue: microsleep, slouching, head nods, and yawns.
- Operational evidence: clips, transcripts, alerts, and Markdown summaries.

Event windows are preserved as separate clips so each occurrence can be reviewed independently. High-priority fatigue events are kept isolated even when they occur near other activity.

## Output Artifacts

Generated files are written to `output/`:

- `detections.json` detection results
- `segments.json` event windows with timestamps and severity
- `clips/` one clip per event occurrence
- `pose_fatigue.json` per-frame fatigue and posture metrics
- `alerts.json` alert summary and segment risk data
- `transcripts/` clip transcript files and transcript index
- `report.txt` final product-style summary
- `qwen/clip_summaries.md` clip summaries in Markdown
- `qwen/whole_video_summary.md` full-run summary in Markdown
- `qwen/qwen_summary_manifest.json` model and endpoint metadata

## Configuration

These settings are controlled through `.env`:

### Core Model Settings

- `YOLO_MODEL_PATH` path to the detection model
- `WHISPER_MODEL_PATH` whisper model path or model name
- `QWEN_API_BASE_URL` OpenAI-compatible Qwen endpoint
- `QWEN_MODEL` preferred Qwen model name
- `QWEN_MODEL_CANDIDATES` fallback Qwen model list

### Detection And Segmentation

- `FRAME_RATE` frame sampling rate
- `DETECTION_CONF_THRESHOLD` minimum detection confidence
- `SEGMENT_GAP` max frame gap inside a segment
- `MIN_SEGMENT_FRAMES` minimum segment size
- `MAX_SEGMENT_FRAMES` optional hard cap for splitting
- `EVENT_LABELS` labels used to define event-based clipping
- `MIN_EVENT_SCORE` minimum score for event inclusion
- `MIN_EVENT_SEGMENT_FRAMES` minimum event segment size
- `EVENT_PADDING_FRAMES` frame padding around each event window
- `EVENT_OCCURRENCE_BY_LABEL` preserve each occurrence as its own clip
- `EVENT_MERGE_PADDED_OVERLAPS` merge overlapping padded windows only when needed

### Safety And Significance

- `CLIP_SIGNIFICANT_EVENTS_ONLY` clip only anomaly-relevant events
- `SIGNIFICANT_EVENT_LABELS` labels considered safety-relevant distractions
- `REPORT_SIGNIFICANT_EVENTS_ONLY` report only significant detections
- `USE_POSE_FOR_SIGNIFICANT_EVENTS` include pose/fatigue events in segment creation
- `SIGNIFICANT_FATIGUE_FLAGS` fatigue flags treated as significant
- `HIGH_PRIORITY_EVENT_LABELS` labels that must remain isolated as separate clips

### Alerting

- `FATIGUE_ALERT_FRAME_RATIO` fatigue threshold for high alert
- `MAX_MICROSLEEP_EVENTS` microsleep tolerance
- `MAX_YAWN_EVENTS` yawn tolerance
- `HIGH_RISK_LABELS` labels that trigger behavior alerts

## Recommended Defaults

For this project, the tuned defaults are aimed at short, reviewable clips:

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

## Setup

### Prerequisites

- Python 3.8+
- FFmpeg on PATH

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```powershell
python main.py input_video.mp4 output
```

If you are working inside this workspace, using `.venv/Scripts/python.exe` directly avoids interpreter mismatch.

## Reading The Results

The most useful outputs for review are:

- `segments.json` for event timing and severity
- `clips/` for each event occurrence
- `alerts.json` for fatigue and behavior alerts
- `report.txt` for a compact summary of what happened
- `qwen/whole_video_summary.md` for a narrative executive summary

## Operational Notes

- Dense detections can still produce longer clips; tune `DETECTION_CONF_THRESHOLD`, `SEGMENT_GAP`, and event-related thresholds for the target video.
- Keep API keys and provider details in local `.env` files only.
- Qwen summaries require a compatible OpenAI-style endpoint and an available model name.
- If one Qwen model is not available, the pipeline automatically tries the next fallback candidate.

## Repository Layout

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
  qwen_summary.py
output/
tests/
```

## License

MIT
