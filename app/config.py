"""Echo configuration — environment-driven, cross-platform.

Values are read from a `.env` file in the project root or from process env vars.
Every value has a sensible default so Echo boots cleanly out of the box.
"""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ECHO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ECHO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── Core ────────────────────────────────────
    echo_host: str = "0.0.0.0"
    echo_port: int = 8420
    echo_data_dir: Path = ECHO_ROOT / "data"

    # ─── SSL (auto-generated on first boot if missing) ───
    # Browser microphone capture requires a secure context (HTTPS or
    # http://localhost), so Echo serves over HTTPS by default.
    ssl_cert_file: Path = ECHO_ROOT / "certs" / "cert.pem"
    ssl_key_file: Path = ECHO_ROOT / "certs" / "key.pem"
    ssl_auto_generate: bool = True

    # ─── Whisper ─────────────────────────────────
    whisper_dir: Path = ECHO_ROOT / "whisper"
    # Initial/default model. After first boot the active model is whatever the
    # in-app model manager last selected (persisted in echo.db). This value is
    # only the fallback when nothing has been chosen yet.
    whisper_model: str = "ggml-large-v3-turbo-q5_0.bin"
    whisper_backend: str = "auto"  # auto | cuda | metal | cpu (build-time hint)
    whisper_host: str = "127.0.0.1"
    whisper_port: int = 8178
    whisper_threads: int = 4
    whisper_ttl_seconds: int = 300  # kill idle server after 5 min


settings = Settings()

# ─── Backwards-compatible module-level exports ────
# Services reference these constants directly. Keep the names stable.
ECHO_HOST = settings.echo_host
ECHO_PORT = settings.echo_port
DATA_DIR = settings.echo_data_dir

WHISPER_DIR = settings.whisper_dir
WHISPER_MODELS_DIR = settings.whisper_dir / "models"
WHISPER_SERVER_EXE = settings.whisper_dir / (
    "whisper-server.exe" if sys.platform == "win32" else "whisper-server"
)
WHISPER_HOST = settings.whisper_host
WHISPER_PORT = settings.whisper_port
WHISPER_THREADS = settings.whisper_threads
WHISPER_TTL_SECONDS = settings.whisper_ttl_seconds

# Ensure data + model dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
WHISPER_MODELS_DIR.mkdir(parents=True, exist_ok=True)
