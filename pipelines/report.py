import json
from pathlib import Path


def generate_report(
    segments_path: str,
    transcripts_index_path: str,
    report_path: str,
    pose_fatigue_path: str = None,
    detections_path: str = None,
    alerts_path: str = None,
) -> str:
    segs = json.loads(Path(segments_path).read_text(encoding="utf-8")) if segments_path else {"segments": []}
    index = json.loads(Path(transcripts_index_path).read_text(encoding="utf-8")) if transcripts_index_path else []
    fatigue = json.loads(Path(pose_fatigue_path).read_text(encoding="utf-8")) if pose_fatigue_path and Path(pose_fatigue_path).exists() else []
    detections = json.loads(Path(detections_path).read_text(encoding="utf-8")) if detections_path and Path(detections_path).exists() else {"video_frames": 0, "detections": []}
    alerts_payload = json.loads(Path(alerts_path).read_text(encoding="utf-8")) if alerts_path and Path(alerts_path).exists() else {"alerts": [], "summary": {}}
    lines = []
    lines.append("Video Intelligence Report (MVP)")
    lines.append("")

    total_frames = int(detections.get("video_frames", 0))
    total_detections = len(detections.get("detections", []) or [])
    lines.append("Overview")
    lines.append(f"- Total frames sampled: {total_frames}")
    lines.append(f"- Total detections: {total_detections}")
    lines.append(f"- Total segments: {len(segs.get('segments', []) or [])}")
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

    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report generated at {report_path}")
    return str(out)
