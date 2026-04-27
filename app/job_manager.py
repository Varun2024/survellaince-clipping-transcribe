import os
import shutil
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.db import create_job, get_job, init_db, list_jobs, update_job_status
from main import load_env_defaults, run_pipeline
from pipelines.utils import read_json


DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "app_data")).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
RUNS_DIR = DATA_DIR / "runs"
DB_PATH = DATA_DIR / "jobs.db"

_executor: Optional[ThreadPoolExecutor] = None
_submit_lock = threading.Lock()
_runtime_checks: Dict[str, Any] = {"ffmpeg_available": False, "ffmpeg_bin": ""}
_logger = logging.getLogger("railway_app")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_runtime() -> None:
    global DATA_DIR, UPLOADS_DIR, RUNS_DIR, DB_PATH, _executor
    load_env_defaults()
    DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "app_data")).resolve()
    UPLOADS_DIR = DATA_DIR / "uploads"
    RUNS_DIR = DATA_DIR / "runs"
    DB_PATH = DATA_DIR / "jobs.db"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)
    logs_dir = DATA_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if not _logger.handlers:
        log_path = logs_dir / "app.log"
        handler = logging.FileHandler(str(log_path), encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        _logger.setLevel(logging.INFO)
        _logger.addHandler(handler)
    ffmpeg_bin = os.environ.get("FFMPEG_BIN", "ffmpeg")
    ffmpeg_path = shutil.which(ffmpeg_bin)
    _runtime_checks["ffmpeg_bin"] = ffmpeg_bin
    _runtime_checks["ffmpeg_available"] = bool(ffmpeg_path)
    _logger.info("Runtime initialized: data_dir=%s ffmpeg_available=%s", str(DATA_DIR), _runtime_checks["ffmpeg_available"])
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=max(1, int(os.environ.get("APP_MAX_WORKERS", "1"))))


def create_and_queue_job(upload_path: Path, original_filename: str) -> Dict[str, Any]:
    init_runtime()
    job_id = uuid4().hex
    job_upload_dir = UPLOADS_DIR / job_id
    job_output_dir = RUNS_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    final_upload_path = job_upload_dir / "input.mp4"
    shutil.move(str(upload_path), str(final_upload_path))

    created_at = _utcnow_iso()
    create_job(
        DB_PATH,
        job_id=job_id,
        filename=original_filename,
        upload_path=str(final_upload_path),
        output_dir=str(job_output_dir),
        created_at=created_at,
    )

    with _submit_lock:
        if _executor is None:
            raise RuntimeError("Job executor is not initialized")
        _executor.submit(_run_job, job_id, final_upload_path, job_output_dir)
    job = get_job(DB_PATH, job_id)
    return job or {}


def _run_job(job_id: str, input_path: Path, output_dir: Path) -> None:
    started_at = _utcnow_iso()
    update_job_status(DB_PATH, job_id=job_id, status="running", started_at=started_at, error=None)
    _logger.info("Job started: id=%s input=%s output=%s", job_id, str(input_path), str(output_dir))
    try:
        run_pipeline(str(input_path), str(output_dir))
    except Exception as exc:
        _logger.exception("Job failed: id=%s error=%s", job_id, str(exc))
        update_job_status(
            DB_PATH,
            job_id=job_id,
            status="failed",
            finished_at=_utcnow_iso(),
            error=str(exc),
        )
        return
    _logger.info("Job completed: id=%s", job_id)
    update_job_status(
        DB_PATH,
        job_id=job_id,
        status="completed",
        finished_at=_utcnow_iso(),
        error=None,
    )


def get_job_record(job_id: str) -> Optional[Dict[str, Any]]:
    init_runtime()
    return get_job(DB_PATH, job_id)


def list_job_records(limit: int = 100) -> List[Dict[str, Any]]:
    init_runtime()
    return list_jobs(DB_PATH, limit=limit)


def _safe_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _detection_summary(detections_path: Path) -> Dict[str, Any]:
    payload = read_json(str(detections_path), {"video_frames": 0, "detections": []}) or {}
    detections = payload.get("detections", []) or []
    label_counts: Dict[str, int] = {}
    for d in detections:
        lbl = str(d.get("label", "unknown"))
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
    return {
        "video_frames": int(payload.get("video_frames", 0)),
        "detections_count": len(detections),
        "label_counts": dict(sorted(label_counts.items(), key=lambda x: x[1], reverse=True)),
    }


def _fatigue_summary(fatigue_path: Path) -> Dict[str, int]:
    rows = read_json(str(fatigue_path), []) or []
    return {
        "frames_analyzed": len(rows),
        "blink_frames": sum(1 for r in rows if bool(r.get("blink"))),
        "microsleep_frames": sum(1 for r in rows if bool(r.get("microsleep"))),
        "yawn_frames": sum(1 for r in rows if bool(r.get("yawn"))),
        "head_nod_frames": sum(1 for r in rows if bool(r.get("head_nod"))),
        "slouch_frames": sum(1 for r in rows if bool(r.get("slouch"))),
    }


def _list_relative_files(base_dir: Path, pattern: str) -> List[str]:
    if not base_dir.exists():
        return []
    return sorted([str(p.relative_to(base_dir)) for p in base_dir.glob(pattern) if p.is_file()])


def _compute_progress(exists: Dict[str, bool], job_status: str) -> Dict[str, Any]:
    stages = [
        {"key": "queued", "label": "Job queued", "done": True},
        {"key": "detect", "label": "Frame ingest + detection", "done": bool(exists.get("detections_json"))},
        {"key": "segment", "label": "Fatigue + segmentation", "done": bool(exists.get("pose_fatigue_json")) and bool(exists.get("segments_json"))},
        {"key": "clips_alerts", "label": "Clips + alerts", "done": bool(exists.get("alerts_json"))},
        {"key": "report", "label": "Transcripts + report", "done": bool(exists.get("transcripts_index_json")) and bool(exists.get("report_txt"))},
        {"key": "summary", "label": "Narrative summaries", "done": bool(exists.get("qwen_whole_summary_md"))},
    ]
    if str(job_status).lower() == "completed":
        for stage in stages:
            stage["done"] = True
    done_count = sum(1 for s in stages if s["done"])
    percent = int(round((done_count / max(1, len(stages))) * 100))
    if str(job_status).lower() == "failed":
        state = "failed"
    elif str(job_status).lower() == "completed":
        state = "completed"
    elif done_count <= 1:
        state = "queued"
    else:
        state = "running"
    return {"percent": percent, "state": state, "stages": stages}


def job_artifacts(job_id: str) -> Dict[str, Any]:
    job = get_job_record(job_id)
    if not job:
        return {}

    output_dir = Path(str(job.get("output_dir", "")))
    if not output_dir.exists():
        return {"job_id": job_id, "ready": False, "files": {}, "data": {}}

    files = {
        "detections_json": "detections.json",
        "segments_json": "segments.json",
        "alerts_json": "alerts.json",
        "pose_fatigue_json": "pose_fatigue.json",
        "report_txt": "report.txt",
        "transcripts_index_json": "transcripts/transcripts_index.json",
        "qwen_clip_summaries_md": "qwen/clip_summaries.md",
        "qwen_whole_summary_md": "qwen/whole_video_summary.md",
    }

    exists = {k: (output_dir / v).exists() for k, v in files.items()}
    data: Dict[str, Any] = {
        "detections_summary": _detection_summary(output_dir / "detections.json"),
        "fatigue_summary": _fatigue_summary(output_dir / "pose_fatigue.json"),
        "segments": read_json(str(output_dir / "segments.json"), {"segments": []}).get("segments", []),
        "alerts": read_json(str(output_dir / "alerts.json"), {"alerts": [], "segment_alerts": [], "summary": {}}),
        "transcripts_index": read_json(str(output_dir / "transcripts" / "transcripts_index.json"), []),
        "qwen_clip_summaries_md": _safe_text(output_dir / "qwen" / "clip_summaries.md"),
        "qwen_whole_summary_md": _safe_text(output_dir / "qwen" / "whole_video_summary.md"),
    }

    transcript_previews: List[Dict[str, str]] = []
    for row in data["transcripts_index"]:
        transcript_path = Path(str(row.get("transcript", "")))
        preview = _safe_text(transcript_path)[:1000]
        transcript_previews.append(
            {
                "clip": str(row.get("clip", "")),
                "transcript": str(row.get("transcript", "")),
                "preview": preview,
            }
        )
    data["transcript_previews"] = transcript_previews
    data["clips"] = _list_relative_files(output_dir / "clips", "*.mp4")
    progress = _compute_progress(exists, str(job.get("status", "")))

    return {
        "job_id": job_id,
        "ready": True,
        "files": files,
        "exists": exists,
        "progress": progress,
        "data": data,
    }


def safe_job_file_path(job_id: str, relative_path: str) -> Optional[Path]:
    job = get_job_record(job_id)
    if not job:
        return None
    output_dir = Path(str(job.get("output_dir", ""))).resolve()
    candidate = (output_dir / relative_path).resolve()
    try:
        if os.path.commonpath([str(output_dir), str(candidate)]) != str(output_dir):
            return None
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def safe_uploaded_video_path(job_id: str) -> Optional[Path]:
    job = get_job_record(job_id)
    if not job:
        return None
    upload_path = Path(str(job.get("upload_path", ""))).resolve()
    uploads_root = (UPLOADS_DIR / job_id).resolve()
    try:
        if os.path.commonpath([str(uploads_root), str(upload_path)]) != str(uploads_root):
            return None
    except ValueError:
        return None
    if not upload_path.exists() or not upload_path.is_file():
        return None
    return upload_path


def job_to_json(job: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(job)
    for key in ("upload_path", "output_dir"):
        output[key] = str(output.get(key, ""))
    return output


def runtime_status() -> Dict[str, Any]:
    init_runtime()
    return dict(_runtime_checks)
