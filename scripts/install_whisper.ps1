# Build whisper.cpp for Windows and download the default model.
# Requires: git, cmake, Visual Studio Build Tools. Optional: CUDA Toolkit.

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root       = Split-Path -Parent $ScriptDir
$WhisperDir = Join-Path $Root "whisper"
$SrcDir     = Join-Path $WhisperDir "src"
$Model      = if ($env:WHISPER_MODEL) { $env:WHISPER_MODEL } else { "ggml-large-v3-turbo-q5_0.bin" }
$ModelUrl   = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$Model"

New-Item -ItemType Directory -Force -Path (Join-Path $WhisperDir "models") | Out-Null

# ─── Clone ──────────────────────────────────────
if (-not (Test-Path $SrcDir)) {
    Write-Host "[Echo] Cloning whisper.cpp..."
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git $SrcDir
}

# ─── Detect accelerator ─────────────────────────
$CmakeArgs = @()
$backend = if ($env:WHISPER_BACKEND) { $env:WHISPER_BACKEND } else { "auto" }
if ($backend -eq "cuda") {
    $CmakeArgs += "-DGGML_CUDA=ON"
} elseif ($backend -eq "auto") {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        Write-Host "[Echo] CUDA detected — building with GPU acceleration"
        $CmakeArgs += "-DGGML_CUDA=ON"
    } else {
        Write-Host "[Echo] No GPU detected — building CPU-only"
    }
}

# ─── Build ──────────────────────────────────────
Push-Location $SrcDir
try {
    cmake -B build @CmakeArgs
    cmake --build build --config Release --target whisper-server -j
} finally {
    Pop-Location
}

# ─── Place binary ───────────────────────────────
$BinSrc = $null
foreach ($candidate in @("build\bin\Release\whisper-server.exe", "build\bin\whisper-server.exe", "build\whisper-server.exe")) {
    $full = Join-Path $SrcDir $candidate
    if (Test-Path $full) { $BinSrc = $full; break }
}
if (-not $BinSrc) { throw "Could not find built whisper-server.exe" }
Copy-Item $BinSrc -Destination $WhisperDir -Force
Write-Host "[Echo] Installed: $(Join-Path $WhisperDir 'whisper-server.exe')"

# ─── Download model ─────────────────────────────
$ModelPath = Join-Path $WhisperDir "models\$Model"
if (-not (Test-Path $ModelPath)) {
    Write-Host "[Echo] Downloading model: $Model (~500-600MB)"
    Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath
}

Write-Host "[Echo] Whisper install complete."
Write-Host "[Echo] Binary: $(Join-Path $WhisperDir 'whisper-server.exe')"
Write-Host "[Echo] Model:  $ModelPath"
