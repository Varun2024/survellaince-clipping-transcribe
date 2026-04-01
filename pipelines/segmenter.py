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

    # Extract frame numbers
    frame_numbers = []
    for f in frames:
        frame_num = int(f.split("frame_")[-1].split(".jpg")[0])
        frame_numbers.append(frame_num)

    segments: List[Dict[str, Any]] = []
    if not frame_numbers:
        # No detections
        segments_path = str(Path(detections_path).parent / "segments.json")
        output = {"video": Path(detections_path).parent.name, "fps": fps, "segments": []}
        with open(segments_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Segments written to {segments_path}")
        return segments_path

    # Group frames into segments, breaking on gaps
    current_segment_start = frame_numbers[0]
    current_segment_end = frame_numbers[0]

    for i in range(1, len(frame_numbers)):
        frame_gap = frame_numbers[i] - frame_numbers[i-1]
        if frame_gap <= segment_gap:
            # Continue the segment
            current_segment_end = frame_numbers[i]
        else:
            # Gap detected, finalize current segment and start a new one
            length = current_segment_end - current_segment_start + 1
            if length >= min_segment_frames:
                segments.append({"start_frame": current_segment_start, "end_frame": current_segment_end})
            current_segment_start = frame_numbers[i]
            current_segment_end = frame_numbers[i]

    # Finalize last segment
    length = current_segment_end - current_segment_start + 1
    if length >= min_segment_frames:
        segments.append({"start_frame": current_segment_start, "end_frame": current_segment_end})

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
