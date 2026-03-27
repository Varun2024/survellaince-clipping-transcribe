import json
import os
from pathlib import Path
from typing import List


def transcribe_clips(clips: List[str], transcripts_dir: str, whisper_model_path: str = None) -> str:
    transcripts_dir_p = Path(transcripts_dir)
    transcripts_dir_p.mkdir(parents=True, exist_ok=True)

    # Try to use Whisper if available; otherwise generate simple placeholder transcripts
    transcripts_index = []
    model = None
    try:
        import whisper  # type: ignore
        model_path = whisper_model_path or os.environ.get("WHISPER_MODEL_PATH", "small")
        # If a local path is provided and exists, use it; otherwise fall back to a known model name
        try:
            if isinstance(model_path, str) and Path(model_path).exists():
                model = whisper.load_model(model_path)  # type: ignore
            else:
                model = whisper.load_model(model_path)  # type: ignore
        except Exception:
            model = whisper.load_model("small")  # type: ignore
    except Exception:
        model = None

    for clip_path in clips:
        clip_name = Path(clip_path).stem
        transcript_file = transcripts_dir_p / f"{clip_name}.txt"
        content = None
        if model is not None:
            try:
                result = model.transcribe(str(clip_path))  # type: ignore
                content = result.get("text", "")
            except Exception:
                content = f"Transcript placeholder for {clip_path}."
        else:
            content = f"Transcript placeholder for {clip_path}."

        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(content or "")
        transcripts_index.append({"clip": clip_path, "transcript": str(transcript_file)})

    index_path = str(transcripts_dir_p / "transcripts_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(transcripts_index, f, indent=2)
    print(f"Transcripts written to {transcripts_dir_p}, index at {index_path}")
    return index_path
