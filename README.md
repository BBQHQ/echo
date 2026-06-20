<h1 align="center">Echo</h1>

<p align="center">
  <strong>Local voice transcription with history — in your browser, on your machine.</strong><br>
  Record or drop in an audio file, get instant text, keep a searchable history. No cloud, no accounts, no API keys.
</p>

<p align="center">
  <a href="https://github.com/BBQHQ/echo/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/BBQHQ/echo?label=download&color=brightgreen&logo=github"></a>
  <a href="https://github.com/BBQHQ/echo/releases"><img alt="Release date" src="https://img.shields.io/github/release-date/BBQHQ/echo?color=blue"></a>
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="Local-first" src="https://img.shields.io/badge/local--first-100%25-brightgreen.svg">
</p>

---

Echo is a tiny self-hosted web app for turning speech into text. You run it on your own computer, open it in a browser, and either click record or upload an audio file. It transcribes locally with [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and saves every transcription to a history you can browse, copy, and delete. **Your audio never leaves your machine** — it's transcribed on-device and discarded; only the text is stored.

It started as the voice feature of a larger assistant app and was split out into its own focused tool.

## Features

- 🎙️ **Record** straight from the browser mic — live waveform, plus hold-<kbd>`</kbd> push-to-talk.
- 📁 **Upload** any audio file (WAV, MP3, M4A, OGG, WebM, FLAC).
- 🕘 **History** — every transcription, grouped by day, one click to copy or delete. Persists across restarts.
- 🧠 **Pick your model** — a built-in manager downloads and switches whisper models so you can match accuracy to your hardware, from a 57 MB laptop model to a 1.5 GB multilingual one.
- ⚡ **NVIDIA GPU acceleration** — one click installs the CUDA engine (no compiler, no CUDA toolkit) if an NVIDIA GPU is detected.
- 🔒 **Fully local & private** — no cloud calls, no API keys, no telemetry, no account.

## How it works

Echo is a small [FastAPI](https://fastapi.tiangolo.com/) server with a plain HTML/JS/CSS front end. The actual speech-to-text is done by `whisper-server`, the local HTTP server from the whisper.cpp project.

```
  Your browser                         Echo (FastAPI, localhost)              whisper.cpp
 ┌──────────────┐   audio (mic/file)  ┌───────────────────────┐   16kHz WAV  ┌──────────────┐
 │  record /    │ ──────────────────► │  /voice/transcribe    │ ───────────► │ whisper-     │
 │  upload      │                     │  • ffmpeg → mono WAV   │              │ server       │
 │              │ ◄────────────────── │  • saves TEXT to       │ ◄─────────── │ (auto-start, │
 │  history UI  │   text + history    │    SQLite (echo.db)    │     text     │  idle-stop)  │
 └──────────────┘                     └───────────────────────┘              └──────────────┘
```

Step by step:

1. You record or upload audio in the browser.
2. The browser sends it to Echo's `/voice/transcribe` endpoint.
3. Echo normalizes it to 16 kHz mono WAV with `ffmpeg` and hands it to the local `whisper-server`.
4. whisper.cpp transcribes it and returns the text.
5. Echo saves the **text** (never the audio) to a local SQLite database and shows it.
6. The history view reads it back, newest first; copy or delete any entry.

A few design choices worth knowing:

- **The engine starts on demand and stops when idle** (default 5 min), so it isn't holding RAM/VRAM when you're not dictating.
- **Models are separate downloads.** The engine (`whisper-server`) is one component; the speech *models* (`.bin` files) are another. The in-app model manager fetches models on demand from the official whisper.cpp model repo.
- **HTTPS by default.** Browsers only allow microphone access in a secure context, so Echo serves over HTTPS using a self-signed certificate it generates on first boot. (On the same machine, `http://localhost` also counts as secure.)

### Where your data lives

Everything is local. History and settings are stored in a single SQLite file at **`data/echo.db`**:

- `voice_log` table — your transcriptions (`text`, `duration_ms`, `source`, `created_at`). **Audio is never stored.**
- `kv` table — small settings (active model, engine variant).

The database is git-ignored, so it's never committed. Back it up (or move it between machines) by copying `data/echo.db`.

## Requirements

- **Python 3.11+**
- **The whisper.cpp engine** — installed once (see [below](#installing-the-engine)).

That's it. **ffmpeg is bundled** (via the `imageio-ffmpeg` wheel in `requirements.txt`), so there's nothing else to install — `pip install` brings it along. If you already have a system `ffmpeg` on your `PATH`, Echo will use that instead.

## Quick start

```bash
git clone https://github.com/BBQHQ/echo.git
cd echo

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# Install the engine (see "Installing the engine" below), e.g. on macOS/Linux:
./scripts/install_whisper.sh

python -m app.main
```

Open **https://localhost:8420**, accept the self-signed certificate warning (it's your own local cert), open the **Model** button, and download a model. Then record.

> On Windows you can double-click **`start-echo.bat`** after the `pip install` step.

## Installing the engine

Echo transcribes with a local `whisper-server` binary. The in-app model manager downloads *model files* — but the **engine itself is a separate component** you install once. Two ways:

- **Build from source** — `scripts/install_whisper.sh` (macOS/Linux) or `scripts/install_whisper.ps1` (Windows). Needs `git`, `cmake`, and a C/C++ toolchain (Xcode CLT / build-essential / VS Build Tools). Auto-detects CUDA/Metal.
- **Prebuilt binary (Windows, no compiler)** — download a release zip from [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases) (`whisper-bin-x64.zip` for CPU), and extract `whisper-server.exe` **and all the `.dll` files** into the `whisper/` folder. On a machine with an NVIDIA GPU, Echo can also do this for you — see below.

Until the engine is present, Echo shows a setup banner telling you exactly what to do.

### NVIDIA GPU acceleration (Windows)

If Echo detects an NVIDIA GPU, the **Model** panel shows a one-click **Enable GPU acceleration** button. It downloads the prebuilt cuBLAS engine (~280 MB, which bundles the CUDA runtime — no CUDA toolkit needed), swaps it in, and restarts the engine. You can switch back to CPU just as easily. GPU acceleration makes the larger multilingual models dramatically faster.

## Choosing a model

Whisper comes in size tiers — bigger is more accurate but needs more RAM/VRAM. Switch any time from the **Model** button; the change applies on your next recording.

| Tier | File | Disk | ~RAM | Language | Good for |
|---|---|---|---|---|---|
| **Lean** | `ggml-base.en-q5_1.bin` | 57 MB | ~280 MB | English | Old/cheap laptops, CPU-only |
| **Balanced** | `ggml-small.en-q5_1.bin` | 181 MB | ~600 MB | English | Modern laptop, near-human English |
| **Pro** ⭐ | `ggml-large-v3-turbo-q5_0.bin` | 547 MB | ~1.5 GB | Multilingual | Desktop or any GPU (default) |
| **Max** | `ggml-large-v3-turbo.bin` | 1.5 GB | ~3 GB | Multilingual | NVIDIA GPU / Apple Silicon |

> `.en` models (Lean, Balanced) are English-only. Pick a multilingual tier if you speak anything else. Need a tier that's not listed? Enter any `.bin` filename from the [whisper.cpp model index](https://huggingface.co/ggerganov/whisper.cpp/tree/main) in the **Custom model** box.

## Configuration

All optional — copy `.env.example` to `.env` and uncomment what you want to change.

| Variable | Default | Meaning |
|---|---|---|
| `ECHO_HOST` | `0.0.0.0` | Bind address |
| `ECHO_PORT` | `8420` | Port |
| `ECHO_DATA_DIR` | `./data` | Where `echo.db` lives |
| `SSL_CERT_FILE` / `SSL_KEY_FILE` | `./certs/…` | TLS cert/key (auto-generated if missing) |
| `SSL_AUTO_GENERATE` | `true` | Self-sign a cert on first boot |
| `WHISPER_MODEL` | `ggml-large-v3-turbo-q5_0.bin` | Initial model (the in-app manager overrides this afterwards) |
| `WHISPER_BACKEND` | `auto` | Build hint for `install_whisper`: `auto`/`cuda`/`metal`/`cpu` |
| `WHISPER_THREADS` | `4` | CPU threads for whisper-server |
| `WHISPER_TTL_SECONDS` | `300` | Stop the idle engine after this many seconds |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/voice/transcribe` | Transcribe an uploaded audio file (multipart `file`) |
| `GET` | `/voice/history?limit&offset` | History, newest first → `{items, total}` |
| `DELETE` | `/voice/history/{id}` | Delete one entry |
| `POST` | `/voice/warmup` | Pre-start the engine (called while recording) |
| `GET` | `/voice/status` | Engine running/standby + active model |
| `GET` | `/models` | Model catalog + downloaded + active + download progress |
| `POST` | `/models/download` · `/models/select` | Download / switch a model |
| `GET` | `/engine` | GPU info + installed engine variant |
| `POST` | `/engine/install` | Install the CPU or CUDA engine |

## Running as a service

See [`docs/echo.service.example`](docs/echo.service.example) (systemd, Linux) and [`docs/com.echo.plist.example`](docs/com.echo.plist.example) (launchd, macOS).

## Security & privacy

Echo is designed to run on your own machine on a trusted network. It is single-user with no authentication. Audio is processed locally and discarded; only transcribed text is stored, in a local database. Don't expose it directly to the public internet without putting your own authentication/proxy in front of it. See [`SECURITY.md`](SECURITY.md) to report a vulnerability.

## Contributing

PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: keep it small, local-first, and dependency-light.

## License

MIT — see [`LICENSE`](LICENSE). Built on [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and [FastAPI](https://fastapi.tiangolo.com/).
