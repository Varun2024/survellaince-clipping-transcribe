import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL,
                upload_path TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        conn.commit()


def create_job(
    db_path: Path,
    job_id: str,
    filename: str,
    upload_path: str,
    output_dir: str,
    created_at: str,
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, filename, status, upload_path, output_dir, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, filename, "queued", upload_path, output_dir, created_at),
        )
        conn.commit()


def update_job_status(
    db_path: Path,
    job_id: str,
    status: str,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                started_at = COALESCE(?, started_at),
                finished_at = COALESCE(?, finished_at),
                error = ?
            WHERE id = ?
            """,
            (status, started_at, finished_at, error, job_id),
        )
        conn.commit()


def get_job(db_path: Path, job_id: str) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(db_path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(r) for r in rows]
