#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from pipelines.ingest import ingest_video
from pipelines.detect import run_detection
from pipelines.segmenter import build_segments
from pipelines.clipper import clip_segments
from pipelines.transcriber import transcribe_clips
from pipelines.report import generate_report
from pipelines.pose_fatigue import analyze_pose_and_fatigue


def load_env_defaults():
    # Simple env loader for .env (no external dependency)
    if not os.path.exists('.env'):
        return
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                if k and v is not None:
                    os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env_defaults()
    parser = argparse.ArgumentParser(description="MVP Video Intelligence Pipeline (Offline)")
    parser.add_argument("input", help="Input video path")
    parser.add_argument("output", nargs="?", default="output", help="Output directory")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    # Ensure dirs
    frames_dir = output_dir / "frames"
    results_json = output_dir / "detections.json"
    segments_json = output_dir / "segments.json"
    clips_dir = output_dir / "clips"
    transcripts_dir = output_dir / "transcripts"
    report_path = output_dir / "report.txt"

    frame_rate = int(os.environ.get("FRAME_RATE", "1"))

    print(f"Starting MVP pipeline for {input_path}")

    # 1) Ingest frames
    ingest_video(str(input_path), str(frames_dir), frame_rate=frame_rate)

    # 2) Detection (simulate if no model)
    run_detection(str(frames_dir), os.environ.get("YOLO_MODEL_PATH", ""), str(results_json))

    # 3) Build segments
    build_segments(str(results_json), fps=frame_rate, segment_gap=5, min_segment_frames=5)

    # 4) Clip segments
    clip_paths = clip_segments(str(input_path), str(segments_json), str(clips_dir), fps=frame_rate)

    # 4.5) Pose and Fatigue Analysis (MediaPipe)
    pose_fatigue_json = output_dir / "pose_fatigue.json"
    analyze_pose_and_fatigue(str(frames_dir), str(pose_fatigue_json))

    # 5) Transcription
    index_path = transcribe_clips(clip_paths, str(transcripts_dir), os.environ.get("WHISPER_MODEL_PATH"))

    # 6) Reporting
    report = generate_report(str(segments_json), str(index_path), str(report_path))
    print("Pipeline complete. Report:", report)

if __name__ == "__main__":
    main()
