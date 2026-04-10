import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set

from pipelines.utils import (
    read_json,
    write_json,
    frame_name_to_number,
    frame_range_to_times,
    get_significant_event_labels,
    is_significant_event_label,
)


def load_detections(detections_path: str) -> Dict[str, Any]:
    return read_json(detections_path, {"detections": []})


def _parse_event_labels(value: str) -> Tuple[set, bool]:
    if not value:
        return set(), True
    cleaned = [v.strip().lower() for v in value.split(",") if v.strip()]
    if not cleaned:
        return set(), True
    if any(v in {"*", "all"} for v in cleaned):
        return set(), True
    return set(cleaned), False


def _parse_significant_fatigue_flags(value: str) -> Set[str]:
    defaults = "microsleep,asleep,slouch,head_nod,yawn"
    raw = value if value is not None else defaults
    cleaned = {v.strip().lower() for v in str(raw).split(",") if v.strip()}
    return cleaned if cleaned else {"microsleep", "asleep", "slouch", "head_nod", "yawn"}


def _fatigue_events_from_rows(
    fatigue_rows: List[Dict[str, Any]],
    enabled_flags: Set[str],
    include_all_events: bool,
    event_labels: Set[str],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for row in fatigue_rows:
        frame = str(row.get("frame", ""))
        if not frame:
            continue
        for flag in enabled_flags:
            source_flag = "microsleep" if flag == "asleep" else flag
            if not bool(row.get(source_flag)):
                continue
            label = f"fatigue_{flag}"
            if not include_all_events and label not in event_labels:
                continue
            events.append(
                {
                    "frame": frame,
                    "label": label,
                    "score": 1.0,
                    "source": "pose_fatigue",
                }
            )
    return events


def _parse_high_priority_event_labels(value: str) -> Set[str]:
    defaults = "fatigue_microsleep,fatigue_asleep"
    raw = value if value is not None else defaults
    labels = {v.strip().lower() for v in str(raw).split(",") if v.strip()}
    return labels if labels else {"fatigue_microsleep", "fatigue_asleep"}


def _event_priority(label: str, high_priority_labels: Set[str]) -> int:
    normalized = str(label).strip().lower()
    if not normalized:
        return 1
    if normalized in high_priority_labels:
        return 3
    if normalized.startswith("fatigue_"):
        return 2
    return 1


def _event_severity(priority: int) -> str:
    if priority >= 3:
        return "high"
    if priority == 2:
        return "medium"
    return "low"


def build_segments(
    detections_path: str,
    fps: int = 1,
    segment_gap: int = 5,
    min_segment_frames: int = 5,
    fatigue_path: str = None,
) -> str:
    data = load_detections(detections_path)
    detections = data.get("detections", [])
    event_labels, include_all_events = _parse_event_labels(os.environ.get("EVENT_LABELS", "*"))
    min_event_score = float(os.environ.get("MIN_EVENT_SCORE", "0.0"))
    event_padding_frames = int(os.environ.get("EVENT_PADDING_FRAMES", "0"))
    min_event_segment_frames = int(os.environ.get("MIN_EVENT_SEGMENT_FRAMES", "1"))
    max_segment_frames = int(os.environ.get("MAX_SEGMENT_FRAMES", "0"))
    occurrence_by_label = os.environ.get("EVENT_OCCURRENCE_BY_LABEL", "1") == "1"
    merge_padded_segments = os.environ.get("EVENT_MERGE_PADDED_OVERLAPS", "0") == "1"
    significant_only_for_clips = os.environ.get("CLIP_SIGNIFICANT_EVENTS_ONLY", "1") == "1"
    use_pose_for_significant_events = os.environ.get("USE_POSE_FOR_SIGNIFICANT_EVENTS", "1") == "1"
    significant_fatigue_flags = _parse_significant_fatigue_flags(os.environ.get("SIGNIFICANT_FATIGUE_FLAGS", ""))
    high_priority_event_labels = _parse_high_priority_event_labels(os.environ.get("HIGH_PRIORITY_EVENT_LABELS", ""))
    significant_labels = get_significant_event_labels()
    total_frames = int(data.get("video_frames", 0))
    effective_min_segment_frames = min_segment_frames if not include_all_events else min_event_segment_frames

    def append_segment(start_frame: int, end_frame: int, event_label: str = "") -> None:
        if end_frame < start_frame:
            return
        length = end_frame - start_frame + 1
        if length < effective_min_segment_frames:
            return
        start_time_sec, end_time_sec = frame_range_to_times(start_frame, end_frame, fps)
        priority = _event_priority(event_label, high_priority_event_labels)
        segment_payload = {
            "start_frame": start_frame,
            "end_frame": end_frame,
            "start_time_sec": round(start_time_sec, 3),
            "end_time_sec": round(end_time_sec, 3),
            "event_label": event_label,
            "event_priority": priority,
            "event_severity": _event_severity(priority),
        }
        if max_segment_frames <= 0 or length <= max_segment_frames:
            segments.append(segment_payload)
            return

        chunk_start = start_frame
        while chunk_start <= end_frame:
            chunk_end = min(chunk_start + max_segment_frames - 1, end_frame)
            if chunk_end - chunk_start + 1 >= min_segment_frames:
                chunk_start_time_sec, chunk_end_time_sec = frame_range_to_times(chunk_start, chunk_end, fps)
                segments.append(
                    {
                        "start_frame": chunk_start,
                        "end_frame": chunk_end,
                        "start_time_sec": round(chunk_start_time_sec, 3),
                        "end_time_sec": round(chunk_end_time_sec, 3),
                        "event_label": event_label,
                        "event_priority": priority,
                        "event_severity": _event_severity(priority),
                    }
                )
            chunk_start = chunk_end + 1
    # Create a simple per-frame map
    event_detections = []
    for det in detections:
        frame = det.get("frame")
        if not frame:
            continue
        label = str(det.get("label", "")).lower()
        score = float(det.get("score", 0.0))
        if not include_all_events and label not in event_labels:
            continue
        if score < min_event_score:
            continue
        if significant_only_for_clips and not is_significant_event_label(label, significant_labels):
            continue
        event_detections.append(det)

    fatigue_event_detections: List[Dict[str, Any]] = []
    if use_pose_for_significant_events and fatigue_path:
        fatigue_rows = read_json(fatigue_path, []) or []
        fatigue_event_detections = _fatigue_events_from_rows(
            fatigue_rows=fatigue_rows,
            enabled_flags=significant_fatigue_flags,
            include_all_events=include_all_events,
            event_labels=event_labels,
        )

    combined_event_detections = event_detections + fatigue_event_detections

    segments: List[Dict[str, Any]] = []
    if not combined_event_detections:
        # No detections
        segments_path = str(Path(detections_path).parent / "segments.json")
        output = {"video": Path(detections_path).parent.name, "fps": fps, "segments": []}
        write_json(segments_path, output)
        print(f"Segments written to {segments_path}")
        return segments_path

    def append_runs(frame_numbers: List[int], label: str = "") -> None:
        if not frame_numbers:
            return
        current_segment_start = frame_numbers[0]
        current_segment_end = frame_numbers[0]
        for i in range(1, len(frame_numbers)):
            frame_gap = frame_numbers[i] - frame_numbers[i - 1]
            if frame_gap <= segment_gap:
                current_segment_end = frame_numbers[i]
            else:
                append_segment(current_segment_start, current_segment_end, event_label=label)
                current_segment_start = frame_numbers[i]
                current_segment_end = frame_numbers[i]
        append_segment(current_segment_start, current_segment_end, event_label=label)

    if occurrence_by_label:
        label_to_frames: Dict[str, set] = {}
        for det in combined_event_detections:
            label = str(det.get("label", "")).lower()
            frame_num = frame_name_to_number(str(det.get("frame", "")))
            if frame_num <= 0:
                continue
            label_to_frames.setdefault(label, set()).add(frame_num)
        for label in sorted(label_to_frames.keys()):
            append_runs(sorted(label_to_frames[label]), label=label)
    else:
        frame_numbers = sorted(
            {
                frame_name_to_number(str(det.get("frame", "")))
                for det in combined_event_detections
                if frame_name_to_number(str(det.get("frame", ""))) > 0
            }
        )
        append_runs(frame_numbers)

    segments.sort(key=lambda s: (int(s.get("start_frame", 0)), -int(s.get("event_priority", 1)), str(s.get("event_label", ""))))
    for idx, seg in enumerate(segments, start=1):
        seg["event_id"] = idx

    if event_padding_frames > 0 and segments:
        padded = []
        for seg in segments:
            s = max(1, int(seg["start_frame"]) - event_padding_frames)
            e = int(seg["end_frame"]) + event_padding_frames
            if total_frames > 0:
                e = min(total_frames, e)
            start_time_sec, end_time_sec = frame_range_to_times(s, e, fps)
            padded.append(
                {
                    "start_frame": s,
                    "end_frame": e,
                    "start_time_sec": round(start_time_sec, 3),
                    "end_time_sec": round(end_time_sec, 3),
                    "event_label": str(seg.get("event_label", "")),
                    "event_id": int(seg.get("event_id", 0)),
                    "event_priority": int(seg.get("event_priority", 1)),
                    "event_severity": str(seg.get("event_severity", "low")),
                }
            )
        if merge_padded_segments:
            padded.sort(key=lambda x: x["start_frame"])
            merged = [padded[0]]
            for seg in padded[1:]:
                last = merged[-1]
                should_keep_separate = int(last.get("event_priority", 1)) >= 3 or int(seg.get("event_priority", 1)) >= 3
                if seg["start_frame"] <= last["end_frame"] + 1 and not should_keep_separate:
                    last["end_frame"] = max(last["end_frame"], seg["end_frame"])
                    _, last_end_time_sec = frame_range_to_times(last["start_frame"], last["end_frame"], fps)
                    last["end_time_sec"] = round(last_end_time_sec, 3)
                    if not last.get("event_label"):
                        last["event_label"] = str(seg.get("event_label", ""))
                    if int(seg.get("event_priority", 1)) > int(last.get("event_priority", 1)):
                        last["event_priority"] = int(seg.get("event_priority", 1))
                        last["event_severity"] = str(seg.get("event_severity", "low"))
                else:
                    merged.append(seg)
            segments = merged
        else:
            segments = padded

    segments.sort(key=lambda s: (int(s.get("start_frame", 0)), -int(s.get("event_priority", 1)), str(s.get("event_label", ""))))
    for idx, seg in enumerate(segments, start=1):
        seg["event_id"] = idx

    # Save segments
    output = {
        "video": Path(detections_path).parent.name,
        "fps": fps,
        "segments": segments,
        "meta": {
            "event_labels": ["*"] if include_all_events else sorted(list(event_labels)),
            "min_event_score": min_event_score,
            "event_detections": len(event_detections),
            "fatigue_event_detections": len(fatigue_event_detections),
            "use_pose_for_significant_events": use_pose_for_significant_events,
            "significant_fatigue_flags": sorted(list(significant_fatigue_flags)),
            "high_priority_event_labels": sorted(list(high_priority_event_labels)),
            "event_padding_frames": event_padding_frames,
            "min_event_segment_frames": min_event_segment_frames,
            "occurrence_by_label": occurrence_by_label,
            "merge_padded_overlaps": merge_padded_segments,
            "significant_only_for_clips": significant_only_for_clips,
            "significant_event_labels": sorted(list(significant_labels)),
        },
    }
    segments_path = str(Path(detections_path).parent / "segments.json")
    write_json(segments_path, output)
    print(f"Segments written to {segments_path}")
    return segments_path
