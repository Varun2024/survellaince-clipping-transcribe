- Video Intelligence Offline MVP

Structured, open-source MVP for an offline video intelligence pipeline focused on long videos (1–2 hours) and driver-behavior analysis. The stack is designed to be modular, replaceable, and usable without cloud dependencies.

This repository provides a minimal, end-to-end offline pipeline with placeholders for API keys. It supports plugging in real models (YOLOv8, Whisper) while preserving a stable orchestration layer. Replace or upgrade components as needed without changing the surrounding pipeline shape.

Table of contents
- Developer-Focused Readme

Overview
- This repository implements an offline Video Intelligence MVP intended for fellow developers. The stack is modular, open-source, and designed to be incrementally replaced with real-model components (YOLOv8, Whisper, etc.) without changing the orchestration layer.
- All heavy dependencies and secrets live behind the .env file. Keys are not committed.

Quickstart (dev environment)
- Prerequisites: Python 3.8+, FFmpeg installed and on PATH
- Setup:
  ```bash
  python -m venv venv
  source venv/bin/activate  # Windows: .\venv\Scripts\activate
  pip install -r requirements.txt
  ```
- Run the MVP pipeline:
  ```bash
  python main.py --input path/to/input_video.mp4 --output output
  ```
- Outputs will appear under the output directory:
  - frames/, detections.json, segments.json, clips/
  - transcripts/, transcripts_index.json
  - report.txt

Project layout
- pipelines/ - module implementations: ingest.py, detect.py, segmenter.py, clipper.py, transcriber.py, report.py
- main.py - orchestrator
- tests/ - unit tests and small integration helpers
- .env - environment configuration for paths and keys
- README.md - this developer-focused documentation
- requirements.txt - Python dependencies to wire in real models

Data contracts (inter-module interfaces)
- detections.json (produced by pipelines/detect.py)
  - {
      "video_frames": <int>,
      "detections": [
        {"frame": "frame_000001.jpg", "label": "phone", "score": 0.85, "bbox": [x1,y1,x2,y2]}
      ]
    }
- segments.json (produced by pipelines/segmenter.py)
  - {
      "video": "<video_id or path>",
      "fps": 1,
      "segments": [ {"start_frame": 1, "end_frame": 120}, ... ]
    }
- transcripts_index.json (produced by pipelines/transcriber.py)
  - [ {"clip": "segment_001.mp4", "transcript": "transcripts/segment_001.txt"}, ... ]
- transcripts/ (directory with per-clip transcripts)
- report.txt (produced by pipelines/report.py)

.env and configuration
- The .env file centralizes model paths and run-time options. Do not commit real keys.
- Usual keys:
  - YOLO_MODEL_PATH: path to YOLO model (pt)
  - WHISPER_MODEL_PATH: path to Whisper model/directory
  - OPENAI_API_KEY, QWEN_API_KEY: for future LLM integrations
  - FFMPEG_BIN: override if FFmpeg is not on PATH
  - FRAME_RATE: frames per second to sample (default 1)
  - OUTPUT_DIR: base output path (default ./output)

Running and development flow
- Local development: run the full pipeline via the main CLI, then inspect the outputs under the OUTPUT_DIR.
- To test individual modules:
  - python -m pipelines.ingest
- Tests: pytest

Module details
- pipelines/ingest.py
  - Extracts frames from input video using FFmpeg at a configurable frame rate, writes to frames/ and returns the path
- pipelines/detect.py
  - Attempts real YOLO inference via Ultralytics if a model is provided; otherwise falls back to MVP-generated detections
- pipelines/segmenter.py
  - Builds segments by grouping consecutive frames with detections; outputs segments.json
- pipelines/clipper.py
  - Clips segments from the original video into segment_XX.mp4 files
- pipelines/transcriber.py
  - Transcribes audio per clip using Whisper if available; otherwise placeholder transcripts
- pipelines/report.py
  - Generates a human-readable MVP report combining segments and transcripts
- main.py
  - Orchestrator; exposes a simple CLI for end-to-end runs

Wiring real models (developer guide)
- YOLO (object detection)
  - Install Ultralytics: pip install ultralytics
  - Place a trained model (.pt) and set YOLO_MODEL_PATH in .env
  - The code reads model outputs and emits a uniform detections.json
- Whisper (transcription)
  - Install Whisper tooling and set WHISPER_MODEL_PATH to a local model
  - The transcriber loads the model and transcribes per clip audio

Testing and CI
- Tests exist under tests/ (ingest, transcriber, and helpers)
- Run: pytest
- For CI, consider a workflow to install dependencies, run tests, and lint code

Contributing
- Open PRs with focused changes; include tests and update READMEs as needed
- Keep environment-specific defaults out of repo; use .env for secrets and local paths

License
- MIT (or your preferred license)

- Prerequisites: Python 3.8+, FFmpeg, optionally PyTorch for real-model inference
- Install dependencies:
  ```bash
  python -m venv venv
  source venv/bin/activate  # on Windows: .\venv\Scripts\activate
  pip install -r requirements.txt
  ```
- Optional: install real model tooling when you wire in real models
- Quickstart: see the Quickstart section for a one-shot run

Architecture overview
- The pipeline is split into clear stages with a predictable data flow:
  - Ingest frames from the input video (FFmpeg)
  - Detect objects/activities (YOLO when available; MVP fallback otherwise)
  - Build temporal segments from detections
  - Clip the original video into segment clips (FFmpeg)
  - Transcribe audio using Whisper (if available)
  - Reasoning/reporting via a lightweight final report
- All data moves through a small, well-defined JSON contract between stages

Quickstart (end-to-end)
- Prereqs: install dependencies, ensure FFmpeg in PATH, set environment
- Run the pipeline on a sample video:
  ```bash
  python main.py --input path/to/input_video.mp4 --output ./output
  ```
- Outputs appear under ./output:
  - frames/            # extracted frames
  - detections.json    # per-frame detections (real or MVP)
  - segments.json      # temporal segments built from detections
  - clips/              # clipped segment videos
  - transcripts/        # per-clip transcripts (or placeholders)
  - transcripts_index.json
  - report.txt          # final MVP report

Pipeline overview and file layout
- pipelines/ - module implementations
- main.py - orchestrator that ties the modules together
- .env - environment-based configuration (model paths, API keys, etc.)
- tests/ - unit tests for MVP components
- README.md - this documentation
- requirements.txt - Python dependencies (adjust when wiring real models)

Environment and configuration
- The .env file is the central place to configure model paths, API keys, and runtime options.
- Keys are intentionally left blank to avoid committing secrets. Fill them locally.
- Common variables:
  - YOLO_MODEL_PATH: path to your trained YOLO model (pt)
  - WHISPER_MODEL_PATH: path to your Whisper model/direct path
  - OPENAI_API_KEY, QWEN_API_KEY: for future LLM integrations
  - FFMPEG_BIN: override FFmpeg binary path if needed
  - FRAME_RATE: frames per second for extraction (default 1)
  - OUTPUT_DIR: base directory for all outputs (default ./output)

Component details
- pipelines/ingest.py
  - Ingests frames from a video using FFmpeg at a configurable frame rate
  - Outputs frames to a frames/ directory and returns the path
- pipelines/detect.py
  - Attempts to load a YOLO model via Ultralytics if a model path is provided
  - Falls back to MVP synthetic detections if the model isn’t available
  - Writes detections.json with per-frame detections
- pipelines/segmenter.py
  - Builds simple segments from per-frame detections (start_frame, end_frame)
- pipelines/clipper.py
  - Clips segments from the input video using FFmpeg based on frame indices
- pipelines/transcriber.py
  - Transcribes audio for each clip via Whisper when available
  - Falls back to placeholder transcripts if Whisper isn’t available
- pipelines/report.py
  - Generates a human-readable report summarizing segments and transcripts
- main.py
  - Orchestrates the end-to-end flow; exposed as a simple CLI

Real-model wiring guide (YOLO + Whisper)
- YOLO (object detection)
  - Install Ultralytics: python -m pip install ultralytics
  - Train or obtain a model file (e.g., yolov8n.pt) and place it in a path
  - Point YOLO_MODEL_PATH to that file in the .env
- Whisper (transcription)
  - Install: pip install -r requirements.txt or specific whisper package per your setup
  - Put your Whisper model in a local path and set WHISPER_MODEL_PATH
  - The transcriber will load your model and transcribe per-clip audio provided the clip contains audio

Testing
- A lightweight unit-test scaffold exists under tests/ (ingest and transcriber)
- To run tests: pytest
- The tests rely on monkeypatching external dependencies (FFmpeg, Whisper) to run in CI or on local machines without heavy model loading

Development and contribution
- This project follows a fork-and-PR workflow. Small, well-scoped PRs with a clear Why/What/How are encouraged
- Add tests for any new feature or model integration
- Update README with usage notes and environment changes when needed

License
- MIT (or your preferred license)

FAQ
- Q: What is MVP scope?
  A: End-to-end offline pipeline with 1 FPS frame sampling, MVP detections, segmenting, clipping, transcription (Whisper), and basic reporting.
- Q: How do I upgrade to real models?
  A: Install the required libraries, place model files, configure environment variables, and swap the MVP paths with real in the detect and transcriber modules.

- Getting started
- Architecture overview
- How to run
- Pipeline modules
- Environment and config
- Extending with real models
- Development and testing
- Contributing
- License

Getting started
- Prerequisites:
  - Python 3.8+ (tested with 3.10+)
  - FFmpeg installed and available on PATH
  - Optional: a CUDA-enabled GPU for real model inference
- Install dependencies (placeholder):
  - Create a Python virtual environment
  - pip install -r requirements.txt
- Basic usage:
  - Place your input video somewhere on disk
  - Run: python main.py --input <video_path> --output <output_dir>
  - Outputs will be generated under the output_dir (frames, detections.json, segments.json, clips/, transcripts/, report.txt)

Architecture overview
- Ingest: FFmpeg-based frame extraction
- Detection: real YOLO model when available, otherwise deterministic MVP detections
- Segmentation: simple frame-range grouping
- Clipping: FFmpeg-based segment extraction
- Transcription: Whisper if available, otherwise placeholder transcripts
- Reasoning/Reporting: simple reporting glue to output a final report

How to run (quick start)
- Ensure FFmpeg is installed
- Create output directory and run the pipeline
  - Example:
    - mkdir -p output
    - python main.py --input path/to/input_video.mp4 --output output
- Inspect the generated artifacts in the output directory

Pipeline modules
- pipelines/ingest.py: frame extraction with FFmpeg
- pipelines/detect.py: real YOLO-based detection (optional) with fallback to MVP detections
- pipelines/segmenter.py: segment formation from detections
- pipelines/clipper.py: FFmpeg-based clipping of segments
- pipelines/transcriber.py: transcription with Whisper if available, else placeholder
- pipelines/report.py: generate human-readable MVP report
- main.py: orchestrator

Environment and config
- .env: central place for model paths, API keys, and runtime options
- Keys are not committed. Fill in your own local values.
- Typical keys: YOLO_MODEL_PATH, WHISPER_MODEL_PATH, OPENAI_API_KEY, QWEN_API_KEY, FFMPEG_BIN

Extending with real models
- Replacing the MVP with real detections:
  - Install Ultralytics YOLO and point YOLO_MODEL_PATH to your trained model
- Wire Whisper for real transcription via WHISPER_MODEL_PATH
- Optional: add an actual reporting/LLM module for richer reasoning

Development and testing
- Unit tests scaffolding can be added per module
- End-to-end tests with a short sample video
- Lint/style checks as needed

Contributing
- Fork, implement, and submit a PR
- Follow the PR style: small, focused changes with clear commit messages that explain why

License
- MIT (or choose as appropriate)

Notes
- This MVP uses a guarded approach: if a real model is unavailable, it falls back to deterministic, lightweight detections to allow end-to-end testing and iteration.
- All sensitive keys belong in .env; do not commit real keys.
# event-extraction-rail
#   s u r v e l l a i n c e - c l i p p i n g - t r a n s c r i b e  
 