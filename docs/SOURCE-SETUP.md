# Run Study Desk from source

[README and installers](../README.md) · [Troubleshooting](TROUBLESHOOTING.md) · [Development](../CONTRIBUTING.md)

Installers are simpler for ordinary use. Source setup opens a browser at
**http://127.0.0.1:8002** and runs only on your computer. It needs no Docker or
separate database server.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) manages Python 3.12 and locked packages.
- [Node.js 20+](https://nodejs.org/en/download).
- OPA 1.21.3: setup downloads and verifies it when missing; an installed `opa`
  on `PATH` is also accepted.
- Internet for initial setup, model downloads and hosted AI. Use your own provider key.

Get the source with Git or extract GitHub's source ZIP into a private writable folder:

```bash
git clone https://github.com/LeymansGuz/Study-Desk.git
cd Study-Desk
```

## Windows

| Action | Launcher |
|---|---|
| First setup or repair | `Setup.cmd` |
| Activate | `Start.cmd` |
| Check status | `Status.cmd` |
| Deactivate | `Stop.cmd` |

Setup can install missing uv/Node.js with WinGet, creates the locked environment,
verifies OPA and optionally prompts for a key using hidden input. Press Enter to
configure it later in Settings. Setup preserves `.env` and study data and makes
no AI requests. Keep the window open until it completes.

Start opens the local browser workspace. Closing that browser does not stop
services; use **Stop.cmd**. Starting again reopens the existing workspace.
If WinGet is unavailable, install uv and Node.js from their official sites and rerun setup.

## macOS

Target: macOS 14+, Apple Silicon or Intel. With Homebrew:

```bash
brew install uv node
```

**Intel only:** install Apple's Command Line Tools if missing, plus Rust,
OpenSSL and pkg-config. Keep these variables in the same terminal:

```bash
brew install rust openssl@3 pkg-config
export OPENSSL_DIR="$(brew --prefix openssl@3)"
export OPENSSL_STATIC=1
```

The lock uses ONNX Runtime 1.23.2 on Intel; its cryptography dependency builds from
source. These requirements do not apply to users installing a DMG.

Then, inside the project folder:

```bash
uv sync --frozen --no-dev
uv run --no-dev python local_app.py setup
uv run --no-dev python local_app.py start
```

Do not run as root. The `.cmd` launchers are Windows-only. If automatic OPA
download is blocked, `brew install opa` is an alternative. Use the trusted-binary
instructions in [troubleshooting](TROUBLESHOOTING.md) if macOS blocks OPA.

## Linux

Target: x86_64. Install uv and Node.js 20+ using your distribution or the official
installers, then run inside the project folder:

```bash
uv sync --frozen --no-dev
uv run --no-dev python local_app.py setup
uv run --no-dev python local_app.py start
```

Setup downloads the static Linux OPA binary if needed. For blocked networks,
install OPA from its official distribution and make `opa` available on `PATH`.

## Status and stopping on macOS/Linux

```bash
uv run --no-dev python local_app.py status
uv run --no-dev python local_app.py stop
```

`start --no-browser` starts without opening a page. Status exits 0 when running,
1 when stopped, and 2 on an error. Stopping preserves data. There is no automatic
start after reboot; start and stop the services explicitly.

## AI connection and storage

[Obtain your provider key](API-KEYS.md), then use **Settings → AI connection**
for the same provider/key flow as the desktop app.
Alternatively, configure the private `.env` created from `.env.example` while
services are stopped. Never commit it. Setup's optional key prompt uses the
source DeepSeek configuration; other providers can be selected in Settings.

Study data is in `data/`; service logs are in `data/runtime/`. The default ports
are 8002 (web) and 8182 (private OPA). Use different free `LOCAL_PORT` and
`LOCAL_OPA_PORT` values in `.env` when necessary. Never expose these services
through a tunnel or reverse proxy.

## Update or repair

1. Back up your study data and stop the services.
2. Pull the source with `git pull` (resolve any local edits first).
3. On Windows, run `Setup.cmd`, then `Start.cmd`.
4. On macOS/Linux, run the three setup/start commands above again.

Setup honours the dependency lock; it does not arbitrarily upgrade packages.
For tests and installer builds, see [Contributing](../CONTRIBUTING.md) and
[Desktop builds](../DESKTOP.md).

Windows source lifecycle has local verification. Native CI packaged-backend
checks are separate from an end-to-end macOS/Linux source setup/start/stop test.
Apple Silicon's reported desktop launch does not certify the source lifecycle.
