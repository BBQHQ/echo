# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Instead, use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on this repository
(https://github.com/BBQHQ/echo/security/advisories/new).

You'll get an acknowledgement, and we'll work with you on a fix and coordinated
disclosure. Thank you for helping keep Echo's users safe.

## Scope & threat model

Echo is a **single-user, local-first** application intended to run on your own
machine on a trusted network. It has **no authentication** by design.

- Audio is transcribed locally and discarded; only transcribed text is stored
  in a local SQLite database (`data/echo.db`).
- Echo serves over HTTPS with a self-signed certificate so the browser will
  grant microphone access.
- **Do not expose Echo directly to the public internet.** If you need remote
  access, put it behind your own authenticating reverse proxy or VPN.

Reports most useful to us include: path traversal / SSRF in the model and
engine download paths, command-injection around the `ffmpeg`/`whisper-server`
subprocess calls, and anything that could read or write outside the project
directory.

## Supported versions

This project is pre-1.0; security fixes land on the latest `main`.
