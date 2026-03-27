import os
from pathlib import Path


def test_ingest_creates_frames(monkeypatch, tmp_path):
    # Import module lazily to avoid importing heavy dependencies at import time
    from pipelines import ingest as ingest_mod

    # Create a dummy input video path (we won't actually read it due to monkeypatch)
    dummy_input = str(tmp_path / "input.mp4")
    frames_dir = str(tmp_path / "frames")

    # Patch subprocess.run to simulate FFmpeg frame extraction by creating dummy frames
    class DummyCompleted:
        def __init__(self):
            self.returncode = 0

    def fake_run(cmd, check=True, *args, **kwargs):
        # Last arg is the frame pattern
        frame_pattern = cmd[-1]
        outdir = Path(frame_pattern).parent
        outdir.mkdir(parents=True, exist_ok=True)
        # Create 3 dummy frames to simulate extraction
        for i in range(1, 4):
            (outdir / f"frame_{i:06d}.jpg").touch()
        return DummyCompleted()

    monkeypatch.setattr("subprocess.run", fake_run)

    out = ingest_mod.ingest_video(dummy_input, frames_dir, frame_rate=1)
    assert Path(frames_dir).exists()
    frame_files = sorted(Path(frames_dir).glob("frame_*.jpg"))
    assert len(frame_files) >= 3
