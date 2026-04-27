from pathlib import Path


def test_job_db_lifecycle(tmp_path):
    from app.db import create_job, get_job, init_db, list_jobs, update_job_status

    db_path = Path(tmp_path) / "jobs.db"
    init_db(db_path)

    create_job(
        db_path=db_path,
        job_id="job1",
        filename="input.mp4",
        upload_path=str(tmp_path / "upload.mp4"),
        output_dir=str(tmp_path / "run"),
        created_at="2026-01-01T00:00:00Z",
    )
    job = get_job(db_path, "job1")
    assert job is not None
    assert job["status"] == "queued"

    update_job_status(
        db_path=db_path,
        job_id="job1",
        status="completed",
        started_at="2026-01-01T00:00:01Z",
        finished_at="2026-01-01T00:00:02Z",
        error=None,
    )
    job = get_job(db_path, "job1")
    assert job is not None
    assert job["status"] == "completed"
    assert job["started_at"] == "2026-01-01T00:00:01Z"
    assert job["finished_at"] == "2026-01-01T00:00:02Z"

    jobs = list_jobs(db_path, limit=10)
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job1"
