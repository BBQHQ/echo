"""Echo first-boot bootstrap — SSL cert generation.

Browser microphone capture only works in a secure context (HTTPS or
http://localhost), so Echo serves over HTTPS using a self-signed cert that
this module generates on first boot. Idempotent and safe to call every boot.
"""

import shutil
import subprocess
from app.config import settings


def ensure_certs() -> bool:
    """Generate a self-signed cert at the configured paths if missing.

    Returns True if certs now exist, False if generation failed.
    """
    cert = settings.ssl_cert_file
    key = settings.ssl_key_file

    if cert.exists() and key.exists():
        return True

    if not settings.ssl_auto_generate:
        print(f"[Echo] SSL certs missing and auto-generate disabled ({cert}, {key})")
        return False

    cert.parent.mkdir(parents=True, exist_ok=True)
    key.parent.mkdir(parents=True, exist_ok=True)

    # Prefer openssl CLI if available (fast, well-tested)
    if shutil.which("openssl"):
        try:
            subprocess.run(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
                    "-out", str(cert), "-keyout", str(key),
                    "-days", "3650",
                    "-subj", "/CN=localhost",
                ],
                check=True, capture_output=True, timeout=30,
            )
            print(f"[Echo] Generated self-signed SSL cert (openssl), valid 10 years: {cert}")
            return True
        except Exception as e:
            print(f"[Echo] openssl cert generation failed, falling back to Python: {e}")

    # Pure-Python fallback using `cryptography`
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta, timezone

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        key.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
        print(f"[Echo] Generated self-signed SSL cert (cryptography), valid 10 years: {cert}")
        return True
    except Exception as e:
        print(f"[Echo] Cert generation failed completely: {e}")
        print("[Echo] Voice features require HTTPS on non-localhost origins.")
        print("[Echo] Either run scripts/generate_cert.sh or access Echo at http://localhost only.")
        return False
