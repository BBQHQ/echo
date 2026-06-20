"""Whisper transcription service — manages a local whisper.cpp server process.

The server is started on demand and shut down after an idle TTL to free RAM.
The active model is resolved at call time from the kv store (set by the in-app
model manager), so switching models takes effect on the next recording without
restarting Echo.
"""

import asyncio
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from app.config import (
    WHISPER_SERVER_EXE,
    WHISPER_MODELS_DIR,
    WHISPER_HOST,
    WHISPER_PORT,
    WHISPER_THREADS,
    WHISPER_TTL_SECONDS,
    settings,
)
from app.services.state import get_state
from app.services import model_store

_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

_last_used: float = 0.0
_server_process: subprocess.Popen | None = None
_ttl_task: asyncio.Task | None = None
_base_url = f"http://{WHISPER_HOST}:{WHISPER_PORT}"


async def get_active_model() -> str:
    """Filename of the model to use — the user's selection, else the default.

    Falls back to the default if the selected model's file is missing (e.g. the
    .bin was deleted or the database was carried over from another machine).
    """
    chosen = await get_state("active_model", None)
    if chosen and _model_path(chosen).exists():
        return chosen
    # Selected model is missing (or nothing chosen yet): prefer the configured
    # default, otherwise fall back to any model that's actually on disk so a
    # single-model install transcribes without the user having to pick first.
    if _model_path(settings.whisper_model).exists():
        return settings.whisper_model
    downloaded = model_store.list_downloaded()
    if downloaded:
        return downloaded[0]
    return settings.whisper_model


def engine_installed() -> bool:
    """Whether the whisper.cpp server binary is present."""
    return WHISPER_SERVER_EXE.exists()


def _model_path(filename: str) -> Path:
    return WHISPER_MODELS_DIR / filename


async def _is_server_running() -> bool:
    """Check if whisper-server is responding."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(_base_url, timeout=3)
            return resp.status_code == 200
    except Exception:
        return False


async def _start_server() -> bool:
    """Start the whisper-server process with the active model."""
    global _server_process

    if await _is_server_running():
        return True

    # Kill any orphaned process
    if _server_process and _server_process.poll() is None:
        _server_process.terminate()
        _server_process.wait(timeout=5)

    if not WHISPER_SERVER_EXE.exists():
        print(f"[Echo] Whisper binary not found at {WHISPER_SERVER_EXE}")
        print("[Echo] Run scripts/install_whisper.sh (or .ps1) to build it.")
        return False

    model_path = _model_path(await get_active_model())
    if not model_path.exists():
        print(f"[Echo] Whisper model not found at {model_path}")
        print("[Echo] Download one from the model manager, or run scripts/install_whisper.")
        return False

    try:
        _server_process = subprocess.Popen(
            [
                str(WHISPER_SERVER_EXE),
                "-m", str(model_path),
                "-t", str(WHISPER_THREADS),
                "--host", WHISPER_HOST,
                "--port", str(WHISPER_PORT),
            ],
            cwd=str(WHISPER_SERVER_EXE.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATION_FLAGS,
        )
    except Exception as e:
        print(f"[Echo] Failed to start whisper-server: {e}")
        return False

    # Wait for server to be ready (model loading takes a few seconds)
    for _ in range(30):
        await asyncio.sleep(1)
        if await _is_server_running():
            print("[Echo] Whisper server started")
            return True

    print("[Echo] Whisper server failed to start in time")
    return False


async def _stop_server():
    """Stop the whisper-server process."""
    global _server_process

    if _server_process and _server_process.poll() is None:
        _server_process.terminate()
        try:
            _server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _server_process.kill()
        print("[Echo] Whisper server stopped")

    _server_process = None


async def restart_for_model_change():
    """Stop the running server so the next request reloads with the new model."""
    await _stop_server()


async def _ttl_watcher():
    """Background task that stops the server after idle timeout."""
    while True:
        await asyncio.sleep(30)
        if _last_used > 0 and _server_process and _server_process.poll() is None:
            idle = time.time() - _last_used
            if idle > WHISPER_TTL_SECONDS:
                print(f"[Echo] Whisper idle for {idle:.0f}s — stopping server")
                await _stop_server()


def start_ttl_watcher():
    """Start the TTL background watcher. Call once at app startup."""
    global _ttl_task
    if _ttl_task is None:
        _ttl_task = asyncio.create_task(_ttl_watcher())


_ffmpeg_exe: str | None = None


def _get_ffmpeg() -> str:
    """Resolve an ffmpeg binary: a system one on PATH if present, otherwise the
    static binary bundled via the imageio-ffmpeg wheel (so Echo is self-contained
    and needs no separate ffmpeg install). Result is cached."""
    global _ffmpeg_exe
    if _ffmpeg_exe:
        return _ffmpeg_exe
    _ffmpeg_exe = shutil.which("ffmpeg")
    if not _ffmpeg_exe:
        try:
            import imageio_ffmpeg
            _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            _ffmpeg_exe = "ffmpeg"  # last resort; surfaces a clear error if absent
    return _ffmpeg_exe


def _convert_to_wav(audio_bytes: bytes, filename: str) -> bytes:
    """Convert any audio format to 16kHz mono WAV using ffmpeg."""
    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src:
        src.write(audio_bytes)
        src_path = src.name
    out_path = src_path + ".wav"
    try:
        subprocess.run(
            [
                _get_ffmpeg(), "-y",
                "-i", src_path,
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                out_path,
            ],
            capture_output=True,
            timeout=30,
            creationflags=_CREATION_FLAGS,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        Path(src_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)


async def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> dict:
    """Transcribe audio bytes via the local whisper.cpp server.

    Returns {"text": "...", "duration_ms": ...} on success, or {"error": "..."}.
    """
    global _last_used

    running = await _is_server_running()
    if not running:
        # Specific, actionable errors beat a generic "failed to start".
        if not WHISPER_SERVER_EXE.exists():
            return {"error": "Whisper engine not installed. The model manager only downloads models — the engine is a separate component. Run scripts/install_whisper, or drop a whisper-server build into the whisper/ folder."}
        model = await get_active_model()
        if not _model_path(model).exists():
            return {"error": "No transcription model found. Open Model (top-right) and download one."}
        started = await _start_server()
        if not started:
            return {"error": "Whisper engine failed to start. Check the server console output for details."}

    _last_used = time.time()
    start = time.time()

    # Convert to WAV — whisper.cpp only accepts WAV
    try:
        wav_bytes = await asyncio.to_thread(_convert_to_wav, audio_bytes, filename)
    except Exception as e:
        return {"error": f"Audio conversion failed: {str(e)}"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_base_url}/inference",
                files={"file": ("audio.wav", wav_bytes)},
                data={"response_format": "json"},
                timeout=120,
            )
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                result = resp.json()
                # Whisper emits a newline after every segment; collapse all
                # whitespace runs to single spaces so mid-thought segment
                # boundaries don't render as line breaks.
                text = " ".join((result.get("text") or "").split())
                return {"text": text, "duration_ms": elapsed_ms}
            return {"error": f"Whisper server returned {resp.status_code}: {resp.text}"}
    except httpx.TimeoutException:
        return {"error": "Transcription timed out (120s limit)"}
    except Exception as e:
        return {"error": f"Transcription failed: {str(e)}"}


async def warm_up() -> dict:
    """Start whisper server without blocking. Returns immediately.

    Bumps _last_used so the TTL watcher won't kill the server while a recording
    is in progress (the frontend heartbeats this during recording).
    """
    global _last_used
    _last_used = time.time()
    running = await _is_server_running()
    if running:
        return {"status": "already_running"}
    # Fire off server start in background — don't await full readiness
    asyncio.create_task(_start_server())
    return {"status": "warming_up"}


async def get_status() -> dict:
    """Return current transcription service status."""
    running = await _is_server_running()
    idle = time.time() - _last_used if _last_used > 0 else None
    model = await get_active_model()
    return {
        "backend": "local",
        "running": running,
        "engine_installed": engine_installed(),
        "model": model,
        "model_present": _model_path(model).exists(),
        "idle_seconds": round(idle) if idle else None,
        "ttl_seconds": WHISPER_TTL_SECONDS,
    }
