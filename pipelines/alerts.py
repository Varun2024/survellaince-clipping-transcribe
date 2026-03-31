import os
from typing import Dict, Any, List

from pipelines.utils import read_json, write_json, frame_name_to_number

def generate_alerts(
    detections_path: str,
    fatigue_path: str,
    segments_path: str,
    alerts_path: str,
    fps: int = 1,
) -> str:
    detections_data = read_json(detections_path, {"detections": []})
    fatigue_data = read_json(fatigue_path, [])
    segments_data = read_json(segments_path, {"segments": []})

    fatigue_frame_threshold = float(os.environ.get("FATIGUE_ALERT_FRAME_RATIO", "0.15"))
    max_microsleep_events = int(os.environ.get("MAX_MICROSLEEP_EVENTS", "0"))
    max_yawn_events = int(os.environ.get("MAX_YAWN_EVENTS", "1"))
    high_risk_labels = {
        x.strip().lower()
        for x in os.environ.get("HIGH_RISK_LABELS", "cell phone,phone").split(",")
        if x.strip()
    }

    detections = detections_data.get("detections", []) or []
    total_frames = int(detections_data.get("video_frames", 0))

    frame_to_detections: Dict[int, List[Dict[str, Any]]] = {}
    for det in detections:
        frame_name = str(det.get("frame", ""))
        frame_num = frame_name_to_number(frame_name)
        if frame_num <= 0:
            continue
        frame_to_detections.setdefault(frame_num, []).append(det)

    frame_to_fatigue: Dict[int, Dict[str, Any]] = {}
    for row in fatigue_data:
        frame_name = str(row.get("frame", ""))
        frame_num = frame_name_to_number(frame_name)
        if frame_num <= 0:
            continue
        frame_to_fatigue[frame_num] = row

    high_risk_hits = []
    for det in detections:
        label = str(det.get("label", "")).lower()
        if label in high_risk_labels:
            high_risk_hits.append(det)

    microsleep_frames = sum(1 for r in fatigue_data if bool(r.get("microsleep")))
    yawn_frames = sum(1 for r in fatigue_data if bool(r.get("yawn")))
    head_nod_frames = sum(1 for r in fatigue_data if bool(r.get("head_nod")))
    slouch_frames = sum(1 for r in fatigue_data if bool(r.get("slouch")))

    fatigue_total_frames = len(fatigue_data)
    fatigue_ratio = (microsleep_frames + yawn_frames + head_nod_frames) / max(1, fatigue_total_frames)

    alerts: List[Dict[str, Any]] = []
    if high_risk_hits:
        alerts.append(
            {
                "type": "behavior",
                "severity": "medium",
                "message": f"Detected {len(high_risk_hits)} high-risk object hits.",
                "details": {
                    "labels": sorted(list({str(h.get('label')) for h in high_risk_hits})),
                    "count": len(high_risk_hits),
                },
            }
        )

    if microsleep_frames > max_microsleep_events:
        alerts.append(
            {
                "type": "fatigue",
                "severity": "high",
                "message": f"Microsleep indicators detected in {microsleep_frames} frame(s).",
            }
        )

    if yawn_frames > max_yawn_events:
        alerts.append(
            {
                "type": "fatigue",
                "severity": "medium",
                "message": f"Yawn indicators detected in {yawn_frames} frame(s).",
            }
        )

    if fatigue_ratio >= fatigue_frame_threshold:
        alerts.append(
            {
                "type": "fatigue",
                "severity": "high",
                "message": f"Fatigue score ratio {fatigue_ratio:.2f} exceeded threshold {fatigue_frame_threshold:.2f}.",
                "details": {
                    "fatigue_ratio": round(fatigue_ratio, 4),
                    "threshold": fatigue_frame_threshold,
                    "microsleep_frames": microsleep_frames,
                    "yawn_frames": yawn_frames,
                    "head_nod_frames": head_nod_frames,
                    "slouch_frames": slouch_frames,
                },
            }
        )

    segment_alerts: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments_data.get("segments", []) or [], start=1):
        start_frame = int(seg.get("start_frame", 0))
        end_frame = int(seg.get("end_frame", 0))
        if start_frame <= 0 or end_frame < start_frame:
            continue

        det_count = 0
        high_risk_count = 0
        microsleep_count = 0
        yawn_count = 0
        head_nod_count = 0
        slouch_count = 0

        for f in range(start_frame, end_frame + 1):
            frame_dets = frame_to_detections.get(f, [])
            det_count += len(frame_dets)
            high_risk_count += sum(1 for d in frame_dets if str(d.get("label", "")).lower() in high_risk_labels)

            fatigue_row = frame_to_fatigue.get(f, {})
            microsleep_count += int(bool(fatigue_row.get("microsleep")))
            yawn_count += int(bool(fatigue_row.get("yawn")))
            head_nod_count += int(bool(fatigue_row.get("head_nod")))
            slouch_count += int(bool(fatigue_row.get("slouch")))

        seg_len = end_frame - start_frame + 1
        fatigue_score = (microsleep_count + yawn_count + head_nod_count) / max(1, seg_len)
        severity = "low"
        if fatigue_score >= fatigue_frame_threshold or microsleep_count > max_microsleep_events:
            severity = "high"
        elif yawn_count > max_yawn_events or high_risk_count > 0:
            severity = "medium"

        segment_alerts.append(
            {
                "segment_id": idx,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "duration_sec": round(seg_len / max(1, fps), 2),
                "severity": severity,
                "detections": det_count,
                "high_risk_hits": high_risk_count,
                "microsleep_frames": microsleep_count,
                "yawn_frames": yawn_count,
                "head_nod_frames": head_nod_count,
                "slouch_frames": slouch_count,
                "fatigue_score": round(fatigue_score, 4),
            }
        )

    payload = {
        "summary": {
            "video_frames": total_frames,
            "fatigue_frames": fatigue_total_frames,
            "high_risk_hits": len(high_risk_hits),
            "microsleep_frames": microsleep_frames,
            "yawn_frames": yawn_frames,
            "head_nod_frames": head_nod_frames,
            "slouch_frames": slouch_frames,
            "fatigue_ratio": round(fatigue_ratio, 4),
            "segments_analyzed": len(segment_alerts),
        },
        "alerts": alerts,
        "segment_alerts": segment_alerts,
    }

    out = write_json(alerts_path, payload)
    print(f"Alerts written to {alerts_path} ({len(alerts)} alert(s))")
    return str(out)
