#!/usr/bin/env bash
# Generate a self-signed SSL cert for Echo.
# Echo auto-generates this on first boot if missing — this script is for manual regeneration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CERTS_DIR="$ROOT/certs"

mkdir -p "$CERTS_DIR"

openssl req -x509 -newkey rsa:4096 -nodes \
  -out "$CERTS_DIR/cert.pem" \
  -keyout "$CERTS_DIR/key.pem" \
  -days 3650 \
  -subj "/CN=localhost"

echo "[Echo] Generated: $CERTS_DIR/cert.pem + key.pem (valid 10 years)"
