"""Whisper model catalog + on-demand downloads from HuggingFace.

Lets the user pick a model tier that fits their hardware instead of being stuck
with whatever shipped. Models come from the official whisper.cpp repo on
HuggingFace — the same source the install script uses.
"""

import asyncio
import os
import re
import httpx
from app.config import WHISPER_MODELS_DIR

HF_BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"

# Only fetch real whisper.cpp ggml model files — blocks path traversal and
# restricts downloads to that one HuggingFace repo.
_VALID = re.compile(r"^ggml-[A-Za-z0-9._-]+\.bin$")

# Curated tiers (mirrors Echo's README table). Users can also enter any other
# `ggml-*.bin` filename from the repo as a custom download.
CATALOG = [
    {
        "tier": "Lean",
        "filename": "ggml-base.en-q5_1.bin",
        "size": "57 MB",
        "ram": "~280 MB",
        "language": "English",
        "note": "Any laptop, CPU-only, 8 GB+ RAM. English dictation.",
    },
    {
        "tier": "Balanced",
        "filename": "ggml-small.en-q5_1.bin",
        "size": "181 MB",
        "ram": "~600 MB",
        "language": "English",
        "note": "Modern laptop, 16 GB RAM. Near-human English accuracy.",
    },
    {
        "tier": "Pro",
        "filename": "ggml-large-v3-turbo-q5_0.bin",
        "size": "547 MB",
        "ram": "~1.5 GB",
        "language": "Multilingual",
        "note": "Desktop, 16 GB+ RAM or any GPU. The default.",
    },
    {
        "tier": "Max",
        "filename": "ggml-large-v3-turbo.bin",
        "size": "1.5 GB",
        "ram": "~3 GB",
        "language": "Multilingual",
        "note": "NVIDIA GPU or Apple Silicon. Full-precision turbo.",
    },
]

# In-progress download state (one at a time). None when idle.
# {"filename": str, "received": int, "total": int, "error": str | None}
_download: dict | None = None
_download_lock = asyncio.Lock()


def is_valid_filename(filename: str) -> bool:
    return bool(_VALID.match(filename))


def list_downloaded() -> list[str]:
    """Filenames of models present on disk."""
    if not WHISPER_MODELS_DIR.exists():
        return []
    return sorted(p.name for p in WHISPER_MODELS_DIR.glob("*.bin"))


def current_download() -> dict | None:
    return _download


async def _download_task(filename: str):
    """Stream a model file to disk, tracking progress in the module global."""
    global _download
    dest = WHISPER_MODELS_DIR / filename
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            async with client.stream("GET", HF_BASE + filename) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                _download = {"filename": filename, "received": 0, "total": total, "error": None}
                received = 0
                with open(part, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1 << 20):
                        f.write(chunk)
                        received += len(chunk)
                        _download = {"filename": filename, "received": received, "total": total, "error": None}
        os.replace(part, dest)
        print(f"[Echo] Model downloaded: {filename}")
    except Exception as e:
        try:
            if part.exists():
                part.unlink()
        except Exception:
            pass
        print(f"[Echo] Model download failed ({filename}): {e}")
        _download = {"filename": filename, "received": 0, "total": 0, "error": str(e)}
        # Surface the error briefly, then clear so the UI can retry.
        await asyncio.sleep(5)
    finally:
        if _download and _download.get("filename") == filename and not _download.get("error"):
            _download = None
        elif _download and _download.get("error"):
            _download = None


async def start_download(filename: str) -> dict:
    """Begin downloading a model in the background. One download at a time."""
    if not is_valid_filename(filename):
        return {"ok": False, "error": "Invalid model filename. Must look like ggml-<name>.bin"}
    if filename in list_downloaded():
        return {"ok": False, "error": "Model already downloaded"}
    global _download
    async with _download_lock:
        if _download is not None:
            return {"ok": False, "error": f"A download is already running ({_download['filename']})"}
        # Claim the slot synchronously so a second request can't race in before
        # the background task opens its stream and sets real progress.
        _download = {"filename": filename, "received": 0, "total": 0, "error": None}
        asyncio.create_task(_download_task(filename))
    return {"ok": True, "status": "started", "filename": filename}


def delete_model(filename: str) -> dict:
    """Delete a downloaded model file."""
    if not is_valid_filename(filename):
        return {"ok": False, "error": "Invalid model filename"}
    dest = WHISPER_MODELS_DIR / filename
    if not dest.exists():
        return {"ok": False, "error": "Model not found"}
    try:
        dest.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
