import json
from pathlib import Path
from typing import List, Dict, Any


def load_detections(detections_path: str) -> Dict[str, Any]:
    with open(detections_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_segments(detections_path: str, fps: int = 1, segment_gap: int = 5, min_segment_frames: int = 5) -> str:
    data = load_detections(detections_path)
    detections = data.get("detections", [])
    # Create a simple per-frame map
    frame_to_has_detection = {d["frame"]: d for d in detections if d.get("frame")}
    frames = sorted(frame_to_has_detection.keys())

    segments: List[Dict[str, Any]] = []
    current = None
    for f in frames:
        detected = f in frame_to_has_detection
        if detected:
            if current is None:
                start = int(f.split("frame_")[-1].split(".jpg")[0])
                current = {"start_frame": start, "end_frame": start}
            else:
                end = int(f.split("frame_")[-1].split(".jpg")[0])
                current["end_frame"] = end
        else:
            if current is not None:
                length = current["end_frame"] - current["start_frame"] + 1
                if length >= min_segment_frames:
                    segments.append(current)
                current = None

    # Finalize last segment
    if current is not None:
        length = current["end_frame"] - current["start_frame"] + 1
        if length >= min_segment_frames:
            segments.append(current)

    # Save segments
    output = {
        "video": Path(detections_path).parent.name,
        "fps": fps,
        "segments": segments,
    }
    segments_path = str(Path(detections_path).parent / "segments.json")
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Segments written to {segments_path}")
    return segments_path
