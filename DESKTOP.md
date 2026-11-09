# Desktop builds and releases

[User installation](README.md#install-the-desktop-application) · [Source setup](docs/SOURCE-SETUP.md) · [Contributing](CONTRIBUTING.md)

This guide is for maintainers. Installer users need only the README and
[User guide](docs/USER-GUIDE.md).

## Current platform status

Release: [0.2.17 beta](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.17-beta.2).

| Target | Package | Verification |
|---|---|---|
| Windows 10/11 x64 | NSIS setup EXE | Native CI/backend checks; Windows desktop/browser checks exist. |
| macOS 14+ Apple Silicon | aarch64 DMG | Native CI/backend/signature/DMG checks; user-reported device launch. |
| macOS 14+ Intel | x64 DMG | Native CI/backend/signature/DMG checks; device GUI testing pending. |
| Linux x64, Ubuntu 22.04 target | DEB and AppImage | Native CI/backend/package checks; device GUI testing pending. |

User-reported launch is not an exhaustive device test. Source lifecycle checks,
installer checks and actual graphical study/update flows are separate evidence.
Windows arm64 and Linux arm64 have no validated native release package.

## Build locally

Build on the intended OS/architecture. Requirements: Python 3.12 through uv,
Node.js 20+, Rust stable, and [Tauri platform prerequisites](https://v2.tauri.app/start/prerequisites/).
Intel Mac additionally needs the cryptography source-build setup in
[Source setup](docs/SOURCE-SETUP.md#macos).

```text
uv sync --frozen --group dev --group desktop-build
uv run --frozen --group dev pytest -q
uv run --frozen --group desktop-build python desktop/build.py
```

- Output: `dist/installers/`, including checksums and build provenance.
- Every backend runs `StudyDeskBackend --self-check` before packaging proceeds.
  It checks OCR, extraction, vector storage, KaTeX and the frozen symbolic worker,
  without provider inference.
- `--backend-only` diagnoses the packaged backend; Cargo is still required for
  the native dependency licence inventory.
- `--shell-only` rebuilds the shell/installer from an existing backend.
- Close test copies first; Windows may lock executable files during packaging.

The build includes the verified OPA binary, Node executable, locked Python/native
packages and public assets. It excludes `.env`, course data, private evaluations
and signing material. Preserve all [distribution notices](THIRD-PARTY-NOTICES.md).

## CI tool downloads

The workflow selects Python 3.12 and installs pinned uv 0.9.5 from PyPI.
Authenticated CI downloads native tools through the official GitHub release API,
with size and SHA-256 verification before caching. A nonce-protected temporary
gateway binds only to loopback and stops after packaging; Tauri retains its own
checksum checks. Linux receives a verified AppImage runtime explicitly.

Normal source builds do not require a GitHub key. CI supplies its scoped
`GH_TOKEN`; it is not an end-user setting or a bundled credential. Native builds
use verbose diagnostics so tool/network failures are distinguishable from app failures.

## Publish a release

1. Run offline checks and review staged files. Keep private data, credentials,
   reports and generated installers out of source commits.
2. Bump the app version consistently in Python/uv, npm, Cargo and Tauri metadata,
   including corresponding locks. Keep README download links and release notes current.
3. Commit, then push an unused matching tag. For the next version, for example:

   ```text
   git push origin main
   git tag -a v0.2.17-beta.2 -m "Study Desk 0.2.17 beta"
   git push origin v0.2.17-beta.2
   ```

4. **Build desktop installers** runs Windows, both Mac architectures and Linux.
   Alternatively dispatch it manually on the intended source revision with a new
   matching tag and `publish` enabled.
5. All four targets must pass tests and packaged-backend checks. The collector
   verifies revision, version, architecture, package formats, signatures and
   checksums before publication.
6. Check the published assets, combined `SHA256SUMS.txt`, four build manifests,
   README links and complete signed updater feed. Device tests remain necessary
   before claiming broad stable-release compatibility.

A published payload must not be replaced in place. Failed targets block
publication; successful Actions artifacts remain available. Documentation-only
changes do not require rebuilding or replacing the installers.

## Signed updates

Updater signing is separate from operating-system publisher signing.
`TAURI_SIGNING_PRIVATE_KEY` is a CI secret; keep an encrypted offline backup.
Do not commit `.signing/` or private keys. Losing the key prevents seamless
updates for existing installations. Forks need their own key and repository/feed URLs.

For local signing, set `TAURI_SIGNING_PRIVATE_KEY` and, when needed,
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` in the build environment.

Publication verifies payload and signed-version metadata, then atomically updates
`desktop/update-manifest.json`. It covers Windows NSIS, Apple Silicon/Intel app
updates, and Linux DEB/AppImage. Never point it at incomplete or unsigned payloads.

Native Rust code owns update authority. Web content cannot supply arbitrary
feeds, signatures, output paths or control results. Installation requires idle
study/indexing and a verified backup. Documents and credentials are separate from
program files; backups do not promise database downgrade compatibility.

### Differential transport

- A backend worker verifies signed block maps, reuses matching verified cached
  bytes and resumes valid partial downloads.
- It reconstructs a complete package and checks its version-bound signature;
  the installer verifies again. It never patches running app files.
- Missing metadata, unsupported byte ranges or poor reuse fall back to a full
  signed package. The worker exits if the parent app exits.
- Cache retention: one verified package and one partial file; backups exclude it.
- Windows uses pinned Tauri CLI 2.12.4 with non-solid LZMA to improve block reuse.
  The full upstream template licence is retained in bundles.

Build/update protocol files: `desktop/build.py`, `desktop/build_downloads.py`,
`desktop/collect_release.py`, `update_blocks.py` and
`desktop/src-tauri/src/updates.rs`.

## OS trust and device testing

Windows builds have no publisher certificate; Mac bundles are ad-hoc signed and
not Apple-notarized. Signed updater metadata does not remove these OS warnings.
Use [troubleshooting](docs/TROUBLESHOOTING.md) for user-facing opening steps.
Developer ID/notarization and Windows publisher signing are separate distribution
work from the existing updater signatures.

Before broader platform claims, test installation, key storage, uploads/OCR,
indexing, AI workflows, shutdown, update/restart and data preservation on actual
devices. Current evidence and unresolved dependency risk are in the
[security review](SECURITY-AUDIT.md); AI measurements are in
[reliability and cost](docs/RELIABILITY-AND-COST.md).
