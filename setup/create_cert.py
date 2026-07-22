"""Create the self-signed code-signing certificate for this app — run ONCE,
then reuse across all future builds (root CLAUDE build spec).

Generates setup/cert/{name}.pfx and setup/cert/password.txt (random password,
created here if absent). Both are gitignored — BACK THEM UP externally.
Recreate only if the certificate expires (5 years) or is corrupted.

Usage:
    python setup/create_cert.py
"""

import json
import secrets
import subprocess
import sys
from pathlib import Path

SETUP_DIR = Path(__file__).parent
CERT_DIR = SETUP_DIR / "cert"
APP_NAME = json.loads((SETUP_DIR / "app_info.json").read_text(encoding="utf-8"))["name"]
PFX_PATH = CERT_DIR / f"{APP_NAME}.pfx"
PASSWORD_PATH = CERT_DIR / "password.txt"
PUBLISHER = "UVuruna"


def _password() -> str:
    """Existing password, or a fresh random one persisted for build.py."""
    if PASSWORD_PATH.exists():
        return PASSWORD_PATH.read_text(encoding="utf-8").strip()
    CERT_DIR.mkdir(exist_ok=True)
    password = secrets.token_urlsafe(24)
    PASSWORD_PATH.write_text(password, encoding="utf-8")
    print(f"Generated new certificate password -> {PASSWORD_PATH}")
    return password


def create_certificate() -> None:
    if PFX_PATH.exists():
        print(f"Certificate already exists: {PFX_PATH}")
        print("Delete it manually if you want to regenerate.")
        return

    password = _password()
    ps_script = f"""
    $cert = New-SelfSignedCertificate `
        -Subject "CN={PUBLISHER}" `
        -Type CodeSigningCert `
        -CertStoreLocation Cert:\\CurrentUser\\My `
        -NotAfter (Get-Date).AddYears(5)

    $pwd = ConvertTo-SecureString -String "{password}" -Force -AsPlainText

    Export-PfxCertificate `
        -Cert $cert `
        -FilePath "{PFX_PATH.as_posix()}" `
        -Password $pwd

    Write-Host "Certificate thumbprint: $($cert.Thumbprint)"
    """

    print(f"Creating self-signed certificate for '{PUBLISHER}'...")
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

    print(result.stdout)
    print(f"Certificate created: {PFX_PATH}")
    print("IMPORTANT: setup/cert/ is gitignored — never commit it; back it up externally.")


if __name__ == "__main__":
    create_certificate()
