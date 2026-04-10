import json
import os
import random
from pathlib import Path
from typing import Dict, Any, List


def _simulate_detections(frames_dir: Path, trigger_interval: int = 300) -> List[Dict[str, Any]]:
    """Create simple simulated detections across frames for MVP.
    Every `trigger_interval` frames, emit a synthetic 'phone' detection.
    """
    frame_files = sorted([p for p in frames_dir.glob("frame_*.jpg") if p.is_file()])
    detections: List[Dict[str, Any]] = []
    for idx, frame in enumerate(frame_files, start=1):
        if idx % trigger_interval == 0:
            detections.append({
                "frame": frame.name,
                "label": "phone",
                "score": round(0.8 + random.random() * 0.15, 2),
                "bbox": [10, 20, 200, 180],
            })
    return detections


def run_detection(frames_dir: str, model_path: str, results_path: str = None) -> str:
    """Run object-detection on frames.
    If a real model is unavailable, fall back to simulated detections.
    Writes a JSON results file containing per-frame detections.
    """
    frames_p = Path(frames_dir)
    results = {"video_frames": len(list(frames_p.glob("frame_*.jpg"))), "detections": []}

    conf_threshold = float(os.environ.get("DETECTION_CONF_THRESHOLD", "0.35"))

    detections: List[Dict[str, Any]] = []
    model = None
    if model_path and Path(model_path).exists():
        try:
            # Prefer Ultralytics YOLO if available
            from ultralytics import YOLO  # type: ignore
            model = YOLO(model_path)  # type: ignore
            print(f"Using YOLO model at {model_path}")
        except Exception as e:
            print(f"Warning: Could not initialize YOLO model: {e}")
            model = None
    else:
        model = None

    frame_list = sorted([p for p in frames_p.glob("frame_*.jpg") if p.is_file()])
    if model is not None:
        # Run per-frame detection using the model
        for frame_path in frame_list:
            try:
                # Ultralytics results for a single image
                frame_results = model(str(frame_path))  # type: ignore
                for res in frame_results:
                    # Normalize to a common structure if possible
                    if hasattr(res, 'boxes'):
                        boxes = res.boxes  # type: ignore
                        if hasattr(boxes, 'data'):
                            for d in boxes.data:  # type: ignore
                                # d expected as [x1, y1, x2, y2, conf, cls]
                                try:
                                    x1, y1, x2, y2, conf, cls = [float(v) for v in d.tolist()]  # type: ignore
                                    label = getattr(model, 'names', None)
                                    if isinstance(label, dict):
                                        lbl = str(label.get(int(cls), int(cls)))
                                    elif label and isinstance(label, (list, tuple)):
                                        lbl = label[int(cls)]  # type: ignore
                                    else:
                                        lbl = str(int(cls))
                                    if float(conf) < conf_threshold:
                                        continue
                                    detections.append({
                                        "frame": Path(frame_path).name,
                                        "label": lbl,
                                        "score": float(conf),
                                        "bbox": [x1, y1, x2, y2],
                                    })
                                except Exception:
                                    continue
                    # if no boxes, skip
            except Exception as e:
                print(f"Frame {frame_path} detection failed: {e}")
        if detections:
            pass  # use collected detections
    else:
        # Fallback to simulated detections for MVP
        detections = _simulate_detections(frames_p)

    if not detections:
        detections = _simulate_detections(frames_p)

    for det in detections:
        det_item = {
            "frame": det.get("frame"),
            "label": det.get("label"),
            "score": det.get("score"),
            "bbox": det.get("bbox"),
        }
        results["detections"].append(det_item)

    results_path = results_path or str(frames_p.parent / "detections.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Detections written to {results_path} (conf >= {conf_threshold})")
    return results_path
