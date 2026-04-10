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
from pipelines.alerts import generate_alerts
from pipelines.utils import clear_dir
from pipelines.qwen_summary import generate_qwen_summaries


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
    alerts_path = output_dir / "alerts.json"

    frame_rate = int(os.environ.get("FRAME_RATE", "1"))
    segment_gap = int(os.environ.get("SEGMENT_GAP", "5"))
    min_segment_frames = int(os.environ.get("MIN_SEGMENT_FRAMES", "5"))

    print(f"Starting MVP pipeline for {input_path}")

    # Clear old artifacts that would otherwise make output look stale across runs
    clear_dir(str(frames_dir))
    clear_dir(str(clips_dir))

    # 1) Ingest frames
    ingest_video(str(input_path), str(frames_dir), frame_rate=frame_rate)

    # 2) Detection (simulate if no model)
    run_detection(str(frames_dir), os.environ.get("YOLO_MODEL_PATH", ""), str(results_json))

    # 3) Pose and Fatigue Analysis
    pose_fatigue_json = output_dir / "pose_fatigue.json"
    analyze_pose_and_fatigue(str(frames_dir), str(pose_fatigue_json))

    # 4) Build segments (detections + significant pose/fatigue events)
    build_segments(
        str(results_json),
        fps=frame_rate,
        segment_gap=segment_gap,
        min_segment_frames=min_segment_frames,
        fatigue_path=str(pose_fatigue_json),
    )

    # 5) Clip segments
    clip_paths = clip_segments(str(input_path), str(segments_json), str(clips_dir), fps=frame_rate)

    # 6) Alerts
    generate_alerts(
        detections_path=str(results_json),
        fatigue_path=str(pose_fatigue_json),
        segments_path=str(segments_json),
        alerts_path=str(alerts_path),
        fps=frame_rate,
    )

    # 7) Transcription
    index_path = transcribe_clips(clip_paths, str(transcripts_dir), os.environ.get("WHISPER_MODEL_PATH", "small"))

    # 8) Reporting
    report = generate_report(
        str(segments_json),
        str(index_path),
        str(report_path),
        pose_fatigue_path=str(pose_fatigue_json),
        detections_path=str(results_json),
        alerts_path=str(alerts_path),
    )

    # 9) Qwen summaries for per-clip and whole-video narrative reporting
    qwen_output_dir = output_dir / "qwen"
    generate_qwen_summaries(
        transcripts_index_path=str(index_path),
        alerts_path=str(alerts_path),
        report_path=str(report_path),
        output_dir=str(qwen_output_dir),
    )
    print("Pipeline complete. Report:", report)

if __name__ == "__main__":
    main()
