import json
from pathlib import Path


def test_report_filters_generic_events(monkeypatch, tmp_path):
    segments_path = tmp_path / "segments.json"
    transcripts_index_path = tmp_path / "transcripts_index.json"
    detections_path = tmp_path / "detections.json"
    report_path = tmp_path / "report.txt"

    segments_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_frame": 5,
                        "end_frame": 6,
                        "start_time_sec": 4.0,
                        "end_time_sec": 6.0,
                        "event_label": "cell phone",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    transcripts_index_path.write_text(json.dumps([]), encoding="utf-8")
    detections_path.write_text(
        json.dumps(
            {
                "video_frames": 12,
                "detections": [
                    {"frame": "frame_000001.jpg", "label": "person", "score": 0.9},
                    {"frame": "frame_000005.jpg", "label": "cell phone", "score": 0.95},
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("REPORT_SIGNIFICANT_EVENTS_ONLY", "1")
    monkeypatch.setenv("SIGNIFICANT_EVENT_LABELS", "cell phone")

    from pipelines.report import generate_report

    generate_report(
        segments_path=str(segments_path),
        transcripts_index_path=str(transcripts_index_path),
        report_path=str(report_path),
        detections_path=str(detections_path),
    )

    text = Path(report_path).read_text(encoding="utf-8")
    assert "Total significant detections: 1" in text
    assert "cell phone(1)" in text
    assert "person(" not in text
