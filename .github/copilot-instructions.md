# Copilot Instructions for `survellaince-clipping-transcribe`

## Build, test, and lint commands

Use Python in a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Run the CLI pipeline:

```powershell
python main.py input_video.mp4 output
```

Run the web app:

```powershell
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Run tests:

```powershell
pytest -q
```

Run a single test (file + test function):

```powershell
pytest -q tests\test_app_api.py::test_health_endpoint
```

No dedicated lint configuration (for example `ruff`, `flake8`, or `pylint`) is currently checked into this repository.

## High-level architecture

This repository has two entry surfaces sharing the same pipeline core:

1. **CLI flow** (`main.py`): loads `.env`, clears stale artifacts, then executes ingest -> detection -> pose/fatigue -> segmentation -> clipping -> alerts -> transcription -> report -> optional Qwen summaries.
2. **Web/API flow** (`app/api.py`, `app/job_manager.py`, `app/db.py`): FastAPI upload + job endpoints enqueue background runs with `ThreadPoolExecutor`, persist job state in SQLite (`app_data/jobs.db`), and call the same `run_pipeline()` used by CLI.

Pipeline modules in `pipelines/` are file-contract based. Each stage reads/writes JSON/text artifacts under a run output directory, and later stages (plus API progress views) depend on those exact artifact names.

## Key conventions specific to this codebase

- **Artifact contract is strict:** `job_manager.job_artifacts()` and progress logic expect paths like `detections.json`, `segments.json`, `alerts.json`, `pose_fatigue.json`, `report.txt`, `transcripts/transcripts_index.json`, and `qwen/whole_video_summary.md`. Renaming or relocating these breaks UI/API readiness and progress stages.
- **Significant-event filtering is a cross-cutting rule:** `pipelines.utils.get_significant_event_labels()` defaults to `cell phone,phone,laptop`. Both segmentation (`CLIP_SIGNIFICANT_EVENTS_ONLY`) and reporting (`REPORT_SIGNIFICANT_EVENTS_ONLY`) apply this significance logic, so changes to labels/behavior should be coordinated across both outputs.
- **Segmentation behavior is env-driven and safety-prioritized:** `pipelines.segmenter.build_segments()` merges detector + pose/fatigue events, supports per-label occurrence clipping, optional overlap merging, padding, and keeps configured high-priority events (default `fatigue_microsleep,fatigue_asleep`) separated for dedicated clips.
- **Graceful fallback behavior is intentional:** detection falls back to simulated events if YOLO is unavailable, transcriber writes placeholder transcripts if Whisper is unavailable, and Qwen summarization falls back to local markdown when remote credentials are not configured.
- **Web job storage layout is stable:** uploads are moved to `app_data/uploads/<job_id>/input.mp4`; run outputs go to `app_data/runs/<job_id>/...`; do not bypass `safe_job_file_path`/`safe_uploaded_video_path` checks when adding download/stream endpoints.
