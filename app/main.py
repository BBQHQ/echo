"""Echo — local voice transcription with history."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import ECHO_ROOT, settings
from app.bootstrap import ensure_certs
from app.services.whisper import start_ttl_watcher, get_status as whisper_status
from app.routers import voice, models, engine


def _quiet_conn_reset(loop, context):
    """Swallow harmless ConnectionResetError from the Windows Proactor loop.

    On Windows + Python 3.12+, uvicorn's ProactorEventLoop logs a traceback
    whenever a browser closes a polling connection with RST instead of FIN
    (e.g. fast /voice/status polling). The request itself completes fine; only
    the cleanup path on connection_lost trips. Silent on other platforms.
    """
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_event_loop().set_exception_handler(_quiet_conn_reset)
    ensure_certs()
    start_ttl_watcher()
    yield


app = FastAPI(title="Echo", version="1.0.0", lifespan=lifespan)

# Routers
app.include_router(voice.router)
app.include_router(models.router)
app.include_router(engine.router)

# Static frontend
frontend_dir = ECHO_ROOT / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(frontend_dir / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Echo", "whisper": await whisper_status()}


def main():
    """Entry point for `python -m app.main`."""
    import uvicorn
    cert = settings.ssl_cert_file
    key = settings.ssl_key_file
    if settings.ssl_auto_generate:
        ensure_certs()
    kwargs = dict(host=settings.echo_host, port=settings.echo_port)
    if cert.exists() and key.exists():
        kwargs["ssl_certfile"] = str(cert)
        kwargs["ssl_keyfile"] = str(key)
    uvicorn.run("app.main:app", **kwargs)


if __name__ == "__main__":
    main()
