"""Tiny key/value store in echo.db — persists app state across restarts.

Currently holds one key: `active_model` (the whisper model the user selected
in the in-app model manager). Kept here rather than in a JSON file so the whole
app uses a single SQLite database with one connection pattern.
"""

import aiosqlite
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "echo.db"


async def _get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)"
    )
    await db.commit()
    return db


async def get_state(key: str, default: str | None = None) -> str | None:
    db = await _get_db()
    try:
        cur = await db.execute("SELECT value FROM kv WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else default
    finally:
        await db.close()


async def set_state(key: str, value: str) -> None:
    db = await _get_db()
    try:
        await db.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()
