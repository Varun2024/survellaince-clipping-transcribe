import json
from pathlib import Path


def generate_report(segments_path: str, transcripts_index_path: str, report_path: str) -> str:
    segs = json.loads(Path(segments_path).read_text(encoding="utf-8")) if segments_path else {"segments": []}
    index = json.loads(Path(transcripts_index_path).read_text(encoding="utf-8")) if transcripts_index_path else []
    lines = []
    lines.append("Video Intelligence Report (MVP)")
    lines.append("")
    for i, seg in enumerate(segs.get("segments", []) or [], start=1):
        start = seg.get("start_frame", 0)
        end = seg.get("end_frame", 0)
        lines.append(f"Segment {i}: frames {start}-{end}")
        # Find related transcript path if available
        clip = index[i-1] if len(index) >= i else None
        if clip:
            lines.append(f"  Transcript: {clip.get('transcript', '')}")

    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report generated at {report_path}")
    return str(out)
