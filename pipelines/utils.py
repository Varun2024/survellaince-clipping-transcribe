import json
from pathlib import Path
from typing import Any


def ensure_dir(path: str) -> Path:
    p = Path(path)
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
