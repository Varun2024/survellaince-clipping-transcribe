import json
import sys
import types
from pathlib import Path


def test_transcribe_clips_with_mock_whisper(monkeypatch, tmp_path):
    # Create fake clip paths
    clips = [str(tmp_path / f"clip_{i}.mp4") for i in range(2)]
    for c in clips:
        Path(c).parent.mkdir(parents=True, exist_ok=True)
        Path(c).touch()

    # Create a fake whisper module
    fake_whisper = types.ModuleType("whisper")

    class DummyModel:
        def transcribe(self, audio_path):
            class Result:
                text = "dummy transcription"
            return {"text": "dummy transcription"}

    def load_model(name):
        return DummyModel()

    fake_whisper.load_model = load_model
    sys.modules["whisper"] = fake_whisper

    # Run transcription
    from pipelines.transcriber import transcribe_clips
    index_path = transcribe_clips(clips, str(tmp_path / "transcripts"), whisper_model_path="small")

    # Verify transcripts index exists and has entries
    idx_path = Path(index_path)
    assert idx_path.exists()
    index = json.loads(idx_path.read_text())
    assert len(index) == 2
    # Each transcript file should exist
    for entry in index:
        tpath = Path(entry["transcript"])
        assert tpath.exists()
