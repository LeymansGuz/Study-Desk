# Security

[Current review](SECURITY-AUDIT.md) · [Privacy](PRIVACY.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## Local trust boundary

Study Desk is a personal, single-owner workspace, not a sandbox against other
software running as your OS account. Keep study files, configuration and backups
private. Do not expose its loopback services through a tunnel or reverse proxy.

Working databases/documents and ordinary backups are unencrypted. Use OS account
permissions and disk encryption; optional encrypted portable backups are available.
Desktop keys use the OS credential store. Source users can use that same Settings
flow or private `.env` configuration; `.env` is not encrypted by the app.

## Services and controls

| Component | Boundary |
|---|---|
| Source web service | Loopback port 8002 by default; Host/Origin/cross-site checks; proxy headers are not trusted. |
| Desktop web service | Random loopback port, per-launch HttpOnly session and separate private control secret. |
| OPA | Separate loopback port (8182 by default for source), fresh token, health/tutor access only; administration denied. Policy failures fail closed. |
| Native window | Restricted navigation; web content has no general native shell/file capability. |
| Key settings | Stored keys are not returned through the API; unavailable keyrings fail visibly without plaintext fallback. |
| Process lifecycle | Birth identities and private control tokens protect stop/cleanup; no killing by arbitrary name or port. |

Closing the source edition's browser does not stop its services; use its launcher.
Closing the desktop application stops its private services. See [Source setup](docs/SOURCE-SETUP.md).

## Files, rendering and study publication

- Size/page/type/path limits apply to uploads. ZIP/DOCX entry/unpacked-size limits
  and XML DTD/entity rejection protect extraction.
- Markdown and SVG are sanitised. Math rendering disables trusted commands;
  CSP restricts scripts. Configuration, databases and backups are not statically served.
- Expressions use bounded evaluators, not arbitrary Python execution.
- Course vectors use a local SQLite store, bound SQL and inert metadata; there
  is no vector HTTP server or remote model configuration.
- Check current sources before atomic publication. Do not hold database write
  locks across model calls, network work or OCR.
- Backups use consistent SQLite snapshots, serialize workspace changes and verify
  archive/database integrity before restore.

## Providers and downloads

AI requests send relevant content to the chosen provider; local storage is not
an offline-model guarantee. Current acknowledgement is required for AI work.
See [Privacy](PRIVACY.md) and [AI connections](docs/AI-AND-PIPELINE.md).

Setup uses locked dependencies and a pinned, checksum-verified official OPA
binary. HTTPS certificate verification stays enabled. CI build-tool downloads
are restricted to official allowlisted releases with size/digest validation.
The temporary CI gateway is loopback-only and is not an app service.

Updates pin the official feed and publisher key, verify signed versions and
packages, and require idle work plus a verified backup before installation.
Differential transport reconstructs a complete signed installer; it does not
patch running files. Updater signatures are separate from OS code signing.

## Report a vulnerability

Use the repository's **Security → Report a vulnerability** option if available.
If private reporting is unavailable, open a minimal issue asking for a private
reporting channel; do not publish exploit details, keys, course files or personal
data. General bugs belong in [Issues](https://github.com/LeymansGuz/Study-Desk/issues).

The [current security review](SECURITY-AUDIT.md) records dated verification and
remaining dependency risk. Automated checks do not prove that every
vulnerability or AI reasoning error has been found.
