import os
from pathlib import Path
from typing import Dict, Any, List

from pipelines.utils import read_json, get_significant_event_labels, is_significant_event_label


def _format_seconds(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if seconds < 0:
        return "n/a"
    minutes = int(seconds // 60)
    remaining = seconds - (minutes * 60)
    return f"{minutes:02d}:{remaining:05.2f}"


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = int(round((len(vals) - 1) * q))
    return float(vals[max(0, min(idx, len(vals) - 1))])


def generate_report(
    segments_path: str,
    transcripts_index_path: str,
    report_path: str,
    pose_fatigue_path: str = None,
    detections_path: str = None,
    alerts_path: str = None,
) -> str:
    segs = read_json(segments_path, {"segments": []}) if segments_path else {"segments": []}
    index = read_json(transcripts_index_path, []) if transcripts_index_path else []
    fatigue = read_json(pose_fatigue_path, []) if pose_fatigue_path else []
    detections = read_json(detections_path, {"video_frames": 0, "detections": []}) if detections_path else {"video_frames": 0, "detections": []}
    alerts_payload = read_json(alerts_path, {"alerts": [], "summary": {}}) if alerts_path else {"alerts": [], "summary": {}}
    report_significant_only = os.environ.get("REPORT_SIGNIFICANT_EVENTS_ONLY", "1") == "1"
    significant_labels = get_significant_event_labels()
    lines = []
    lines.append("Video Intelligence Report (MVP)")
    lines.append("")

    total_frames = int(detections.get("video_frames", 0))
    detection_rows = detections.get("detections", []) or []
    filtered_detections = detection_rows
    if report_significant_only:
        filtered_detections = [
            d
            for d in detection_rows
            if is_significant_event_label(str(d.get("label", "")), significant_labels)
        ]

    total_detections = len(filtered_detections)
    confs = [float(d.get("score", 0.0)) for d in filtered_detections if d.get("score") is not None]

    label_counts: Dict[str, int] = {}
    for d in filtered_detections:
        lbl = str(d.get("label", "unknown"))
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
    top_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    lines.append("Overview")
    lines.append(f"- Total frames sampled: {total_frames}")
    if report_significant_only:
        lines.append(f"- Total significant detections: {total_detections}")
        lines.append(f"- Significant labels used: {', '.join(sorted(list(significant_labels)))}")
    else:
        lines.append(f"- Total detections: {total_detections}")
    lines.append(f"- Total segments: {len(segs.get('segments', []) or [])}")
    lines.append("")

    if confs:
        lines.append("Detection Confidence (Significant Events)")
        lines.append(f"- Min/Avg/Max: {min(confs):.3f}/{(sum(confs)/len(confs)):.3f}/{max(confs):.3f}")
        lines.append(f"- P50/P90/P95: {_percentile(confs, 0.50):.3f}/{_percentile(confs, 0.90):.3f}/{_percentile(confs, 0.95):.3f}")
        if top_labels:
            lines.append("- Top labels: " + ", ".join(f"{k}({v})" for k, v in top_labels))
        lines.append("")

    if fatigue:
        fatigue_frames = len(fatigue)
        blink_frames = sum(1 for r in fatigue if bool(r.get("blink")))
        microsleep_frames = sum(1 for r in fatigue if bool(r.get("microsleep")))
        yawn_frames = sum(1 for r in fatigue if bool(r.get("yawn")))
        head_nod_frames = sum(1 for r in fatigue if bool(r.get("head_nod")))
        slouch_frames = sum(1 for r in fatigue if bool(r.get("slouch")))

        lines.append("Fatigue Metrics")
        lines.append(f"- Blink frames: {blink_frames}/{fatigue_frames}")
        lines.append(f"- Microsleep frames: {microsleep_frames}/{fatigue_frames}")
        lines.append(f"- Yawn frames: {yawn_frames}/{fatigue_frames}")
        lines.append(f"- Head nod frames: {head_nod_frames}/{fatigue_frames}")
        lines.append(f"- Slouch frames: {slouch_frames}/{fatigue_frames}")
        lines.append("")

    for i, seg in enumerate(segs.get("segments", []) or [], start=1):
        start = seg.get("start_frame", 0)
        end = seg.get("end_frame", 0)
        start_time = _format_seconds(seg.get("start_time_sec"))
        end_time = _format_seconds(seg.get("end_time_sec"))
        event_label = str(seg.get("event_label", "")).strip()
        event_severity = str(seg.get("event_severity", "low")).upper()
        label_text = f" | label {event_label}" if event_label else ""
        lines.append(f"Segment {i}: frames {start}-{end} | time {start_time} -> {end_time}{label_text} | severity {event_severity}")
        # Find related transcript path if available
        clip = index[i-1] if len(index) >= i else None
        if clip:
            lines.append(f"  Transcript: {clip.get('transcript', '')}")

    anomaly_counts: Dict[str, int] = {}
    for seg in segs.get("segments", []) or []:
        lbl = str(seg.get("event_label", "")).strip().lower()
        if not lbl:
            continue
        anomaly_counts[lbl] = anomaly_counts.get(lbl, 0) + 1
    if anomaly_counts:
        lines.append("")
        lines.append("Behavior Anomaly Events")
        for lbl, count in sorted(anomaly_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {lbl}: {count} occurrence(s)")

    alerts = alerts_payload.get("alerts", []) or []
    if alerts:
        lines.append("")
        lines.append("Alerts")
        for a in alerts:
            lines.append(f"- [{a.get('severity', 'info').upper()}] {a.get('message', '')}")

    segment_alerts = alerts_payload.get("segment_alerts", []) or []
    if segment_alerts:
        lines.append("")
        lines.append("Segment Risk Summary")
        for seg in segment_alerts:
            sid = seg.get("segment_id", 0)
            severity = str(seg.get("severity", "low")).upper()
            score = float(seg.get("fatigue_score", 0.0))
            lines.append(
                f"- Segment {sid} [{severity}] fatigue_score={score:.3f}, high_risk_hits={seg.get('high_risk_hits', 0)}, microsleep={seg.get('microsleep_frames', 0)}, yawn={seg.get('yawn_frames', 0)}"
            )

    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report generated at {report_path}")
    return str(out)
