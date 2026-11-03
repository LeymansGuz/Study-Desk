# Study Desk desktop

The desktop application opens Study Desk in its own window. Python, OPA, Node.js,
OCR models and the study interface are bundled. Users do not need a terminal,
Python installation, `.env` file or an account on a hosted Study Desk service.
Hosted AI needs internet access and the user's own eligible provider API key. Free endpoints are limited and experimental.
Local text embeddings may download their model on first use.

## Installing and using releases

1. Download the installer for your computer and `SHA256SUMS.txt` from the
   [current beta release](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.7-beta.1).
   On Windows, run the setup executable for your Windows user. On macOS, drag
   the app from the DMG into Applications. On Linux, install the DEB or make
   the AppImage executable. See [installation instructions](README.md#install-the-desktop-application)
   for platform requirements and unsigned-build guidance.
2. Open **Study Desk** from the Start menu or its shortcut.
3. On first launch, **Settings → AI connection** opens automatically.
   Paste your API key and choose **Save API key**. Saving makes no provider call.
4. Add course documents in Workspace, wait for indexing, then practise or explain
   a concept. The same question-quality gates apply in the desktop application.
5. Close the application to stop its backend and policy service. Reopening it
   restores the same local workspace. Only one desktop instance runs per user.

The key is stored using the operating system's credential service, never embedded in
frontend assets or saved in the study database, backups, release installer or repository. It cannot be
read back through the settings API. Enter another key to replace it. If your
system keyring is unavailable or locked, saving fails visibly; the application
does not fall back to a plaintext key file.

The application still runs a private loopback backend internally. Its random
port and per-launch HttpOnly session are managed automatically. It does not
publish a server on your network. The main window stays inside its workspace. Allowlisted provider/legal and official repository links open in the system browser. Web content has no Tauri shell/file privileges.

## Study data and updates

Study data is separate from installation files:

| System | Default directory |
|---|---|
| Windows | `%APPDATA%\link.spookelgoose.studydesk` |
| macOS | `~/Library/Application Support/link.spookelgoose.studydesk` |
| Linux | `$XDG_DATA_HOME/link.spookelgoose.studydesk`, usually `~/.local/share/link.spookelgoose.studydesk` |

Use Settings → App updates to check, download and install a signed full-package update. Installation requires an idle workspace and a verified backup, then restarts the app. The first updater-enabled release needs a manual install. Uninstalling preserves study data and the system credential. See README for platform permissions and recovery limits.

To transfer a source-edition workspace, stop both editions first. Back up its
`data` folder, then copy its contents into the desktop data directory before
reopening the app. Keep the original copy until you verify documents and sessions.
Do not copy `.env`, `.tools`, `.venv` or `audit`; enter the key in Settings.
Changing assessment versions can make older bank questions ineligible until they
meet the current verification policy.

## Building from source

Build on the OS and architecture you intend to distribute. Windows x64 is the
primary target. The published beta also has native Apple Silicon, Intel Mac and
Linux x64 builds. All four targets passed CI tests and packaged-backend checks;
macOS and Linux still need graphical testing on target devices.

Build-machine requirements: Python 3.12 via uv, Node.js 20+, Rust stable and the
platform build tools described in the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).
These tools are needed by maintainers, not by users of the installer.

```text
uv sync --frozen --group dev --group desktop-build
uv run --frozen --group dev pytest -q
uv run --frozen --group desktop-build python desktop/build.py
```

The build bundles the verified OPA download, the build machine's Node executable
and public application assets. It excludes `.env`, study data, local evaluations
and private documents. Python and npm locks plus `desktop/src-tauri/Cargo.lock`
are kept in source. A build manifest records the Python/Node/OPA versions and
the Python lock digest. Bundled component licence notices accompany the backend.

Every backend build runs `StudyDeskBackend --self-check` before proceeding.
This checks OCR, native document extraction, vector storage, KaTeX rejection of
bad math and the frozen symbolic worker. It does not call DeepSeek. The Windows
installer appears in `dist/installers` with `SHA256SUMS.txt`; generated build and
release files are ignored by Git. Installers are large because they include the
native OCR, document and Python dependencies.

For backend-only diagnosis, use `--backend-only`. Once a backend is ready,
`--shell-only` rebuilds the native shell/installer. Close all test copies of Study
Desk before rebuilding: Windows can lock executables being packaged.

## Building through GitHub and publishing a beta

1. Review and commit the source, lock files, `desktop/` and `.github/workflows/`.
   Push them to your repository. Do not force-add ignored local files.
2. Push an unused tag matching the source version, such as **v0.2.3-beta.3**. This
   starts **Build desktop installers** for Windows x64, Apple Silicon, Intel Mac
   and Linux x64. Alternatively run that workflow manually on `main`, supplying
   a new tag and selecting `publish`. No DeepSeek key is required.
3. Each target runs offline tests, builds on its native runner, and checks the
   packaged backend. Intel Mac uses ONNX Runtime 1.23.2 and builds the current
   cryptography package from source. macOS requires version 14 or later.
4. After all four targets succeed, the workflow validates source commit, version,
   architecture, installer format and checksums. It publishes installers, build
   manifests and a combined `SHA256SUMS.txt` as a GitHub prerelease. Failed targets
   block publication; successful job artifacts remain downloadable from Actions.
   Test the graphical app, key storage, indexing, generation and shutdown on your
   devices before considering a stable release. CI checks cannot guarantee these.
5. For later releases, update the version in `pyproject.toml`, `desktop/package.json`,
   `desktop/src-tauri/Cargo.toml` and `desktop/src-tauri/tauri.conf.json`;
   regenerate the corresponding locks and repeat verification. The build manifest
   reads the version from `pyproject.toml`.

The current beta installers are unsigned. Signing credentials
are not supplied by this repository. For a publicly distributed release, arrange
Windows code signing; macOS distribution also needs appropriate Apple signing
and notarization. Configure signing secrets in CI only after obtaining them.
The workflow publishes unsigned experimental prereleases. It refuses to overwrite
an already published release; use a new beta tag for another attempt.

The macOS and Linux installers remain experimental until checked on real devices.
Linux needs an available Secret Service or KWallet credential backend. Android
and iOS are outside this desktop release: the Python/native-worker architecture
requires a separate mobile implementation.

## Verification for this Windows build

The per-user installer, installed runtime self-check and uninstaller passed on
this Windows computer. The installed native window was inspected in light and
dark modes; its first-run key setup and normal close/shutdown worked. Scanned-PDF
upload, spawned OCR workers and local indexing also passed with an empty provider
key. The release has not been verified on a clean Windows VM, macOS or Linux.

## Maintaining signed updates

Updater signing is separate from OS code signing. Official CI uses repository
secret `TAURI_SIGNING_PRIVATE_KEY`. The public key and strict signed-version check
are embedded in the native shell. Keep an encrypted offline backup of the private
key: losing it prevents seamless updates for existing users. The maintainer's
ignored `.signing/` directory must never be committed or bundled.

For a local build, set `TAURI_SIGNING_PRIVATE_KEY` to your key path and, if needed,
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` in the build environment. Forks must generate
their own key and change the fixed repository/feed URLs.

Bump the version consistently in Python/uv, npm and Cargo/Tauri metadata, commit
and push, then run desktop-build with a new matching tag. All four platform builds
must pass. Publication independently verifies signatures, signed versions,
architecture and checksums, then publishes latest.json and atomically updates
desktop/update-manifest.json. The feed covers Windows NSIS, both Mac architectures
and Linux DEB/AppImage. Never point it at incomplete/unsigned releases or replace
published payloads. Use a newer application version for another update.

Native update authority stays in Rust. The UI can request only check/download/
install. Private control endpoints require the per-launch secret; webview input
cannot override the feed, signing key or download path. Updates make no DeepSeek
calls and send no course content to GitHub.

Windows installers use supported NSIS LZMA archive compression. It reduces the
download size while unpacking the same application files; build/installation can
take longer. Runtime libraries and OCR capabilities remain bundled. macOS/Linux
packaging retains its existing supported compression. HTML drag/drop is enabled
inside the native window; clipboard-button availability depends on the WebView,
with standard keyboard paste available as the fallback.
