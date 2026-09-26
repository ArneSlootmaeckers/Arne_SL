"""Periodic maintenance: database back-ups and pruning old back-up files.

Uses sqlite3's own online backup API (Connection.backup()) — the same
mechanism as the `sqlite3 ... ".backup"` command documented in the README —
so a back-up is safe to take while the server keeps running and writing.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def create_backup(database_path: str, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"backup-{timestamp}.db"

    source = sqlite3.connect(database_path)
    try:
        dest = sqlite3.connect(backup_path)
        try:
            with dest:
                source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    return backup_path


def purge_old_backups(backup_dir: Path, retention_days: int) -> int:
    if not backup_dir.is_dir():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    for backup_file in backup_dir.glob("backup-*.db"):
        modified_at = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)
        if modified_at < cutoff:
            backup_file.unlink()
            removed += 1
    return removed
