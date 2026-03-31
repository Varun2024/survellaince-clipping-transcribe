import os
import subprocess
from pathlib import Path

from pipelines.utils import ensure_dir, read_json


def clip_segments(video_path: str, segments_path: str, output_dir: str, fps: int = 1) -> list:
    video = Path(video_path)
    segments = read_json(segments_path, {"segments": []})
    clips = []
    out_dir = ensure_dir(output_dir)
    ffmpeg = os.environ.get("FFMPEG_BIN", "ffmpeg")
    clip_reencode = os.environ.get("CLIP_REENCODE", "1") == "1"

    for i, seg in enumerate(segments.get("segments", []), start=1):
        start_frame = seg.get("start_frame", 0)
        end_frame = seg.get("end_frame", 0)
        start_sec = max(0.0, (start_frame - 1) / float(fps))
        duration = max(0.0, (end_frame - start_frame + 1) / float(fps))
        out_path = out_dir / f"segment_{i:03d}.mp4"
        if clip_reencode:
            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(start_sec),
                "-t", str(duration),
                "-i", str(video),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(out_path),
            ]
        else:
            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(start_sec),
                "-t", str(duration),
                "-i", str(video),
                "-c", "copy",
                str(out_path),
            ]
        print(f"Clipping segment {i}: {start_sec:.2f}s for {duration:.2f}s -> {out_path}")
        subprocess.run(cmd, check=True)
        clips.append(str(out_path))
    return clips
