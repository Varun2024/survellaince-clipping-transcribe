import os
import subprocess
from pathlib import Path


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ingest_video(input_path: str, frames_dir: str, frame_rate: int = 1, width: int = 1280, height: int = 720) -> Path:
    """Extract frames from a video at a given frame rate.
    - Frames are saved as frame_000001.jpg, frame_000002.jpg, ...
    - Returns the directory containing frames.
    """
    frames_dir_p = ensure_dir(frames_dir)
    # Normalize paths
    input_path = str(input_path)
    frame_pattern = os.path.join(str(frames_dir_p), "frame_%06d.jpg")

    # Build FFmpeg command
    ffmpeg = os.environ.get("FFMPEG_BIN", "ffmpeg")
    # -vf scale ensures consistent resolution; adjust if input is already suitable
    filter_str = f"fps={frame_rate},scale={width}:{height}"
    cmd = [ffmpeg, "-y", "-i", input_path, "-vf", filter_str, frame_pattern]

    print(f"Ingest: extracting frames to {frames_dir_p} at {frame_rate}fps (scaled {width}x{height})")
    subprocess.run(cmd, check=True)
    return frames_dir_p
