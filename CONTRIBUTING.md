# Contributing to Echo

Thanks for your interest! Echo is intentionally small — a focused voice-transcription app. PRs that keep it lean and dependency-light are very welcome.

## Principles

- **Fully local, no accounts.** No cloud transcription, no API keys, no telemetry. Audio stays on the user's machine.
- **Single-user, trusted-network.** No auth layer. Keep it simple.
- **Small surface.** Record, transcribe, keep a history, pick a model. New features should serve that core, not sprawl past it.
- **Cross-platform.** Windows, macOS, Linux. Guard any Windows-only subprocess flags behind the existing `_CREATION_FLAGS` pattern.
- **SQLite only.** One file (`data/echo.db`), `CREATE TABLE IF NOT EXISTS`, no migration framework.

## Stack

- **Backend:** FastAPI + `uvicorn`, async throughout (`aiosqlite`, `httpx`).
- **Frontend:** vanilla HTML/JS/CSS — no framework, no build step. Edit `frontend/` directly.
- **Engine:** [whisper.cpp](https://github.com/ggerganov/whisper.cpp) via its `whisper-server` HTTP interface.

## Layout

```
app/
├── main.py            # FastAPI app + lifespan (certs, whisper TTL watcher)
├── config.py          # Pydantic settings from .env
├── bootstrap.py       # self-signed SSL cert generation
├── routers/           # voice.py, models.py
└── services/          # whisper.py, voice_log.py, model_store.py, state.py
frontend/              # index.html, echo.js, echo.css
scripts/               # install_whisper.*, generate_cert.*
```

## Style

- Python: double quotes, f-strings, `snake_case`, type hints. Run `ruff` if you have it.
- Comment the *why*, not the *what*.
- Keep subprocess calls cross-platform: `encoding="utf-8"`, sensible timeouts, the `_CREATION_FLAGS` guard.
- Small PRs, one change each.

## Running locally

See the [README](README.md) setup section. After changes, smoke-test: record something, check it lands in history, copy it, switch a model in the manager.
