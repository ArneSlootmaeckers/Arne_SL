"""Tests for automatic database back-ups and back-up pruning."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.maintenance_service import create_backup, purge_old_backups


def _make_sqlite_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO t (value) VALUES ('hallo')")
    conn.commit()
    conn.close()


def test_create_backup_produces_a_working_copy(tmp_path):
    db_path = tmp_path / "toelating.db"
    _make_sqlite_db(db_path)

    backup_path = create_backup(str(db_path), tmp_path / "backups")

    assert backup_path.exists()
    conn = sqlite3.connect(backup_path)
    rows = conn.execute("SELECT value FROM t").fetchall()
    conn.close()
    assert rows == [("hallo",)]


def test_create_backup_is_safe_while_a_writer_is_open(tmp_path):
    """The online backup API must work even with another open connection —
    that's the whole point of using it instead of a plain file copy."""
    db_path = tmp_path / "toelating.db"
    _make_sqlite_db(db_path)

    writer = sqlite3.connect(db_path)
    writer.execute("INSERT INTO t (value) VALUES ('nog een rij')")
    writer.commit()

    backup_path = create_backup(str(db_path), tmp_path / "backups")
    writer.close()

    conn = sqlite3.connect(backup_path)
    count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    conn.close()
    assert count == 2


def test_purge_old_backups_removes_only_expired_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    old_file = backup_dir / "backup-old.db"
    recent_file = backup_dir / "backup-recent.db"
    old_file.write_text("oud")
    recent_file.write_text("recent")

    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
    import os

    os.utime(old_file, (old_timestamp, old_timestamp))

    removed = purge_old_backups(backup_dir, retention_days=30)

    assert removed == 1
    assert not old_file.exists()
    assert recent_file.exists()


def test_purge_old_backups_on_missing_directory_is_a_no_op(tmp_path):
    assert purge_old_backups(tmp_path / "does-not-exist", retention_days=30) == 0


def test_server_startup_creates_an_initial_backup(client, test_settings):
    """The maintenance loop runs once immediately at startup (see main.py),
    so a fresh server should already have produced one back-up file."""
    backup_dir = Path(test_settings.backup_dir)
    # The startup task runs concurrently; give it a brief moment.
    for _ in range(20):
        if backup_dir.is_dir() and list(backup_dir.glob("backup-*.db")):
            break
        time.sleep(0.1)

    backups = list(backup_dir.glob("backup-*.db"))
    assert len(backups) >= 1
