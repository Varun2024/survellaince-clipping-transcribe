import json
import os
import shutil
from pathlib import Path
from typing import Any, Set


DEFAULT_SIGNIFICANT_EVENT_LABELS = (
    "cell phone",
    "phone",
    "laptop",
)


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def clear_dir(path: str) -> Path:
    p = Path(path)
    if p.exists():
        for child in p.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str, payload: Any) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(p)


def frame_name_to_number(frame_name: str) -> int:
    if "frame_" not in frame_name:
        return -1
    try:
        return int(frame_name.split("frame_")[-1].split(".")[0])
    except ValueError:
        return -1


def frame_number_to_seconds(frame_number: int, fps: float) -> float:
    if frame_number <= 0 or fps <= 0:
        return 0.0
    return max(0.0, (frame_number - 1) / float(fps))


def frame_range_to_times(start_frame: int, end_frame: int, fps: float) -> tuple:
    if start_frame <= 0 or end_frame < start_frame or fps <= 0:
        return 0.0, 0.0
    start_time = frame_number_to_seconds(start_frame, fps)
    end_time = max(start_time, end_frame / float(fps))
    return start_time, end_time


def parse_csv_labels(value: str) -> Set[str]:
    return {v.strip().lower() for v in str(value).split(",") if v and v.strip()}


def get_significant_event_labels() -> Set[str]:
    configured = os.environ.get("SIGNIFICANT_EVENT_LABELS", "")
    if configured.strip():
        return parse_csv_labels(configured)
    return set(DEFAULT_SIGNIFICANT_EVENT_LABELS)


def is_significant_event_label(label: str, significant_labels: Set[str]) -> bool:
    normalized = str(label).strip().lower()
    if not normalized:
        return False
    if normalized in significant_labels:
        return True
    return "phone" in significant_labels and "phone" in normalized
