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
- `FRAME_RATE` sampled FPS
- `DETECTION_CONF_THRESHOLD` minimum confidence for detections

Segmentation tuning:

- `SEGMENT_GAP` max frame gap to keep same segment
- `MIN_SEGMENT_FRAMES` minimum segment length to keep

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

## Notes

- If detections span most frames, clips may still be long; tune `DETECTION_CONF_THRESHOLD`, `SEGMENT_GAP`, and `MIN_SEGMENT_FRAMES`.
- Current tuned defaults in `.env` are set for shorter/cleaner clips on typical real videos:
  - `DETECTION_CONF_THRESHOLD=0.45`
  - `SEGMENT_GAP=2`
  - `MIN_SEGMENT_FRAMES=8`
  - `FATIGUE_ALERT_FRAME_RATIO=0.10`
- Keep secrets out of source control and use local `.env` values.

## License

MIT
