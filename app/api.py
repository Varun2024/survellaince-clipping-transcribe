from contextlib import asynccontextmanager
from html import escape
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.job_manager import (
    create_and_queue_job,
    get_job_record,
    init_runtime,
    job_artifacts,
    job_to_json,
    list_job_records,
    runtime_status,
    safe_job_file_path,
    safe_uploaded_video_path,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_runtime()
    yield


app = FastAPI(title="Railway Video Intelligence App", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> Dict[str, Any]:
    status = runtime_status()
    return {
        "status": "ok" if status.get("ffmpeg_available") else "degraded",
        "ffmpeg_available": "1" if status.get("ffmpeg_available") else "0",
        "ffmpeg_bin": str(status.get("ffmpeg_bin", "ffmpeg")),
    }


_NAV_ICONS = {
    "home": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 11.5L12 4l9 7.5"/><path d="M5 10v10h14V10"/></svg>',
    "overview": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>',
    "upload": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/></svg>',
    "jobs": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 6h18M3 12h18M3 18h18"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="6" cy="12" r="1" fill="currentColor"/><circle cx="6" cy="18" r="1" fill="currentColor"/></svg>',
}


def _shell(title: str, active: str, content: str, script: str = "") -> str:
    def nav_link(path: str, label: str, key: str) -> str:
        cls = "nav-item active" if active == key else "nav-item"
        icon = _NAV_ICONS.get(key, "")
        return f'<a class="{cls}" href="{path}"><span class="nav-icon">{icon}</span><span>{label}</span></a>'

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #07090f;
      --bg-elev-0: #0a0d15;
      --bg-elev-1: #0f131d;
      --bg-elev-2: #141926;
      --bg-elev-3: #1a2030;
      --text: #e8edf7;
      --text-dim: #98a2b8;
      --text-muted: #64708a;
      --border: #1f2536;
      --border-strong: #2a3247;
      --accent: #00e0ff;
      --accent-2: #4f7cff;
      --accent-soft: rgba(0, 224, 255, 0.12);
      --ok: #10b981;
      --ok-soft: rgba(16, 185, 129, 0.14);
      --warn: #f59e0b;
      --warn-soft: rgba(245, 158, 11, 0.14);
      --err: #ef4444;
      --err-soft: rgba(239, 68, 68, 0.14);
      --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 40px rgba(0,0,0,0.35);
      --radius: 12px;
      --radius-sm: 8px;
      --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      font-family: 'Inter', system-ui, -apple-system, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      background-image:
        radial-gradient(800px 400px at 12% -10%, rgba(0,224,255,0.06), transparent 60%),
        radial-gradient(700px 360px at 100% 0%, rgba(79,124,255,0.05), transparent 65%),
        linear-gradient(180deg, #06080d 0%, #07090f 100%);
      color: var(--text);
      font-feature-settings: "ss01", "cv11";
      letter-spacing: -0.005em;
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ color: #7defff; }}
    code, .mono {{ font-family: var(--mono); }}

    .layout {{ display: grid; grid-template-columns: 248px 1fr; min-height: 100vh; }}
    .sidebar {{
      background: linear-gradient(180deg, rgba(10,13,21,0.95), rgba(7,9,15,0.95));
      border-right: 1px solid var(--border);
      padding: 22px 14px 24px;
      position: sticky; top: 0; height: 100vh; overflow-y: auto;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; padding: 4px 8px 18px; border-bottom: 1px solid var(--border); margin-bottom: 14px; }}
    .brand-mark {{ width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #00e0ff 0%, #4f7cff 100%); position: relative; box-shadow: 0 4px 14px rgba(0,224,255,0.35); }}
    .brand-mark::after {{ content: ""; position: absolute; inset: 5px; border-radius: 4px; background: #06080d; }}
    .brand-mark::before {{ content: ""; position: absolute; inset: 9px; border-radius: 2px; background: linear-gradient(135deg, #00e0ff, #4f7cff); }}
    .brand-text {{ display: flex; flex-direction: column; line-height: 1.1; }}
    .brand-title {{ font-weight: 700; font-size: 14px; letter-spacing: 0.01em; }}
    .brand-sub {{ color: var(--text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; margin-top: 3px; font-weight: 500; }}

    .nav-section {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.16em; color: var(--text-muted); padding: 14px 10px 8px; font-weight: 600; }}
    .nav-item {{
      display: flex; align-items: center; gap: 10px;
      color: var(--text-dim); text-decoration: none;
      padding: 9px 10px; border-radius: 8px; margin-bottom: 2px;
      font-size: 13.5px; font-weight: 500;
      border: 1px solid transparent;
      transition: background 120ms, color 120ms, border-color 120ms;
    }}
    .nav-item:hover {{ background: rgba(255,255,255,0.025); color: var(--text); }}
    .nav-item.active {{ background: var(--accent-soft); color: var(--text); border-color: rgba(0,224,255,0.18); }}
    .nav-item.active .nav-icon {{ color: var(--accent); }}
    .nav-icon {{ width: 16px; height: 16px; display: inline-flex; color: var(--text-muted); }}
    .nav-icon svg {{ width: 100%; height: 100%; }}

    .sidebar-footer {{ position: absolute; bottom: 18px; left: 14px; right: 14px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg-elev-1); font-size: 11px; color: var(--text-muted); }}
    .sidebar-footer .build {{ font-family: var(--mono); color: var(--text-dim); margin-top: 2px; }}

    main {{ padding: 0; }}
    .topbar {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 28px; border-bottom: 1px solid var(--border);
      background: rgba(7,9,15,0.6); backdrop-filter: blur(8px);
      position: sticky; top: 0; z-index: 5;
    }}
    .breadcrumb {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-muted); }}
    .breadcrumb b {{ color: var(--text); font-weight: 600; }}
    .breadcrumb .sep {{ opacity: 0.4; }}
    .topbar-actions {{ display: flex; align-items: center; gap: 12px; }}
    .status-chip {{ display: inline-flex; align-items: center; gap: 7px; padding: 5px 10px; border: 1px solid var(--border); background: var(--bg-elev-1); border-radius: 999px; font-size: 11.5px; color: var(--text-dim); font-weight: 500; }}
    .status-dot {{ width: 7px; height: 7px; border-radius: 999px; background: var(--ok); box-shadow: 0 0 0 0 rgba(16,185,129,0.6); animation: pulse 2s infinite; }}
    .status-chip.warn .status-dot {{ background: var(--warn); animation-name: pulseWarn; }}
    @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(16,185,129,0.55); }} 70% {{ box-shadow: 0 0 0 7px rgba(16,185,129,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(16,185,129,0); }} }}
    @keyframes pulseWarn {{ 0% {{ box-shadow: 0 0 0 0 rgba(245,158,11,0.55); }} 70% {{ box-shadow: 0 0 0 7px rgba(245,158,11,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(245,158,11,0); }} }}

    .page {{ padding: 26px 28px 60px; max-width: 1500px; }}
    .page-head {{ margin-bottom: 22px; }}
    .page-title {{ font-size: 24px; font-weight: 700; margin: 0; letter-spacing: -0.02em; }}
    .page-sub {{ color: var(--text-dim); font-size: 13.5px; margin: 5px 0 0; max-width: 720px; }}

    .muted {{ color: var(--text-dim); }}
    .dim {{ color: var(--text-muted); }}
    .ok {{ color: var(--ok); }} .warn {{ color: var(--warn); }} .err {{ color: var(--err); }}

    .card {{
      background: linear-gradient(180deg, var(--bg-elev-1), var(--bg-elev-0));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px;
      margin-bottom: 14px;
      box-shadow: var(--shadow);
    }}
    .card h3 {{ margin: 0 0 12px; font-size: 13px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; gap: 8px; }}
    .card h3 .tag {{ font-family: var(--mono); font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--bg-elev-2); color: var(--text-muted); border: 1px solid var(--border); text-transform: none; letter-spacing: 0; }}

    .grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
    .grid-2 {{ display: grid; gap: 14px; grid-template-columns: repeat(2, 1fr); }}
    @media (max-width: 1100px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}

    .kpi {{ position: relative; overflow: hidden; padding: 16px 18px 14px; }}
    .kpi-label {{ display: flex; align-items: center; gap: 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-muted); font-weight: 600; margin-bottom: 10px; }}
    .kpi-icon {{ width: 26px; height: 26px; border-radius: 7px; background: var(--bg-elev-2); display: inline-flex; align-items: center; justify-content: center; color: var(--text-dim); border: 1px solid var(--border); }}
    .kpi-icon svg {{ width: 14px; height: 14px; }}
    .kpi-value {{ font-family: var(--mono); font-size: 30px; font-weight: 600; letter-spacing: -0.02em; line-height: 1; color: var(--text); }}
    .kpi-foot {{ font-size: 11.5px; color: var(--text-muted); margin-top: 6px; }}
    .kpi.accent .kpi-value {{ color: var(--accent); }}
    .kpi.ok .kpi-value {{ color: var(--ok); }}
    .kpi.warn .kpi-value {{ color: var(--warn); }}
    .kpi.err .kpi-value {{ color: var(--err); }}

    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }}
    th {{ color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; padding-top: 4px; padding-bottom: 10px; }}
    tbody tr {{ transition: background 100ms; }}
    tbody tr:hover {{ background: rgba(255,255,255,0.02); }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    td.mono {{ font-family: var(--mono); font-size: 12px; color: var(--text-dim); }}

    input[type="file"], input[type="search"], input[type="text"] {{
      background: var(--bg-elev-0); color: var(--text);
      border: 1px solid var(--border); border-radius: var(--radius-sm);
      padding: 10px 12px; font-size: 13.5px; font-family: inherit;
      transition: border-color 120ms, box-shadow 120ms;
    }}
    input[type="file"]:focus, input[type="search"]:focus, input[type="text"]:focus {{
      outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft);
    }}

    button {{
      border: 1px solid transparent; border-radius: var(--radius-sm);
      padding: 9px 14px; cursor: pointer; font-weight: 600; font-size: 13px;
      background: var(--accent); color: #051018; font-family: inherit;
      transition: transform 120ms, box-shadow 120ms, background 120ms;
      display: inline-flex; align-items: center; gap: 7px;
    }}
    button:hover {{ background: #2af0ff; }}
    button.secondary {{ background: var(--bg-elev-2); color: var(--text); border-color: var(--border-strong); }}
    button.secondary:hover {{ background: var(--bg-elev-3); }}
    button.ghost {{ background: transparent; color: var(--text-dim); border-color: var(--border); }}
    button.ghost:hover {{ background: var(--bg-elev-1); color: var(--text); }}

    .btn-cta {{
      display: inline-flex; align-items: center; gap: 9px;
      background: linear-gradient(135deg, #00e0ff 0%, #4f7cff 100%);
      color: #04111a; font-weight: 700; border: 0;
      border-radius: 10px; padding: 12px 18px; font-size: 13.5px;
      box-shadow: 0 8px 28px rgba(0,224,255,0.28), 0 0 0 1px rgba(0,224,255,0.35) inset;
      transition: transform 140ms, box-shadow 140ms;
    }}
    .btn-cta:hover {{ transform: translateY(-1px); color: #04111a; box-shadow: 0 12px 36px rgba(0,224,255,0.4); }}
    .btn-cta-wrap {{ display: inline-block; }}
    .btn-cta-wrap.pulse {{ animation: pulseGlow 2s infinite; }}
    @keyframes pulseGlow {{ 0%, 100% {{ filter: drop-shadow(0 0 0 rgba(0,224,255,0)); }} 50% {{ filter: drop-shadow(0 0 12px rgba(0,224,255,0.5)); }} }}

    .share-row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .share-input {{ flex: 1; min-width: 280px; background: var(--bg-elev-0); color: var(--text-dim); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 12px; font-family: var(--mono); font-size: 12px; }}
    .button-chip {{ border: 1px solid var(--border); background: var(--bg-elev-1); color: var(--text); border-radius: var(--radius-sm); padding: 8px 12px; cursor: pointer; font-weight: 500; font-size: 12.5px; transition: background 120ms, border-color 120ms; }}
    .button-chip:hover {{ background: var(--bg-elev-2); border-color: var(--border-strong); }}

    .pill {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 10px; font-size: 11.5px; font-weight: 600; letter-spacing: 0.02em; border: 1px solid transparent; text-transform: capitalize; }}
    .pill::before {{ content: ""; width: 6px; height: 6px; border-radius: 999px; background: currentColor; }}
    .pill.queued {{ background: var(--bg-elev-2); color: var(--text-dim); border-color: var(--border-strong); }}
    .pill.running {{ background: var(--warn-soft); color: var(--warn); border-color: rgba(245,158,11,0.25); }}
    .pill.completed {{ background: var(--ok-soft); color: var(--ok); border-color: rgba(16,185,129,0.25); }}
    .pill.failed {{ background: var(--err-soft); color: var(--err); border-color: rgba(239,68,68,0.25); }}

    .progress-track {{ width: 100%; height: 6px; border-radius: 999px; background: var(--bg-elev-2); overflow: hidden; border: 1px solid var(--border); }}
    .progress-fill {{ height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); transition: width .35s ease; box-shadow: 0 0 12px rgba(0,224,255,0.35); }}

    .timeline {{ list-style: none; padding: 0; margin: 14px 0 0; position: relative; }}
    .timeline::before {{ content: ""; position: absolute; left: 5px; top: 8px; bottom: 8px; width: 1px; background: var(--border); }}
    .timeline li {{ display: flex; align-items: center; gap: 12px; padding: 7px 0; color: var(--text-muted); font-size: 13px; position: relative; }}
    .timeline li.done {{ color: var(--text); }}
    .dot {{ width: 11px; height: 11px; border-radius: 999px; background: var(--bg-elev-2); border: 2px solid var(--border-strong); flex-shrink: 0; z-index: 1; }}
    .timeline li.done .dot {{ background: var(--ok); border-color: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); }}

    pre {{ background: var(--bg-elev-0); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; white-space: pre-wrap; word-break: break-word; font-family: var(--mono); font-size: 12px; line-height: 1.55; color: var(--text-dim); max-height: 360px; overflow: auto; }}
    pre::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    pre::-webkit-scrollbar-thumb {{ background: var(--border-strong); border-radius: 999px; }}

    .markdown-host {{
      background: var(--bg-elev-0);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 12px 14px;
      max-height: 360px;
      overflow: auto;
      color: var(--text-dim);
      font-size: 12.5px;
      line-height: 1.6;
    }}
    .markdown-host h1, .markdown-host h2, .markdown-host h3 {{
      color: var(--text);
      margin: 0 0 8px;
      letter-spacing: -0.01em;
    }}
    .markdown-host h1 {{ font-size: 18px; }}
    .markdown-host h2 {{ font-size: 16px; }}
    .markdown-host h3 {{ font-size: 14px; }}
    .markdown-host p {{ margin: 0 0 10px; }}
    .markdown-host ul {{ margin: 0 0 10px 18px; padding: 0; }}
    .markdown-host li {{ margin: 0 0 6px; }}
    .markdown-host code {{
      font-family: var(--mono);
      background: var(--bg-elev-2);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 1px 5px;
      color: var(--text);
    }}
    .markdown-host pre {{
      margin: 0 0 10px;
      max-height: none;
    }}
    .fullscreen-overlay {{
      position: fixed;
      inset: 0;
      background: rgba(4, 7, 13, 0.86);
      backdrop-filter: blur(6px);
      z-index: 50;
      display: none;
      align-items: stretch;
      justify-content: center;
      padding: 20px;
    }}
    .fullscreen-panel {{
      width: min(1200px, 100%);
      height: 100%;
      background: linear-gradient(180deg, var(--bg-elev-1), var(--bg-elev-0));
      border: 1px solid var(--border-strong);
      border-radius: 14px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .fullscreen-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: var(--bg-elev-1);
    }}
    .fullscreen-title {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      letter-spacing: 0.01em;
    }}
    .fullscreen-content {{
      flex: 1;
      padding: 14px;
      overflow: auto;
    }}
    .fullscreen-content .markdown-host {{
      max-height: none;
      min-height: 100%;
      font-size: 13.5px;
      line-height: 1.72;
    }}

    video {{ width: 100%; border-radius: var(--radius-sm); border: 1px solid var(--border); background: #000; }}
    .video-grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .video-grid > div {{ background: var(--bg-elev-0); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px; }}
    .video-grid .clip-name {{ font-family: var(--mono); font-size: 11px; color: var(--text-muted); margin-bottom: 8px; word-break: break-all; }}

    /* Hero */
    .hero {{
      padding: 32px 30px 30px;
      border-radius: 16px;
      background:
        radial-gradient(600px 240px at 90% -30%, rgba(0,224,255,0.18), transparent 70%),
        radial-gradient(500px 220px at 0% 100%, rgba(79,124,255,0.14), transparent 70%),
        linear-gradient(180deg, var(--bg-elev-1), var(--bg-elev-0));
      border: 1px solid var(--border);
      margin-bottom: 18px;
      position: relative; overflow: hidden;
    }}
    .hero::after {{
      content: ""; position: absolute; inset: 0;
      background-image: linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 40px 40px; pointer-events: none; opacity: 0.4;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.6), transparent 80%);
    }}
    .hero > * {{ position: relative; z-index: 1; }}
    .hero-eyebrow {{ display: inline-flex; align-items: center; gap: 8px; padding: 5px 11px; border-radius: 999px; background: var(--accent-soft); border: 1px solid rgba(0,224,255,0.25); color: var(--accent); font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 16px; }}
    .hero h1 {{ margin: 0 0 12px; font-size: 36px; font-weight: 700; letter-spacing: -0.025em; line-height: 1.15; max-width: 760px; }}
    .hero h1 .accent {{ background: linear-gradient(135deg, #00e0ff, #4f7cff); -webkit-background-clip: text; background-clip: text; color: transparent; }}
    .hero p {{ margin: 0 0 20px; color: var(--text-dim); max-width: 680px; font-size: 14.5px; line-height: 1.6; }}
    .hero-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}

    .feature-list {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    .feature {{ padding: 18px; background: var(--bg-elev-1); border: 1px solid var(--border); border-radius: var(--radius); }}
    .feature-icon {{ width: 32px; height: 32px; border-radius: 8px; background: var(--accent-soft); border: 1px solid rgba(0,224,255,0.2); display: inline-flex; align-items: center; justify-content: center; color: var(--accent); margin-bottom: 12px; }}
    .feature-icon svg {{ width: 16px; height: 16px; }}
    .feature h4 {{ margin: 0 0 6px; font-size: 14px; font-weight: 600; }}
    .feature p {{ margin: 0; font-size: 12.5px; color: var(--text-muted); line-height: 1.55; }}

    .upload-dropzone {{
      border: 1.5px dashed var(--border-strong);
      border-radius: var(--radius);
      padding: 36px 24px;
      background: linear-gradient(180deg, rgba(0,224,255,0.025), rgba(79,124,255,0.015));
      text-align: center;
      transition: border-color 160ms, background 160ms;
    }}
    .upload-dropzone:hover {{ border-color: var(--accent); background: var(--accent-soft); }}
    .upload-dropzone .drop-icon {{ width: 48px; height: 48px; margin: 0 auto 14px; border-radius: 12px; background: var(--bg-elev-2); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; color: var(--accent); }}
    .upload-dropzone .drop-icon svg {{ width: 22px; height: 22px; }}
    .upload-dropzone h3 {{ margin: 0 0 6px; font-size: 16px; text-transform: none; letter-spacing: 0; color: var(--text); }}
    .upload-dropzone .formats {{ font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); margin-bottom: 18px; }}

    .split {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; }}
    @media (max-width: 1100px) {{ .split {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }}
      .sidebar-footer {{ display: none; }}
      .page, .topbar {{ padding-left: 18px; padding-right: 18px; }}
    }}

    .meta-row {{ display: flex; flex-wrap: wrap; gap: 18px; font-size: 12.5px; color: var(--text-muted); }}
    .meta-row .label {{ color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; font-size: 10.5px; font-weight: 600; margin-right: 6px; }}
    .meta-row .value {{ font-family: var(--mono); color: var(--text-dim); }}

    .section-actions {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }}
    .section-actions .grow {{ flex: 1; }}

    .empty-state {{ padding: 40px 20px; text-align: center; color: var(--text-muted); font-size: 13px; }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"></div>
        <div class="brand-text">
          <span class="brand-title">RailSight</span>
          <span class="brand-sub">Operations OS</span>
        </div>
      </div>
      <div class="nav-section">Workspace</div>
      {nav_link("/", "Dashboard", "home")}
      {nav_link("/overview", "Overview", "overview")}
      <div class="nav-section">Pipeline</div>
      {nav_link("/upload", "New Analysis", "upload")}
      {nav_link("/jobs-ui", "Jobs", "jobs")}
      <div class="sidebar-footer">
        <div>Railway Video Intelligence</div>
        <div class="build">v0.1.0 · build 2026.04</div>
      </div>
    </aside>
    <main>
      <div class="topbar">
        <div class="breadcrumb">
          <span>RailSight</span>
          <span class="sep">/</span>
          <b>{escape(title.split(" - ")[0])}</b>
        </div>
        <div class="topbar-actions">
          <span class="status-chip" id="systemStatusChip"><span class="status-dot"></span><span id="systemStatusText">System operational</span></span>
        </div>
      </div>
      <div class="page">{content}</div>
    </main>
  </div>
  <script>
    function h(v) {{
      return String(v ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}
    (async function pollHealth() {{
      try {{
        const res = await fetch('/health');
        const data = await res.json();
        const chip = document.getElementById('systemStatusChip');
        const txt = document.getElementById('systemStatusText');
        if (!chip || !txt) return;
        if (data.status === 'ok') {{
          chip.classList.remove('warn');
          txt.textContent = 'System operational';
        }} else {{
          chip.classList.add('warn');
          txt.textContent = 'Degraded · ffmpeg missing';
        }}
      }} catch (e) {{}}
    }})();
    {script}
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home_page() -> str:
    content = """
      <section class="hero">
        <span class="hero-eyebrow"><span style="width:6px;height:6px;border-radius:999px;background:#00e0ff;display:inline-block;box-shadow:0 0 8px #00e0ff;"></span>Industrial Video Intelligence Platform</span>
        <h1>Turn surveillance footage into <span class="accent">audit-ready safety intelligence.</span></h1>
        <p>RailSight ingests hours of railway video and produces event timelines, fatigue analytics, evidence clips, and operations-grade reports — without the manual scrub.</p>
        <div class="hero-actions">
          <a href="/upload"><button class="btn-cta">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
            Launch New Analysis
          </button></a>
          <a href="/overview"><button class="secondary">View Operations Overview</button></a>
        </div>
      </section>
      <div class="feature-list">
        <div class="feature">
          <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg></div>
          <h4>End-to-End Pipeline</h4>
          <p>Ingest, detect, segment, clip, transcribe, and summarize in a single deterministic workflow.</p>
        </div>
        <div class="feature">
          <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3v18h18"/><path d="M7 14l4-4 4 4 5-7"/></svg></div>
          <h4>Live Operations Dashboard</h4>
          <p>Track job status, processing timeline, and safety alerts with real-time progress streaming.</p>
        </div>
        <div class="feature">
          <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg></div>
          <h4>Evidence-Ready Output</h4>
          <p>Source video, auto-generated clips, transcripts, and final reports — all in one shareable surface.</p>
        </div>
        <div class="feature">
          <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 10h10M7 14h6"/></svg></div>
          <h4>Built for Control Rooms</h4>
          <p>Designed for safety teams, ops control, and incident review analysts who need answers fast.</p>
        </div>
      </div>
    """
    return _shell("Dashboard - RailSight", "home", content)


@app.get("/overview", response_class=HTMLResponse)
def overview_page() -> str:
    status = runtime_status()
    jobs = list_job_records(limit=100)
    counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
    for j in jobs:
        st = str(j.get("status", "")).lower()
        if st in counts:
            counts[st] += 1
    ffmpeg_ok = bool(status.get("ffmpeg_available"))
    ffmpeg_bin = escape(str(status.get("ffmpeg_bin", "ffmpeg")))
    success_rate = (counts["completed"] / len(jobs) * 100.0) if jobs else 0.0
    content = f"""
      <div class="page-head">
        <h1 class="page-title">Operations Overview</h1>
        <p class="page-sub">Real-time pipeline health, throughput, and recent processing activity across the analysis fleet.</p>
      </div>
      <div class="grid">
        <div class="card kpi accent">
          <div class="kpi-label">
            <span class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg></span>
            Total Jobs
          </div>
          <div class="kpi-value">{len(jobs)}</div>
          <div class="kpi-foot">All-time tracked runs</div>
        </div>
        <div class="card kpi ok">
          <div class="kpi-label">
            <span class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12l5 5L20 7"/></svg></span>
            Completed
          </div>
          <div class="kpi-value">{counts['completed']}</div>
          <div class="kpi-foot">{success_rate:.1f}% success rate</div>
        </div>
        <div class="card kpi warn">
          <div class="kpi-label">
            <span class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>
            In Flight
          </div>
          <div class="kpi-value">{counts['running'] + counts['queued']}</div>
          <div class="kpi-foot">{counts['running']} running · {counts['queued']} queued</div>
        </div>
        <div class="card kpi err">
          <div class="kpi-label">
            <span class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg></span>
            Failed
          </div>
          <div class="kpi-value">{counts['failed']}</div>
          <div class="kpi-foot">Requires review</div>
        </div>
      </div>
      <div class="grid-2" style="margin-top:14px;">
        <div class="card">
          <h3>Runtime Health <span class="tag">{'healthy' if ffmpeg_ok else 'degraded'}</span></h3>
          <div class="meta-row" style="margin-bottom:10px;">
            <div><span class="label">FFmpeg</span><span class="value {'ok' if ffmpeg_ok else 'err'}">{'Available' if ffmpeg_ok else 'Missing'}</span></div>
            <div><span class="label">Binary</span><span class="value">{ffmpeg_bin}</span></div>
          </div>
          <p class="dim" style="margin:0;font-size:12.5px;line-height:1.55;">FFmpeg powers frame extraction, clip generation, and transcoding. A missing binary blocks the full pipeline downstream.</p>
        </div>
        <div class="card">
          <h3>Quick Actions</h3>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a href="/upload"><button>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 5v14M5 12h14"/></svg>
              New Analysis
            </button></a>
            <a href="/jobs-ui"><button class="secondary">View All Jobs</button></a>
            <a href="/health" target="_blank"><button class="ghost">Health Endpoint</button></a>
          </div>
        </div>
      </div>
    """
    return _shell("Overview - RailSight", "overview", content)


@app.get("/upload", response_class=HTMLResponse)
def upload_page() -> str:
    content = """
      <div class="page-head">
        <h1 class="page-title">New Analysis</h1>
        <p class="page-sub">Submit surveillance footage to the intelligence pipeline. Frame extraction, detection, and reporting run automatically.</p>
      </div>
      <div class="split">
        <div class="card">
          <h3>Source Footage <span class="tag">step 1</span></h3>
          <div class="upload-dropzone">
            <div class="drop-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/></svg>
            </div>
            <h3>Drop video file or browse</h3>
            <div class="formats">MP4 · MOV · AVI · MKV · WEBM</div>
            <input type="file" id="videoFile" accept="video/*" style="margin-bottom:14px;" />
            <div>
              <button onclick="uploadVideo()" class="btn-cta" id="uploadBtn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
                Run Industrial Analysis
              </button>
            </div>
            <div id="uploadStatus" class="dim" style="margin-top:14px;font-size:12.5px;font-family:var(--mono);"></div>
          </div>
        </div>
        <div class="card">
          <h3>Pipeline Stages <span class="tag">automated</span></h3>
          <ul class="timeline" style="margin-top:6px;">
            <li class="done"><span class="dot"></span><span>Frame extraction &amp; object detection</span></li>
            <li class="done"><span class="dot"></span><span>Fatigue &amp; behavior signal analysis</span></li>
            <li class="done"><span class="dot"></span><span>Clip segmentation &amp; transcription</span></li>
            <li class="done"><span class="dot"></span><span>Operational report generation</span></li>
          </ul>
          <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--border);">
            <div class="meta-row">
              <div><span class="label">Max upload</span><span class="value">1024 MB</span></div>
              <div><span class="label">Avg runtime</span><span class="value">~3-8 min / hr</span></div>
            </div>
          </div>
        </div>
      </div>
    """
    script = """
      async function uploadVideo() {
        const fileEl = document.getElementById('videoFile');
        const statusEl = document.getElementById('uploadStatus');
        const btn = document.getElementById('uploadBtn');
        if (!fileEl.files.length) { statusEl.textContent = '> select a video file first'; return; }
        const fd = new FormData();
        fd.append('file', fileEl.files[0]);
        if (btn) { btn.disabled = true; btn.style.opacity = '0.7'; }
        statusEl.textContent = '> uploading ' + fileEl.files[0].name + '...';
        try {
          const res = await fetch('/jobs', { method: 'POST', body: fd });
          if (!res.ok) {
            const err = await res.text();
            statusEl.textContent = '> upload failed: ' + err;
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
            return;
          }
          const job = await res.json();
          statusEl.textContent = '> job queued · id ' + (job.id || '');
          window.location.href = '/jobs-ui/' + encodeURIComponent(job.id);
        } catch (e) {
          statusEl.textContent = '> network error: ' + e.message;
          if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        }
      }
    """
    return _shell("New Analysis - RailSight", "upload", content, script)


@app.get("/jobs-ui", response_class=HTMLResponse)
def jobs_page() -> str:
    rows = list_job_records(limit=200)
    table_rows = []
    for row in rows:
        job_id = escape(str(row.get("id", "")))
        filename = escape(str(row.get("filename", "")))
        status = escape(str(row.get("status", "")))
        created = escape(str(row.get("created_at", "")))
        short_id = job_id[:8]
        table_rows.append(
            f"""
            <tr>
              <td class="mono"><a href="/jobs-ui/{job_id}">{short_id}</a></td>
              <td style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{filename}</td>
              <td><span class="pill {status.lower()}">{status}</span></td>
              <td class="mono">{created}</td>
              <td style="text-align:right;"><a href="/jobs-ui/{job_id}" class="dim" style="font-size:12px;">Open &rarr;</a></td>
            </tr>
            """
        )
    body = (
        "".join(table_rows)
        if table_rows
        else '<tr><td colspan="5"><div class="empty-state">No jobs yet — start a <a href="/upload">new analysis</a>.</div></td></tr>'
    )
    content = f"""
      <div class="page-head">
        <h1 class="page-title">Jobs</h1>
        <p class="page-sub">Browse, search, and open every analysis run processed by the pipeline.</p>
      </div>
      <div class="card">
        <div class="section-actions">
          <input type="search" id="jobFilter" placeholder="Search by filename, id, or status..." oninput="filterJobs()" style="min-width:280px;" class="grow" />
          <a href="/upload"><button>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 5v14M5 12h14"/></svg>
            New Analysis
          </button></a>
        </div>
        <table id="jobsTable">
          <thead><tr><th>Job ID</th><th>Filename</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    """
    script = """
      function filterJobs() {
        const q = (document.getElementById('jobFilter').value || '').toLowerCase();
        const rows = document.querySelectorAll('#jobsTable tbody tr');
        rows.forEach(r => {
          const txt = (r.textContent || '').toLowerCase();
          r.style.display = txt.includes(q) ? '' : 'none';
        });
      }
    """
    return _shell("Jobs - RailSight", "jobs", content, script)


@app.get("/jobs-ui/{job_id}", response_class=HTMLResponse)
def job_details_page(job_id: str) -> str:
    safe_job_id = escape(job_id)
    short_id = safe_job_id[:8]
    content = f"""
      <div class="page-head" style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
        <div>
          <h1 class="page-title">Job <span class="mono" style="font-size:18px;color:var(--text-dim);font-weight:500;">#{short_id}</span></h1>
          <p class="page-sub">Live tracking, artifacts, and evidence for analysis run <code class="mono" style="color:var(--text-dim);">{safe_job_id}</code></p>
        </div>
        <a href="/jobs-ui"><button class="ghost">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          All Jobs
        </button></a>
      </div>
      <div id="jobSummary" class="card"><div class="dim">Loading job...</div></div>
      <div id="reportCtaCard" class="card"><div class="dim">Preparing report actions...</div></div>
      <div id="shareReportCard" class="card"><h3>Share Report</h3><p class="dim" style="margin:0;font-size:13px;">Share options will appear once the report is generated.</p></div>
      <div class="grid-2">
        <div class="card">
          <h3>Source Footage <span class="tag">original</span></h3>
          <video id="sourceVideoPlayer" controls preload="metadata"></video>
        </div>
        <div class="card">
          <h3>Processing Timeline <span class="tag" id="progressTag">running</span></h3>
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:10px;">
            <span id="progressLabel" class="dim" style="font-size:13px;">Preparing...</span>
            <b id="progressPercent" class="mono" style="font-size:22px;color:var(--accent);">0%</b>
          </div>
          <div class="progress-track"><div id="progressFill" class="progress-fill"></div></div>
          <ul id="timelineList" class="timeline"><li><span class="dot"></span><span>Loading timeline...</span></li></ul>
        </div>
      </div>
      <div class="grid-2">
        <div id="alertsCard" class="card"><h3>Safety Alerts <span class="tag">events</span></h3><pre>Loading...</pre></div>
        <div id="metricsCard" class="card"><h3>Detection &amp; Fatigue Metrics <span class="tag">summary</span></h3><pre>Loading...</pre></div>
      </div>
      <div id="clipsCard" class="card">
        <h3>Generated Evidence Clips <span class="tag" id="clipsCount">0</span></h3>
        <div class="section-actions">
          <button id="clipsPrevBtn" class="button-chip" type="button">← Previous</button>
          <span id="clipsPageInfo" class="dim mono">Page 1 / 1</span>
          <button id="clipsNextBtn" class="button-chip" type="button">Next →</button>
        </div>
        <div id="clipsContainer"><div class="empty-state">Loading...</div></div>
      </div>
      <div class="grid-2">
        <div id="summaryCard" class="card">
          <h3>Video Summary <span class="tag">qwen</span></h3>
          <div class="section-actions">
            <div class="grow"></div>
            <button id="summaryFullscreenBtn" class="button-chip" type="button">Fullscreen</button>
          </div>
          <div class="markdown-host"><div class="dim">Loading...</div></div>
        </div>
      </div>
      <div id="clipSummariesCard" class="card">
        <h3>Per-Clip Summaries <span class="tag">qwen</span></h3>
        <div class="section-actions">
          <button id="clipSummaryPrevBtn" class="button-chip" type="button">← Previous</button>
          <span id="clipSummaryPageInfo" class="dim mono">Clip 0 / 0</span>
          <button id="clipSummaryNextBtn" class="button-chip" type="button">Next →</button>
          <button id="clipSummaryFullscreenBtn" class="button-chip" type="button">Fullscreen</button>
        </div>
        <div class="markdown-host"><div class="dim">Loading...</div></div>
      </div>
      <div id="transcriptsCard" class="card"><h3>Transcripts <span class="tag">audio</span></h3><pre>Loading...</pre></div>
      <div id="markdownFullscreen" class="fullscreen-overlay">
        <div class="fullscreen-panel">
          <div class="fullscreen-header">
            <div id="fullscreenTitle" class="fullscreen-title">Summary</div>
            <button class="button-chip" type="button" onclick="closeFullscreenReader()">Close</button>
          </div>
          <div class="fullscreen-content">
            <div id="fullscreenMarkdown" class="markdown-host"></div>
          </div>
        </div>
      </div>
    """
    script = f"""
      const JOB_ID = {repr(job_id)};
      const CLIPS_PER_PAGE = 10;
      let clipsCurrentPage = 1;
      let clipsCache = [];
      let clipSummariesCache = [];
      let clipSummaryCurrentIndex = 1;
      let summaryWholeHtmlCache = '';
      function statusPill(status) {{
        const s = (status || '').toLowerCase();
        return `<span class="pill ${{h(s)}}">${{h(status || '—')}}</span>`;
      }}
      function fmtDate(s) {{
        if (!s) return '—';
        return s;
      }}
      function inlineMd(text) {{
        return h(text || '')
          .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
          .replace(/`([^`]+)`/g, '<code>$1</code>');
      }}
      function markdownToHtml(markdown) {{
        const src = String(markdown || '').replace(/\\r\\n/g, '\\n');
        if (!src.trim()) return '';
        const lines = src.split('\\n');
        let out = [];
        let inCode = false;
        let inList = false;
        let para = [];
        const flushPara = () => {{
          if (!para.length) return;
          out.push(`<p>${{inlineMd(para.join(' '))}}</p>`);
          para = [];
        }};
        const closeList = () => {{
          if (inList) {{
            out.push('</ul>');
            inList = false;
          }}
        }};
        for (const lineRaw of lines) {{
          const line = String(lineRaw || '');
          const trimmed = line.trim();
          if (trimmed.startsWith('```')) {{
            flushPara();
            closeList();
            if (!inCode) {{
              inCode = true;
              out.push('<pre><code>');
            }} else {{
              inCode = false;
              out.push('</code></pre>');
            }}
            continue;
          }}
          if (inCode) {{
            out.push(`${{h(line)}}\\n`);
            continue;
          }}
          if (!trimmed) {{
            flushPara();
            closeList();
            continue;
          }}
          const h3 = trimmed.match(/^###\\s+(.+)/);
          if (h3) {{
            flushPara();
            closeList();
            out.push(`<h3>${{inlineMd(h3[1])}}</h3>`);
            continue;
          }}
          const h2 = trimmed.match(/^##\\s+(.+)/);
          if (h2) {{
            flushPara();
            closeList();
            out.push(`<h2>${{inlineMd(h2[1])}}</h2>`);
            continue;
          }}
          const h1 = trimmed.match(/^#\\s+(.+)/);
          if (h1) {{
            flushPara();
            closeList();
            out.push(`<h1>${{inlineMd(h1[1])}}</h1>`);
            continue;
          }}
          const li = trimmed.match(/^-\\s+(.+)/);
          if (li) {{
            flushPara();
            if (!inList) {{
              out.push('<ul>');
              inList = true;
            }}
            out.push(`<li>${{inlineMd(li[1])}}</li>`);
            continue;
          }}
          para.push(trimmed);
        }}
        flushPara();
        closeList();
        if (inCode) out.push('</code></pre>');
        return out.join('');
      }}
      function renderMarkdownCard(selector, markdown, emptyText) {{
        const card = document.querySelector(selector);
        if (!card) return;
        const host = card.querySelector('.markdown-host');
        if (!host) return;
        const html = markdownToHtml(markdown || '');
        host.innerHTML = html || `<div class="dim">${{h(emptyText || 'Not available yet.')}}</div>`;
        return html;
      }}
      function splitClipSummaries(markdown) {{
        const src = String(markdown || '').trim();
        if (!src) return [];
        const normalized = src.replace(/^#\\s+Clip\\s+Summaries\\s*/i, '').trim();
        const marker = /^###\\s+Clip:/gm;
        const blocks = [];
        const starts = [];
        let m;
        while ((m = marker.exec(normalized)) !== null) {{
          starts.push(m.index);
        }}
        if (!starts.length) return [normalized];
        for (let i = 0; i < starts.length; i += 1) {{
          const start = starts[i];
          const end = (i + 1 < starts.length) ? starts[i + 1] : normalized.length;
          const chunk = normalized.slice(start, end).trim();
          if (chunk) blocks.push(chunk);
        }}
        return blocks;
      }}
      function renderClipsPage() {{
        const clips = Array.isArray(clipsCache) ? clipsCache : [];
        const total = clips.length;
        const pages = Math.max(1, Math.ceil(total / CLIPS_PER_PAGE));
        clipsCurrentPage = Math.max(1, Math.min(clipsCurrentPage, pages));
        const start = (clipsCurrentPage - 1) * CLIPS_PER_PAGE;
        const pageItems = clips.slice(start, start + CLIPS_PER_PAGE);
        const infoEl = document.getElementById('clipsPageInfo');
        const prevBtn = document.getElementById('clipsPrevBtn');
        const nextBtn = document.getElementById('clipsNextBtn');
        const clipsCountEl = document.getElementById('clipsCount');
        const container = document.getElementById('clipsContainer');
        if (clipsCountEl) clipsCountEl.textContent = total;
        if (infoEl) infoEl.textContent = `Page ${{clipsCurrentPage}} / ${{pages}}`;
        if (prevBtn) prevBtn.disabled = clipsCurrentPage <= 1;
        if (nextBtn) nextBtn.disabled = clipsCurrentPage >= pages;
        if (!container) return;
        container.innerHTML = pageItems.length
          ? `<div class="video-grid">${{pageItems.map(c => `
               <div>
                 <div class="clip-name">${{h(c)}}</div>
                 <video controls preload="metadata" src="/jobs/${{h(JOB_ID)}}/download?path=clips/${{encodeURIComponent(c)}}"></video>
               </div>
             `).join('')}}</div>`
          : '<div class="empty-state">No clips generated for this run.</div>';
      }}
      function renderClipSummaryPage() {{
        const host = document.querySelector('#clipSummariesCard .markdown-host');
        const infoEl = document.getElementById('clipSummaryPageInfo');
        const prevBtn = document.getElementById('clipSummaryPrevBtn');
        const nextBtn = document.getElementById('clipSummaryNextBtn');
        if (!host) return;
        const total = clipSummariesCache.length;
        if (!total) {{
          if (infoEl) infoEl.textContent = 'Clip 0 / 0';
          if (prevBtn) prevBtn.disabled = true;
          if (nextBtn) nextBtn.disabled = true;
          host.innerHTML = '<div class="dim">Per-clip summaries are not available yet.</div>';
          return;
        }}
        clipSummaryCurrentIndex = Math.max(1, Math.min(clipSummaryCurrentIndex, total));
        if (infoEl) infoEl.textContent = `Clip ${{clipSummaryCurrentIndex}} / ${{total}}`;
        if (prevBtn) prevBtn.disabled = clipSummaryCurrentIndex <= 1;
        if (nextBtn) nextBtn.disabled = clipSummaryCurrentIndex >= total;
        const markdown = clipSummariesCache[clipSummaryCurrentIndex - 1] || '';
        host.innerHTML = markdownToHtml(markdown) || '<div class="dim">Per-clip summary is empty.</div>';
      }}
      function openFullscreenReader(title, htmlContent) {{
        const overlay = document.getElementById('markdownFullscreen');
        const titleEl = document.getElementById('fullscreenTitle');
        const contentEl = document.getElementById('fullscreenMarkdown');
        if (!overlay || !titleEl || !contentEl) return;
        titleEl.textContent = String(title || 'Summary');
        contentEl.innerHTML = htmlContent || '<div class="dim">No content available.</div>';
        overlay.style.display = 'flex';
      }}
      function closeFullscreenReader() {{
        const overlay = document.getElementById('markdownFullscreen');
        if (!overlay) return;
        overlay.style.display = 'none';
      }}
      function bindDetailUiActions() {{
        const clipsPrev = document.getElementById('clipsPrevBtn');
        const clipsNext = document.getElementById('clipsNextBtn');
        const summaryPrev = document.getElementById('clipSummaryPrevBtn');
        const summaryNext = document.getElementById('clipSummaryNextBtn');
        const summaryFull = document.getElementById('summaryFullscreenBtn');
        const clipSummaryFull = document.getElementById('clipSummaryFullscreenBtn');
        if (clipsPrev) clipsPrev.onclick = () => {{ clipsCurrentPage -= 1; renderClipsPage(); }};
        if (clipsNext) clipsNext.onclick = () => {{ clipsCurrentPage += 1; renderClipsPage(); }};
        if (summaryPrev) summaryPrev.onclick = () => {{ clipSummaryCurrentIndex -= 1; renderClipSummaryPage(); }};
        if (summaryNext) summaryNext.onclick = () => {{ clipSummaryCurrentIndex += 1; renderClipSummaryPage(); }};
        if (summaryFull) summaryFull.onclick = () => {{
          const host = document.querySelector('#summaryCard .markdown-host');
          openFullscreenReader('Video Summary', host ? host.innerHTML : summaryWholeHtmlCache);
        }};
        if (clipSummaryFull) clipSummaryFull.onclick = () => {{
          const host = document.querySelector('#clipSummariesCard .markdown-host');
          openFullscreenReader('Per-Clip Summary', host ? host.innerHTML : '');
        }};
        const overlay = document.getElementById('markdownFullscreen');
        if (overlay) {{
          overlay.onclick = (evt) => {{
            if (evt.target === overlay) closeFullscreenReader();
          }};
        }}
        document.onkeydown = (evt) => {{
          if (evt && evt.key === 'Escape') closeFullscreenReader();
        }};
      }}
      async function loadJob() {{
        const [jobRes, artRes] = await Promise.all([
          fetch(`/jobs/${{encodeURIComponent(JOB_ID)}}`),
          fetch(`/jobs/${{encodeURIComponent(JOB_ID)}}/artifacts`)
        ]);
        if (!jobRes.ok) {{
          document.getElementById('jobSummary').innerHTML = '<h3>Job</h3><p class="err" style="margin:0;">Job not found.</p>';
          return;
        }}
        const job = await jobRes.json();
        const status = (job.status || '').toLowerCase();
        const isCompleted = status === 'completed';
        const isFailed = status === 'failed';
        const summary = document.getElementById('jobSummary');
        const reportCta = document.getElementById('reportCtaCard');
        const shareCard = document.getElementById('shareReportCard');

        summary.innerHTML = `
          <h3>Run Manifest <span class="tag">${{h(short_idJs(JOB_ID))}}</span></h3>
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:14px;">
            <div style="min-width:0;flex:1;">
              <div style="font-size:16px;font-weight:600;margin-bottom:4px;word-break:break-all;">${{h(job.filename || '—')}}</div>
              <div>${{statusPill(job.status)}}</div>
            </div>
          </div>
          <div class="meta-row">
            <div><span class="label">Created</span><span class="value">${{h(fmtDate(job.created_at))}}</span></div>
            <div><span class="label">Started</span><span class="value">${{h(fmtDate(job.started_at))}}</span></div>
            <div><span class="label">Finished</span><span class="value">${{h(fmtDate(job.finished_at))}}</span></div>
          </div>
          ${{job.error ? `<div style="margin-top:14px;padding:10px 12px;background:var(--err-soft);border:1px solid rgba(239,68,68,0.25);border-radius:8px;color:var(--err);font-size:12.5px;font-family:var(--mono);">${{h(job.error)}}</div>` : ''}}
        `;

        if (isCompleted) {{
          reportCta.innerHTML = `
            <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:space-between;">
              <div style="min-width:0;flex:1;">
                <h3 style="margin-bottom:6px;color:var(--ok);">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" style="vertical-align:-2px;"><path d="M5 12l5 5L20 7"/></svg>
                  Analysis Complete
                </h3>
                <p class="dim" style="margin:0;font-size:13px;">Your operational report is ready for download and review.</p>
              </div>
              <span class="btn-cta-wrap pulse">
                <a class="btn-cta" href="/jobs/${{h(JOB_ID)}}/download?path=report.txt" target="_blank">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 4v12M6 14l6 6 6-6M4 22h16"/></svg>
                  Download Final Report
                </a>
              </span>
            </div>
          `;
        }} else if (isFailed) {{
          reportCta.innerHTML = `
            <h3 style="color:var(--err);">Analysis Failed</h3>
            <p class="dim" style="margin:0;font-size:13px;">The pipeline did not complete. Inspect the error above and retry the upload.</p>
          `;
        }} else {{
          reportCta.innerHTML = `
            <h3 style="color:var(--accent);">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
              Analysis In Progress
            </h3>
            <p class="dim" style="margin:0;font-size:13px;">The report download will appear here automatically once processing finishes.</p>
          `;
        }}

        if (isCompleted) {{
          const reportUrl = `${{window.location.origin}}/jobs/${{encodeURIComponent(JOB_ID)}}/download?path=report.txt`;
          shareCard.innerHTML = `
            <h3>Share Report <span class="tag">link</span></h3>
            <p class="dim" style="margin:0 0 12px;font-size:13px;">Distribute the report URL to operations, safety, or audit teams.</p>
            <div class="share-row">
              <input id="shareReportInput" class="share-input" readonly value="${{h(reportUrl)}}" />
              <button class="button-chip" onclick="copyReportLink()">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:5px;"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>
                Copy
              </button>
              <button class="button-chip" onclick="shareReport()">Share</button>
              <a class="button-chip" href="mailto:?subject=Railway%20Safety%20Report&body=${{encodeURIComponent(reportUrl)}}">Email</a>
            </div>
            <p id="shareStatus" class="dim" style="margin-top:10px;font-size:12px;font-family:var(--mono);"></p>
          `;
        }}

        if (!artRes.ok) return;
        const art = await artRes.json();
        const alerts = (((art || {{}}).data || {{}}).alerts || {{}}).alerts || [];
        const det = (((art || {{}}).data || {{}}).detections_summary || {{}});
        const fat = (((art || {{}}).data || {{}}).fatigue_summary || {{}});
        const clips = (((art || {{}}).data || {{}}).clips || []);
        const transcriptPreviews = (((art || {{}}).data || {{}}).transcript_previews || []);
        const qwenClips = (((art || {{}}).data || {{}}).qwen_clip_summaries_md || '');
        const qwenWhole = (((art || {{}}).data || {{}}).qwen_whole_summary_md || 'Summary not available yet.');
        const progress = (art || {{}}).progress || {{percent: 0, state: 'queued', stages: []}};

        document.querySelector('#alertsCard pre').textContent = alerts.length ? JSON.stringify(alerts, null, 2) : 'No alerts recorded.';
        document.querySelector('#metricsCard pre').textContent = JSON.stringify({{detections: det, fatigue: fat}}, null, 2);
        document.querySelector('#transcriptsCard pre').textContent = transcriptPreviews.length ? JSON.stringify(transcriptPreviews, null, 2) : 'No transcripts available.';
        summaryWholeHtmlCache = renderMarkdownCard('#summaryCard', qwenWhole, 'Summary not available yet.') || '';
        clipSummariesCache = splitClipSummaries(qwenClips);
        if (clipSummaryCurrentIndex > clipSummariesCache.length) clipSummaryCurrentIndex = Math.max(1, clipSummariesCache.length);
        renderClipSummaryPage();
        document.getElementById('sourceVideoPlayer').src = `/jobs/${{h(JOB_ID)}}/source-video`;

        clipsCache = clips;
        if ((clipsCurrentPage - 1) * CLIPS_PER_PAGE >= clipsCache.length) {{
          clipsCurrentPage = Math.max(1, Math.ceil(clipsCache.length / CLIPS_PER_PAGE));
        }}
        renderClipsPage();

        const pct = Math.max(0, Math.min(100, Number(progress.percent || 0)));
        document.getElementById('progressPercent').textContent = `${{pct}}%`;
        document.getElementById('progressFill').style.width = `${{pct}}%`;
        document.getElementById('progressLabel').textContent = `State · ${{(progress.state || job.status || 'running')}}`;
        const tagEl = document.getElementById('progressTag');
        if (tagEl) tagEl.textContent = (progress.state || job.status || 'running');
        const timeline = Array.isArray(progress.stages) ? progress.stages : [];
        document.getElementById('timelineList').innerHTML = timeline.length
          ? timeline.map(s => `<li class="${{s.done ? 'done' : ''}}"><span class="dot"></span><span>${{h(s.label || s.key || '')}}</span></li>`).join('')
          : '<li><span class="dot"></span><span class="dim">Timeline not available yet.</span></li>';

        if (status === 'queued' || status === 'running') {{
          setTimeout(loadJob, 4000);
        }}
      }}
      function short_idJs(id) {{ return (id || '').slice(0, 8); }}
      async function copyReportLink() {{
        const input = document.getElementById('shareReportInput');
        const status = document.getElementById('shareStatus');
        if (!input) return;
        try {{
          await navigator.clipboard.writeText(input.value);
          if (status) status.textContent = '> link copied to clipboard';
        }} catch (err) {{
          input.select();
          document.execCommand('copy');
          if (status) status.textContent = '> link copied to clipboard';
        }}
      }}
      async function shareReport() {{
        const input = document.getElementById('shareReportInput');
        const status = document.getElementById('shareStatus');
        if (!input) return;
        if (navigator.share) {{
          try {{
            await navigator.share({{ title: 'Railway Safety Report', text: 'Sharing report link', url: input.value }});
            if (status) status.textContent = '> share dialog opened';
            return;
          }} catch (err) {{}}
        }}
        copyReportLink();
      }}
      bindDetailUiActions();
      loadJob();
    """
    return _shell(f"Job {short_id} - RailSight", "jobs", content, script)


@app.post("/jobs")
def create_job(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    if file.content_type and not str(file.content_type).lower().startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid content type")

    max_upload_mb = int(os.environ.get("APP_MAX_UPLOAD_MB", "1024"))
    max_upload_bytes = max_upload_mb * 1024 * 1024

    with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        total = 0
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_upload_bytes:
                temp_path = Path(temp.name)
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File too large (>{max_upload_mb}MB)")
            temp.write(chunk)
        temp_path = Path(temp.name)

    try:
        job = create_and_queue_job(temp_path, file.filename)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return job_to_json(job)


@app.get("/jobs")
def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> List[Dict[str, Any]]:
    rows = list_job_records(limit=limit)
    return [job_to_json(r) for r in rows]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = get_job_record(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_json(job)


@app.get("/jobs/{job_id}/artifacts")
def get_artifacts(job_id: str) -> Dict[str, Any]:
    job = get_job_record(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if str(job.get("status", "")) not in {"completed", "failed", "running", "queued"}:
        raise HTTPException(status_code=400, detail="Invalid job state")
    payload = job_artifacts(job_id)
    return payload


@app.get("/jobs/{job_id}/download")
def download_job_file(job_id: str, path: str = Query(..., min_length=1)) -> FileResponse:
    file_path = safe_job_file_path(job_id, str(path))
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), filename=file_path.name)


@app.get("/jobs/{job_id}/source-video")
def source_video(job_id: str) -> FileResponse:
    video_path = safe_uploaded_video_path(job_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Source video not found")
    return FileResponse(path=str(video_path), filename=video_path.name)
