def test_compute_progress_running():
    from app.job_manager import _compute_progress

    exists = {
        "detections_json": True,
        "segments_json": True,
        "pose_fatigue_json": True,
        "alerts_json": False,
        "transcripts_index_json": False,
        "report_txt": False,
        "qwen_whole_summary_md": False,
    }
    progress = _compute_progress(exists, "running")
    assert progress["state"] == "running"
    assert 0 < progress["percent"] < 100
    assert len(progress["stages"]) == 6


def test_compute_progress_completed():
    from app.job_manager import _compute_progress

    progress = _compute_progress({}, "completed")
    assert progress["state"] == "completed"
    assert progress["percent"] == 100
    assert all(stage["done"] for stage in progress["stages"])
