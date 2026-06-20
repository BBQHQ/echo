"""NVIDIA GPU detection via nvidia-smi."""

import subprocess
import sys

_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def detect_gpu() -> dict:
    """Return {available, name, driver} for the first NVIDIA GPU, if any."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=8, creationflags=_CREATION_FLAGS,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return {"available": False, "name": None, "driver": None}
        first = out.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in first.split(",")]
        name = parts[0] if parts else None
        driver = parts[1] if len(parts) > 1 else None
        return {"available": True, "name": name, "driver": driver}
    except Exception:
        return {"available": False, "name": None, "driver": None}
