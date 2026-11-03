# Study Desk desktop

The desktop application opens Study Desk in its own window. Python, OPA, Node.js,
OCR models and the study interface are bundled. Users do not need a terminal,
Python installation, `.env` file or an account on a hosted Study Desk service.
DeepSeek generation needs internet access and the user's own funded API key.
Local text embeddings may download their model on first use.

## Installing and using Windows releases

1. After a release is published, download the Windows setup executable and `SHA256SUMS.txt`
   from [GitHub Releases](https://github.com/LeymansGuz/Study-Desk/releases). Install it for your Windows user.
2. Open **Study Desk** from the Start menu or its shortcut.
3. On first launch, **Settings → DeepSeek connection** opens automatically.
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
publish a server on your network. Links outside the workspace cannot navigate
the application's main window, and web content has no Tauri shell/file privileges.

## Study data and updates

Study data is separate from installation files:

| System | Default directory |
|---|---|
| Windows | `%APPDATA%\link.spookelgoose.studydesk` |
| macOS | `~/Library/Application Support/link.spookelgoose.studydesk` |
| Linux | `$XDG_DATA_HOME/link.spookelgoose.studydesk`, usually `~/.local/share/link.spookelgoose.studydesk` |

Install a newer release over the current one after closing Study Desk. Study data
and the system-stored key are preserved. Create a backup in Settings first.
There is no automatic updater in this release. Uninstalling removes the program;
study data and the saved credential are intentionally retained for reinstalling.

To transfer a source-edition workspace, stop both editions first. Back up its
`data` folder, then copy its contents into the desktop data directory before
reopening the app. Keep the original copy until you verify documents and sessions.
Do not copy `.env`, `.tools`, `.venv` or `audit`; enter the key in Settings.
Changing assessment versions can make older bank questions ineligible until they
meet the current verification policy.

## Building from source

Build on the OS and architecture you intend to distribute. Windows x64 is the
primary target. macOS and Linux build paths are provided for subsequent testing;
they are not established as tested releases by the Windows build.

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
2. Push a new tag matching the source version, such as **v0.2.2-beta.1**. This
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

The initial locally built Windows installer is unsigned. Signing credentials
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
