# Generate a self-signed SSL cert for Echo.
# Echo auto-generates this on first boot if missing — this script is for manual regeneration.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$CertsDir = Join-Path $Root "certs"

New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null

& openssl req -x509 -newkey rsa:4096 -nodes `
    -out "$CertsDir\cert.pem" `
    -keyout "$CertsDir\key.pem" `
    -days 3650 `
    -subj "/CN=localhost"

Write-Host "[Echo] Generated: $CertsDir\cert.pem + key.pem (valid 10 years)"
