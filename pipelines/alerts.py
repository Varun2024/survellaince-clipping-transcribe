import json
import os
from pathlib import Path
from typing import Dict, Any, List


def _load_json(path: str, default: Any) -> Any:
    if not path or not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def generate_alerts(
    detections_path: str,
    fatigue_path: str,
    alerts_path: str,
    fps: int = 1,
) -> str:
    detections_data = _load_json(detections_path, {"detections": []})
    fatigue_data = _load_json(fatigue_path, [])

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
        },
        "alerts": alerts,
    }

    out = Path(alerts_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Alerts written to {alerts_path} ({len(alerts)} alert(s))")
    return str(out)
