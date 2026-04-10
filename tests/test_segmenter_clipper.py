import json
from pathlib import Path


def test_build_segments_adds_timestamps(tmp_path, monkeypatch):
    detections_path = tmp_path / "detections.json"
    payload = {
        "video_frames": 10,
        "detections": [
            {"frame": "frame_000001.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000002.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000005.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
        ],
    }
    detections_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("CLIP_SIGNIFICANT_EVENTS_ONLY", "0")

    from pipelines.segmenter import build_segments

    segments_path = build_segments(str(detections_path), fps=2, segment_gap=1, min_segment_frames=1)
    data = json.loads(Path(segments_path).read_text(encoding="utf-8"))

    assert data["segments"]
    first_segment = data["segments"][0]
    assert "start_time_sec" in first_segment
    assert "end_time_sec" in first_segment
    assert first_segment["start_time_sec"] == 0.0
    assert first_segment["end_time_sec"] == 1.0


def test_clip_segments_prefers_segment_timestamps(tmp_path, monkeypatch):
    video_path = tmp_path / "input.mp4"
    segments_path = tmp_path / "segments.json"
    clips_dir = tmp_path / "clips"
    video_path.touch()
    segments_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_frame": 3,
                        "end_frame": 7,
                        "start_time_sec": 1.25,
                        "end_time_sec": 3.75,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyCompleted:
        returncode = 0

    def fake_run(cmd, check=True, *args, **kwargs):
        captured["cmd"] = cmd
        out_path = Path(cmd[-1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.touch()
        return DummyCompleted()

    monkeypatch.setattr("subprocess.run", fake_run)

    from pipelines.clipper import clip_segments

    clip_paths = clip_segments(str(video_path), str(segments_path), str(clips_dir), fps=2)

    assert clip_paths
    assert captured["cmd"][captured["cmd"].index("-ss") + 1] == "1.25"
    assert captured["cmd"][captured["cmd"].index("-to") + 1] == "3.75"


def test_build_segments_keeps_each_event_occurrence(tmp_path, monkeypatch):
    detections_path = tmp_path / "detections.json"
    payload = {
        "video_frames": 30,
        "detections": [
            {"frame": "frame_000001.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000002.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000008.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000009.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000015.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000021.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000022.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
        ],
    }
    detections_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("EVENT_LABELS", "cell phone")
    monkeypatch.setenv("EVENT_OCCURRENCE_BY_LABEL", "1")
    monkeypatch.setenv("EVENT_MERGE_PADDED_OVERLAPS", "0")

    from pipelines.segmenter import build_segments

    segments_path = build_segments(str(detections_path), fps=1, segment_gap=1, min_segment_frames=1)
    data = json.loads(Path(segments_path).read_text(encoding="utf-8"))

    assert len(data["segments"]) == 4
    assert all(seg.get("event_label") == "cell phone" for seg in data["segments"])
    assert [seg.get("event_id") for seg in data["segments"]] == [1, 2, 3, 4]


def test_build_segments_filters_generic_events_for_clipping(tmp_path, monkeypatch):
    detections_path = tmp_path / "detections.json"
    payload = {
        "video_frames": 12,
        "detections": [
            {"frame": "frame_000001.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000002.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000005.jpg", "label": "cell phone", "score": 0.9, "bbox": [0, 0, 1, 1]},
            {"frame": "frame_000006.jpg", "label": "cell phone", "score": 0.9, "bbox": [0, 0, 1, 1]},
        ],
    }
    detections_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("CLIP_SIGNIFICANT_EVENTS_ONLY", "1")
    monkeypatch.setenv("SIGNIFICANT_EVENT_LABELS", "cell phone")
    monkeypatch.setenv("EVENT_LABELS", "*")

    from pipelines.segmenter import build_segments

    segments_path = build_segments(str(detections_path), fps=1, segment_gap=1, min_segment_frames=1)
    data = json.loads(Path(segments_path).read_text(encoding="utf-8"))

    assert len(data["segments"]) == 1
    assert data["segments"][0].get("event_label") == "cell phone"


def test_build_segments_uses_pose_fatigue_events(tmp_path, monkeypatch):
    detections_path = tmp_path / "detections.json"
    fatigue_path = tmp_path / "pose_fatigue.json"
    payload = {
        "video_frames": 12,
        "detections": [
            {"frame": "frame_000001.jpg", "label": "person", "score": 0.9, "bbox": [0, 0, 1, 1]},
        ],
    }
    fatigue_rows = [
        {"frame": "frame_000006.jpg", "slouch": True, "microsleep": False, "yawn": False, "head_nod": False},
        {"frame": "frame_000007.jpg", "slouch": True, "microsleep": True, "yawn": False, "head_nod": False},
    ]
    detections_path.write_text(json.dumps(payload), encoding="utf-8")
    fatigue_path.write_text(json.dumps(fatigue_rows), encoding="utf-8")

    monkeypatch.setenv("CLIP_SIGNIFICANT_EVENTS_ONLY", "1")
    monkeypatch.setenv("SIGNIFICANT_EVENT_LABELS", "cell phone")
    monkeypatch.setenv("USE_POSE_FOR_SIGNIFICANT_EVENTS", "1")
    monkeypatch.setenv("SIGNIFICANT_FATIGUE_FLAGS", "slouch,microsleep")
    monkeypatch.setenv("EVENT_LABELS", "*")

    from pipelines.segmenter import build_segments

    segments_path = build_segments(
        str(detections_path),
        fps=1,
        segment_gap=1,
        min_segment_frames=1,
        fatigue_path=str(fatigue_path),
    )
    data = json.loads(Path(segments_path).read_text(encoding="utf-8"))

    labels = {str(seg.get("event_label", "")) for seg in data.get("segments", [])}
    assert "fatigue_slouch" in labels or "fatigue_microsleep" in labels


def test_high_priority_events_stay_separate_when_overlap_merge_on(tmp_path, monkeypatch):
    detections_path = tmp_path / "detections.json"
    fatigue_path = tmp_path / "pose_fatigue.json"
    payload = {
        "video_frames": 20,
        "detections": [
            {"frame": "frame_000010.jpg", "label": "cell phone", "score": 0.95, "bbox": [0, 0, 1, 1]},
        ],
    }
    fatigue_rows = [
        {"frame": "frame_000011.jpg", "slouch": False, "microsleep": True, "yawn": False, "head_nod": False},
    ]
    detections_path.write_text(json.dumps(payload), encoding="utf-8")
    fatigue_path.write_text(json.dumps(fatigue_rows), encoding="utf-8")

    monkeypatch.setenv("CLIP_SIGNIFICANT_EVENTS_ONLY", "1")
    monkeypatch.setenv("SIGNIFICANT_EVENT_LABELS", "cell phone")
    monkeypatch.setenv("USE_POSE_FOR_SIGNIFICANT_EVENTS", "1")
    monkeypatch.setenv("SIGNIFICANT_FATIGUE_FLAGS", "microsleep")
    monkeypatch.setenv("HIGH_PRIORITY_EVENT_LABELS", "fatigue_microsleep")
    monkeypatch.setenv("EVENT_MERGE_PADDED_OVERLAPS", "1")
    monkeypatch.setenv("EVENT_PADDING_FRAMES", "1")
    monkeypatch.setenv("EVENT_LABELS", "*")

    from pipelines.segmenter import build_segments

    segments_path = build_segments(
        str(detections_path),
        fps=1,
        segment_gap=1,
        min_segment_frames=1,
        fatigue_path=str(fatigue_path),
    )
    data = json.loads(Path(segments_path).read_text(encoding="utf-8"))
    labels = [str(seg.get("event_label", "")) for seg in data.get("segments", [])]

    assert len(data.get("segments", [])) == 2
    assert "cell phone" in labels
    assert "fatigue_microsleep" in labels
    microsleep_seg = next(seg for seg in data["segments"] if seg.get("event_label") == "fatigue_microsleep")
    assert microsleep_seg.get("event_severity") == "high"
