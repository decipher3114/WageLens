"""Clear local runtime artifacts on each process start."""

from __future__ import annotations

from pathlib import Path

from wagelens.config import settings


def _sqlite_path(url: str) -> Path | None:
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", ""))
    return None


def reset_runtime_data() -> None:
    """Delete log files and SQLite database so each run starts fresh."""
    log_path = Path(settings.log_file)
    log_dir = log_path.parent
    if log_dir.exists():
        for path in log_dir.glob(f"{log_path.name}*"):
            path.unlink(missing_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    db_path = _sqlite_path(settings.database_url)
    if db_path is None:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        path.unlink(missing_ok=True)
