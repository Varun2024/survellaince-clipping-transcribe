from pathlib import Path
from typing import Dict, Any, List

from pipelines.utils import read_json


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
    lines = []
    lines.append("Video Intelligence Report (MVP)")
    lines.append("")

    total_frames = int(detections.get("video_frames", 0))
    detection_rows = detections.get("detections", []) or []
    total_detections = len(detection_rows)
    confs = [float(d.get("score", 0.0)) for d in detection_rows if d.get("score") is not None]

    label_counts: Dict[str, int] = {}
    for d in detection_rows:
        lbl = str(d.get("label", "unknown"))
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
    top_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    lines.append("Overview")
    lines.append(f"- Total frames sampled: {total_frames}")
    lines.append(f"- Total detections: {total_detections}")
    lines.append(f"- Total segments: {len(segs.get('segments', []) or [])}")
    lines.append("")

    if confs:
        lines.append("Detection Confidence")
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
        lines.append(f"Segment {i}: frames {start}-{end}")
        # Find related transcript path if available
        clip = index[i-1] if len(index) >= i else None
        if clip:
            lines.append(f"  Transcript: {clip.get('transcript', '')}")

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
