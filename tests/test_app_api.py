from pathlib import Path

from fastapi.testclient import TestClient


def _client(monkeypatch):
    from app import api as api_mod

    monkeypatch.setattr(api_mod, "init_runtime", lambda: None)
    monkeypatch.setattr(api_mod, "runtime_status", lambda: {"ffmpeg_available": True, "ffmpeg_bin": "ffmpeg"})
    return TestClient(api_mod.app)


def test_health_endpoint(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ffmpeg_available"] == "1"


def test_ui_pages(monkeypatch):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(api_mod, "list_job_records", lambda **_: [])
    monkeypatch.setattr(api_mod, "runtime_status", lambda: {"ffmpeg_available": True, "ffmpeg_bin": "ffmpeg"})
    monkeypatch.setattr(api_mod, "get_job_record", lambda _job_id: {"id": "job1", "filename": "input.mp4", "status": "completed"})
    monkeypatch.setattr(api_mod, "job_artifacts", lambda _job_id: {"data": {}})

    assert client.get("/").status_code == 200
    assert client.get("/overview").status_code == 200
    assert client.get("/upload").status_code == 200
    assert client.get("/jobs-ui").status_code == 200
    assert client.get("/jobs-ui/job1").status_code == 200


def test_create_job_rejects_non_video_content_type(monkeypatch, tmp_path):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(api_mod, "create_and_queue_job", lambda *_: {"id": "job1", "status": "queued"})
    response = client.post(
        "/jobs",
        files={"file": ("input.mp4", b"abc", "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid content type" in response.text


def test_create_job_success(monkeypatch):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(
        api_mod,
        "create_and_queue_job",
        lambda *_: {"id": "job1", "filename": "input.mp4", "status": "queued"},
    )
    response = client.post(
        "/jobs",
        files={"file": ("input.mp4", b"abc", "video/mp4")},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "job1"


def test_get_job_not_found(monkeypatch):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(api_mod, "get_job_record", lambda _job_id: None)
    response = client.get("/jobs/missing")
    assert response.status_code == 404


def test_get_artifacts(monkeypatch):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(api_mod, "get_job_record", lambda _job_id: {"id": "job1", "status": "completed"})
    monkeypatch.setattr(api_mod, "job_artifacts", lambda _job_id: {"job_id": "job1", "ready": True})
    response = client.get("/jobs/job1/artifacts")
    assert response.status_code == 200
    assert response.json()["job_id"] == "job1"


def test_download_missing(monkeypatch):
    from app import api as api_mod

    client = _client(monkeypatch)
    monkeypatch.setattr(api_mod, "safe_job_file_path", lambda *_: None)
    response = client.get("/jobs/job1/download?path=report.txt")
    assert response.status_code == 404


def test_download_success(monkeypatch, tmp_path):
    from app import api as api_mod

    client = _client(monkeypatch)
    report = Path(tmp_path) / "report.txt"
    report.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(api_mod, "safe_job_file_path", lambda *_: report)
    response = client.get("/jobs/job1/download?path=report.txt")
    assert response.status_code == 200


def test_source_video_success(monkeypatch, tmp_path):
    from app import api as api_mod

    client = _client(monkeypatch)
    source = Path(tmp_path) / "input.mp4"
    source.write_bytes(b"video-bytes")
    monkeypatch.setattr(api_mod, "safe_uploaded_video_path", lambda *_: source)
    response = client.get("/jobs/job1/source-video")
    assert response.status_code == 200
