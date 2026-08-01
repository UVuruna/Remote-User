# Create Cert

**Script:** [Create Cert (script)](../create_cert.py)

## Purpose

One-time self-signed code-signing certificate generator (root SHIP.md
Certificate Management). Run manually, once, before the first build:
`python setup/create_cert.py`. Produces `setup/cert/{app_name}.pfx` and
`setup/cert/password.txt` — both gitignored, both consumed later by
`build.py`'s `sign_file()`. Safe to re-run: it refuses to overwrite an
existing `.pfx`.

## Connections

### Uses
- `setup/app_info.json` — reads `name` to derive the certificate filename
  (`{name}.pfx`)
- Windows PowerShell (`New-SelfSignedCertificate` / `Export-PfxCertificate`,
  via `subprocess.run(["powershell", ...])`)

### Used by
- [Build Orchestrator](build.md) — `sign_file()` in `build.py` reads the
  `.pfx` and `password.txt` this script produces to sign both the exe
  (Step 4) and the installer (Step 6)

## Functions

### `_password() -> str`
Reuses `setup/cert/password.txt` if it already exists; otherwise generates a
random URL-safe token (`secrets.token_urlsafe(24)`), persists it, and prints
where it was written. This is the ONLY place the password is created —
`build.py`'s `sign_file()` only ever reads it back.

### `create_certificate() -> None`
No-ops with a message if `setup/cert/{name}.pfx` already exists (delete it
manually to force regeneration). Otherwise builds a PowerShell script and
runs it via `subprocess`: `New-SelfSignedCertificate` (`CN=UVuruna`,
`CodeSigningCert` type, `Cert:\CurrentUser\My` store, 5-year expiry) then
`Export-PfxCertificate` to the `.pfx` path using the password from
`_password()`. Exits with code 1 and prints PowerShell's stderr on failure.

**Note:** the certificate subject (`PUBLISHER = "UVuruna"`) is a hardcoded
constant here, independent of root `company.json`'s `company_name` — see the
Design Decisions in [setup (folder)](../___setup.md) for the flagged
divergence.
