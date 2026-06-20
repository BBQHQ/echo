#!/usr/bin/env bash
# Build whisper.cpp for the host platform and download the default model.
# Produces ./whisper/whisper-server (or .exe on Windows) + ./whisper/models/<MODEL>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WHISPER_DIR="$ROOT/whisper"
SRC_DIR="$WHISPER_DIR/src"
MODEL="${WHISPER_MODEL:-ggml-large-v3-turbo-q5_0.bin}"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL"

mkdir -p "$WHISPER_DIR/models"

# ─── Clone whisper.cpp ──────────────────────────
if [ ! -d "$SRC_DIR" ]; then
  echo "[Echo] Cloning whisper.cpp..."
  git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$SRC_DIR"
fi

# ─── Detect accelerator ─────────────────────────
CMAKE_ARGS=""
if [ -n "${WHISPER_BACKEND:-}" ] && [ "$WHISPER_BACKEND" != "auto" ]; then
  case "$WHISPER_BACKEND" in
    cuda)  CMAKE_ARGS="-DGGML_CUDA=ON" ;;
    metal) CMAKE_ARGS="-DGGML_METAL=ON" ;;
    cpu)   CMAKE_ARGS="" ;;
  esac
else
  # Auto-detect
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[Echo] CUDA detected — building with GPU acceleration"
    CMAKE_ARGS="-DGGML_CUDA=ON"
  elif [ "$(uname)" = "Darwin" ]; then
    echo "[Echo] macOS detected — building with Metal"
    CMAKE_ARGS="-DGGML_METAL=ON"
  else
    echo "[Echo] No GPU detected — building CPU-only"
  fi
fi

# ─── Build ──────────────────────────────────────
cd "$SRC_DIR"
cmake -B build $CMAKE_ARGS
cmake --build build --config Release --target whisper-server -j

# ─── Place binary ───────────────────────────────
BIN_SRC=""
for candidate in "build/bin/whisper-server" "build/bin/Release/whisper-server.exe" "build/whisper-server"; do
  if [ -f "$SRC_DIR/$candidate" ]; then
    BIN_SRC="$SRC_DIR/$candidate"
    break
  fi
done
if [ -z "$BIN_SRC" ]; then
  echo "[Echo] Could not find built whisper-server binary" >&2
  exit 1
fi
cp "$BIN_SRC" "$WHISPER_DIR/"
echo "[Echo] Installed: $WHISPER_DIR/$(basename "$BIN_SRC")"

# ─── Download model ─────────────────────────────
if [ ! -f "$WHISPER_DIR/models/$MODEL" ]; then
  echo "[Echo] Downloading model: $MODEL (~500-600MB)"
  if command -v curl >/dev/null 2>&1; then
    curl -L -o "$WHISPER_DIR/models/$MODEL" "$MODEL_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$WHISPER_DIR/models/$MODEL" "$MODEL_URL"
  else
    echo "[Echo] Need curl or wget to fetch the model" >&2
    exit 1
  fi
fi

echo "[Echo] Whisper install complete."
echo "[Echo] Binary: $WHISPER_DIR/whisper-server"
echo "[Echo] Model:  $WHISPER_DIR/models/$MODEL"
