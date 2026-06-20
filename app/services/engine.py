"""whisper.cpp engine management — install the CPU or CUDA prebuilt binary.

On Windows, the whisper.cpp project ships prebuilt release zips: a small CPU
build and a larger cuBLAS (NVIDIA) build that bundles the CUDA runtime DLLs.
Echo can download and swap between them so users with an NVIDIA GPU get
hardware-accelerated transcription with one click — no compiler, no CUDA
toolkit install.
"""

import asyncio
import io
import sys
import time
import zipfile
import httpx
from app.config import WHISPER_DIR, WHISPER_SERVER_EXE
from app.services.state import get_state, set_state
from app.services import gpu, whisper

# Pinned whisper.cpp release. cuBLAS 11.8 is ~278 MB and runs on any reasonably
# recent NVIDIA driver thanks to CUDA forward-compatibility.
_TAG = "v1.9.1"
_BASE = f"https://github.com/ggml-org/whisper.cpp/releases/download/{_TAG}/"
ASSETS = {
    "cpu": {"file": "whisper-bin-x64.zip", "label": "CPU", "size": "~8 MB"},
    "cuda": {"file": "whisper-cublas-11.8.0-bin-x64.zip", "label": "NVIDIA GPU (CUDA)", "size": "~280 MB"},
}

# In-progress engine download/install state (one at a time). None when idle.
_install: dict | None = None
_install_lock = asyncio.Lock()


def supported() -> bool:
    """Prebuilt engine swapping is Windows-only for now."""
    return sys.platform == "win32"


async def get_variant() -> str:
    """Which engine is installed: 'cpu', 'cuda', 'unknown' (manual), or 'none'."""
    if not WHISPER_SERVER_EXE.exists():
        return "none"
    return await get_state("engine_variant", None) or "unknown"


async def current() -> dict:
    return {
        "gpu": gpu.detect_gpu(),
        "variant": await get_variant(),
        "installed": WHISPER_SERVER_EXE.exists(),
        "supported": supported(),
        "installing": _install,
    }


def _write_with_retry(path, data: bytes, attempts: int = 10):
    """Write a file, retrying briefly if it's still locked (e.g. a just-stopped
    whisper-server.exe whose handle the OS hasn't released yet on Windows)."""
    for i in range(attempts):
        try:
            path.write_bytes(data)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.5)


def _extract_engine(zip_bytes: bytes):
    """Replace the engine binary + DLLs in whisper/ with those from the zip.

    Old .dll/.exe are cleared first so CPU and CUDA libraries never mix.
    The caller must stop the whisper server first so the .exe isn't locked.
    """
    for old in list(WHISPER_DIR.glob("*.dll")) + list(WHISPER_DIR.glob("*.exe")):
        for i in range(10):
            try:
                old.unlink()
                break
            except PermissionError:
                time.sleep(0.5)
            except Exception:
                break
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            name = member.rsplit("/", 1)[-1]
            if not name or not (name.endswith(".exe") or name.endswith(".dll")):
                continue
            with zf.open(member) as src:
                _write_with_retry(WHISPER_DIR / name, src.read())


async def _install_task(variant: str):
    global _install
    asset = ASSETS[variant]
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            async with client.stream("GET", _BASE + asset["file"]) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                _install = {"variant": variant, "phase": "downloading", "received": 0, "total": total, "error": None}
                buf = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=1 << 20):
                    buf.extend(chunk)
                    _install = {"variant": variant, "phase": "downloading", "received": len(buf), "total": total, "error": None}
        _install = {"variant": variant, "phase": "installing", "received": len(buf), "total": len(buf), "error": None}
        # Stop the server first so its .exe isn't file-locked during the swap.
        await whisper.restart_for_model_change()
        await asyncio.to_thread(_extract_engine, bytes(buf))
        await set_state("engine_variant", variant)
        print(f"[Echo] Installed {variant} engine ({asset['file']})")
    except Exception as e:
        print(f"[Echo] Engine install failed ({variant}): {e}")
        _install = {"variant": variant, "phase": "error", "received": 0, "total": 0, "error": str(e)}
        await asyncio.sleep(5)
    finally:
        if _install and _install.get("phase") != "error":
            _install = None
        elif _install and _install.get("phase") == "error":
            _install = None


async def start_install(variant: str) -> dict:
    global _install
    if variant not in ASSETS:
        return {"ok": False, "error": "Unknown engine variant"}
    if not supported():
        return {"ok": False, "error": "Prebuilt engine install is Windows-only. On macOS/Linux build with WHISPER_BACKEND=cuda via scripts/install_whisper."}
    if variant == "cuda" and not gpu.detect_gpu()["available"]:
        return {"ok": False, "error": "No NVIDIA GPU detected."}
    async with _install_lock:
        if _install is not None:
            return {"ok": False, "error": "An engine install is already running."}
        _install = {"variant": variant, "phase": "starting", "received": 0, "total": 0, "error": None}
        asyncio.create_task(_install_task(variant))
    return {"ok": True, "status": "started", "variant": variant}
