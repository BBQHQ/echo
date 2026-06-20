"""Voice log — SQLite storage for all voice transcriptions."""

import aiosqlite
from datetime import datetime
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "echo.db"


async def _get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("""
        CREATE TABLE IF NOT EXISTS voice_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            text         TEXT    NOT NULL,
            duration_ms  INTEGER,
            source       TEXT    NOT NULL DEFAULT 'recording',
            created_at   TEXT    NOT NULL
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_voice_log_created ON voice_log(created_at DESC)"
    )
    await db.commit()
    return db


async def log_transcription(
    text: str,
    duration_ms: int | None = None,
    source: str = "recording",
) -> dict:
    """Save a transcription to the voice log. Returns the saved row."""
    db = await _get_db()
    try:
        now = datetime.now().isoformat()
        cur = await db.execute(
            "INSERT INTO voice_log (text, duration_ms, source, created_at) "
            "VALUES (?, ?, ?, ?)",
            (text, duration_ms, source, now),
        )
        await db.commit()
        return {
            "id": cur.lastrowid,
            "text": text,
            "duration_ms": duration_ms,
            "source": source,
            "created_at": now,
        }
    finally:
        await db.close()


async def get_history(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return voice log entries, newest first."""
    db = await _get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM voice_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_count() -> int:
    """Total number of voice log entries."""
    db = await _get_db()
    try:
        cur = await db.execute("SELECT COUNT(*) FROM voice_log")
        row = await cur.fetchone()
        return row[0]
    finally:
        await db.close()


async def delete_entry(entry_id: int) -> bool:
    """Delete a voice log entry by ID."""
    db = await _get_db()
    try:
        cur = await db.execute("DELETE FROM voice_log WHERE id = ?", (entry_id,))
        await db.commit()
        return cur.rowcount > 0
    finally:
        await db.close()
