import os
import json
import subprocess
from pathlib import Path


def clip_segments(video_path: str, segments_path: str, output_dir: str, fps: int = 1) -> list:
    video = Path(video_path)
    segments = json.loads(Path(segments_path).read_text(encoding="utf-8"))
    clips = []
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, seg in enumerate(segments.get("segments", []), start=1):
        start_frame = seg.get("start_frame", 0)
        end_frame = seg.get("end_frame", 0)
        start_sec = max(0.0, (start_frame - 1) / float(fps))
        duration = max(0.0, (end_frame - start_frame + 1) / float(fps))
        out_path = out_dir / f"segment_{i:03d}.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video),
            "-ss", str(start_sec),
            "-t", str(duration),
            "-c", "copy",
            str(out_path),
        ]
        print(f"Clipping segment {i}: {start_sec:.2f}s for {duration:.2f}s -> {out_path}")
        subprocess.run(cmd, check=True)
        clips.append(str(out_path))
    return clips
