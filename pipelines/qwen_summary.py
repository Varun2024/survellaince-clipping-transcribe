import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from pipelines.utils import read_json, write_json


def _resolve_qwen_config() -> Dict[str, str]:
    api_key = os.environ.get("QWEN_API_KEY", "").strip()
    base_url = os.environ.get("QWEN_API_BASE_URL", "").strip()

    if api_key.startswith("http://") or api_key.startswith("https://"):
        base_url = api_key
        api_key = os.environ.get("QWEN_API_TOKEN", os.environ.get("OPENAI_API_KEY", "")).strip()

    if not base_url:
        base_url = "https://api.qwen.ai/v1"

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": os.environ.get("QWEN_MODEL", "qwen/qwen3-32b"),
        "candidate_models": os.environ.get(
            "QWEN_MODEL_CANDIDATES",
            "qwen/qwen3-32b,qwen/qwen2.5-32b,qwen/qwen1.5-32b,qwen-plus",
        ),
    }


def _client() -> OpenAI:
    cfg = _resolve_qwen_config()
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])


def _candidate_models() -> List[str]:
    cfg = _resolve_qwen_config()
    models = [m.strip() for m in cfg["candidate_models"].split(",") if m.strip()]
    if cfg["model"] not in models:
        models.insert(0, cfg["model"])
    return models


def _call_with_model_fallback(client: OpenAI, messages: List[Dict[str, str]], temperature: float = 0.2) -> Dict[str, str]:
    chosen_model = ""
    last_error = None
    for model in _candidate_models():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""
            chosen_model = model
            return {"content": content, "model": chosen_model}
        except Exception as exc:
            last_error = exc
            continue

    return {
        "content": json.dumps(
            {
                "error": "Qwen remote call failed for all candidate models.",
                "details": str(last_error),
            },
            indent=2,
        ),
        "model": chosen_model,
    }


def _clip_payload(index_row: Dict[str, Any], segment_alerts: List[Dict[str, Any]], transcripts_dir: Path) -> Dict[str, Any]:
    transcript_path = Path(index_row.get("transcript", ""))
    transcript_text = ""
    if transcript_path.exists():
        transcript_text = transcript_path.read_text(encoding="utf-8").strip()

    clip_name = Path(index_row.get("clip", "clip.mp4")).stem
    matching_alert = None
    for alert in segment_alerts:
        if int(alert.get("segment_id", -1)) == int(clip_name.split("_")[-1]):
            matching_alert = alert
            break

    return {
        "clip": index_row.get("clip", ""),
        "transcript": transcript_text,
        "segment_alert": matching_alert or {},
    }


def _strip_reasoning_and_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\\s*```$", "", cleaned).strip()
    return cleaned


def _json_to_clip_markdown(data: Dict[str, Any], clip_path: str) -> str:
    clip_name = Path(clip_path).name if clip_path else "unknown_clip"
    key_events = data.get("key_events", []) or []
    key_events_md = "\n".join([f"- {str(evt)}" for evt in key_events]) if key_events else "- No key events reported"

    return (
        f"### Clip: {clip_name}\n\n"
        f"**Clip Summary**\n{data.get('clip_summary', 'No summary provided')}\n\n"
        f"**Key Events**\n{key_events_md}\n\n"
        f"**Risk Level**\n{data.get('risk_level', 'Unknown')}\n\n"
        f"**Recommended Action**\n{data.get('recommended_action', 'Review clip manually.')}\n"
    )


def _json_to_whole_markdown(data: Dict[str, Any]) -> str:
    major_events = data.get("major_events", []) or []
    major_events_md = "\n".join([f"- {str(evt)}" for evt in major_events]) if major_events else "- No major events reported"
    next_steps_val = data.get("next_steps", data.get("actionable_next_steps", "Review generated outputs."))
    if isinstance(next_steps_val, list):
        next_steps_md = "\n".join([f"- {str(step)}" for step in next_steps_val]) if next_steps_val else "- Review generated outputs."
    else:
        next_steps_md = f"- {str(next_steps_val)}"

    return (
        "## Executive Summary\n"
        f"{data.get('executive_summary', 'No executive summary provided.')}\n\n"
        "## Major Events\n"
        f"{major_events_md}\n\n"
        "## Overall Risk Level\n"
        f"{data.get('overall_risk_level', data.get('overall_risk', 'Unknown'))}\n\n"
        "## Actionable Next Steps\n"
        f"{next_steps_md}\n"
    )


def _normalize_clip_summary_to_markdown(content: str, clip_path: str) -> str:
    cleaned = _strip_reasoning_and_fences(content)

    if "```json" in cleaned.lower():
        match = re.search(r"```json\\s*(.*?)\\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return _json_to_clip_markdown(parsed, clip_path)
    except Exception:
        pass

    return cleaned


def _normalize_whole_summary_to_markdown(content: str) -> str:
    cleaned = _strip_reasoning_and_fences(content)

    if "```json" in cleaned.lower():
        match = re.search(r"```json\\s*(.*?)\\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return _json_to_whole_markdown(parsed)
    except Exception:
        pass

    return cleaned


def generate_qwen_summaries(
    transcripts_index_path: str,
    alerts_path: str,
    report_path: str,
    output_dir: str,
) -> str:
    transcripts_index = read_json(transcripts_index_path, []) or []
    alerts_payload = read_json(alerts_path, {"summary": {}, "alerts": [], "segment_alerts": []}) or {}
    report_text = Path(report_path).read_text(encoding="utf-8") if report_path and Path(report_path).exists() else ""

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries: List[Dict[str, Any]] = []
    client = None
    cfg = _resolve_qwen_config()
    use_remote = bool(cfg["api_key"])
    if use_remote:
        try:
            client = _client()
        except Exception:
            client = None
            use_remote = False

    segment_alerts = alerts_payload.get("segment_alerts", []) or []
    for idx, row in enumerate(transcripts_index, start=1):
        clip_payload = _clip_payload(row, segment_alerts, out_dir)
        prompt = (
            "You are a safety analyst for railway surveillance.\n"
            "Summarize this clip for the locopilot monitoring context.\n"
            "Return Markdown only using these sections in order:\n"
            "### Clip: <clip_name>\n"
            "**Clip Summary**\n"
            "**Key Events**\n"
            "**Risk Level**\n"
            "**Recommended Action**\n"
            "Do not use JSON and do not include reasoning tags.\n\n"
            f"CLIP_PATH: {clip_payload['clip']}\n"
            f"TRANSCRIPT:\n{clip_payload['transcript']}\n\n"
            f"SEGMENT_ALERT:\n{json.dumps(clip_payload['segment_alert'], indent=2)}\n"
        )

        if client is not None:
            result = _call_with_model_fallback(
                client,
                [
                    {"role": "system", "content": "You produce tight, operational summaries for surveillance clips."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = result["content"]
            if result["model"]:
                cfg["model"] = result["model"]
        else:
            content = (
                f"### Clip: {Path(clip_payload['clip']).name or 'unknown_clip'}\n\n"
                "**Clip Summary**\n"
                "Qwen not configured; fallback summary generated locally.\n\n"
                "**Key Events**\n"
                "- Transcript processed\n"
                "- Alert data available\n\n"
                "**Risk Level**\n"
                f"{clip_payload['segment_alert'].get('severity', 'unknown') or 'unknown'}\n\n"
                "**Recommended Action**\n"
                "Review the clip and associated alerts.\n"
            )

        content_md = _normalize_clip_summary_to_markdown(content, clip_payload["clip"])

        summaries.append(
            {
                "clip": row.get("clip", ""),
                "transcript": row.get("transcript", ""),
                "qwen_summary": content_md,
            }
        )

    clip_summary_path = write_json(str(out_dir / "clip_summaries.json"), summaries)
    clip_markdown_path = out_dir / "clip_summaries.md"
    clip_md_parts = ["# Clip Summaries\n"]
    for item in summaries:
        clip_md_parts.append(item.get("qwen_summary", "").strip())
        clip_md_parts.append("")
    clip_markdown_path.write_text("\n".join(clip_md_parts).strip() + "\n", encoding="utf-8")

    whole_prompt = (
        "You are preparing the final monitoring report for a railway locopilot.\n"
        "Use the report text, alerts, and clip summaries to produce:\n"
        "1) an executive summary,\n"
        "2) a list of major events,\n"
        "3) overall risk level,\n"
        "4) actionable next steps.\n"
        "Return Markdown only with these headings exactly:\n"
        "## Executive Summary\n"
        "## Major Events\n"
        "## Overall Risk Level\n"
        "## Actionable Next Steps\n"
        "Do not return JSON and do not include reasoning tags.\n"
        "Keep the result concise and operational.\n\n"
        f"REPORT:\n{report_text}\n\n"
        f"ALERTS:\n{json.dumps(alerts_payload, indent=2)}\n\n"
        f"CLIP_SUMMARIES:\n{json.dumps(summaries, indent=2)}\n"
    )

    if client is not None:
        result = _call_with_model_fallback(
            client,
            [
                {"role": "system", "content": "You write concise operational summaries for railway monitoring."},
                {"role": "user", "content": whole_prompt},
            ],
            temperature=0.2,
        )
        whole_summary = result["content"]
        if result["model"]:
            cfg["model"] = result["model"]
    else:
        whole_summary = (
            "## Executive Summary\n"
            "Qwen not configured; fallback whole-video summary generated locally.\n\n"
            "## Major Events\n"
            + "\n".join([f"- {a.get('message', '')}" for a in alerts_payload.get("alerts", [])[:5]])
            + "\n\n"
            "## Overall Risk Level\n"
            + str(alerts_payload.get("summary", {}).get("fatigue_ratio", 0))
            + "\n\n"
            "## Actionable Next Steps\n"
            "- Review clips, alerts, and transcripts.\n"
        )

    whole_summary = _normalize_whole_summary_to_markdown(whole_summary)

    legacy_whole_summary_path = Path(out_dir / "whole_video_summary.txt")
    if legacy_whole_summary_path.exists():
        legacy_whole_summary_path.unlink()

    whole_summary_path = Path(out_dir / "whole_video_summary.md")
    whole_summary_path.write_text(whole_summary, encoding="utf-8")

    manifest = {
        "clip_summaries": clip_summary_path,
        "clip_summaries_markdown": str(clip_markdown_path),
        "whole_video_summary": str(whole_summary_path),
        "model": cfg["model"],
        "base_url": cfg["base_url"],
        "used_remote": use_remote,
    }
    write_json(str(out_dir / "qwen_summary_manifest.json"), manifest)
    print(f"Qwen summaries written to {out_dir}")
    return str(out_dir)
