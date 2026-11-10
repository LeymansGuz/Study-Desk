# Troubleshooting

[Downloads](../README.md#install-the-desktop-application) · [User guide](USER-GUIDE.md) · [Source setup](SOURCE-SETUP.md)

## macOS blocks the app

1. Download the correct official DMG: Apple Silicon or Intel, with macOS 14+.
2. Drag Study Desk to **Applications**, eject the DMG, and try opening it once.
3. For a trusted download blocked as an unidentified developer, open
   **System Settings → Privacy & Security → Open Anyway**, then confirm opening it.

The beta is ad-hoc signed, not Apple-notarized. This is Apple's per-app override,
not a reason to disable Gatekeeper globally. See [Apple's instructions](https://support.apple.com/en-us/102445).

A damaged-app or invalid-signature warning can also mean a corrupt download.
Re-download and compare against the release's `SHA256SUMS.txt` before proceeding.
For example, from the download folder:

```bash
shasum -a 256 Study-Desk_0.2.18_aarch64.dmg
```

Use the x64 filename for an Intel DMG. If the verified official app remains blocked
by quarantine, this app-specific command is an advanced fallback:

```bash
xattr -cr "/Applications/Study Desk.app"
```

Do not use it on unknown apps or treat every signing warning as harmless. If the
app still fails, report the Mac chip, macOS version, app version and exact message.
Apple Silicon has user-reported launch testing; Intel hardware testing is pending.

## Windows blocks the installer

The beta has no Windows publisher certificate. Download from the official release
and verify its checksum before deciding whether to allow an unknown-publisher
prompt. Follow your organisation's device policy. Do not disable protection
system-wide. Windows may also need to install its WebView2 runtime.

## Linux dependencies or FUSE

The Linux packages target Ubuntu 22.04 x64. The DEB resolves package dependencies
through your package manager. Other distributions may need compatible
`libwebkit2gtk-4.1-0` and `libsecret-1-0` packages.

For a missing-FUSE AppImage error, install `libfuse2` where available, or run:

```bash
./Study-Desk_0.2.18_amd64.AppImage --appimage-extract-and-run
```

Saving an API key needs an unlocked Secret Service or KWallet credential backend.
The app fails visibly rather than writing a plaintext key. Linux native CI checks
passed; end-user desktop testing is still pending.

## API key, model or free-allowance errors

Need to create a key first? Follow [Get an API key](API-KEYS.md).

- Open **Settings → AI connection**. Check the provider, model and hosting endpoint.
- Leave the key blank to reuse that provider's saved key; enter a new one to replace it.
- Wait for model/endpoint loading before saving. A failed lookup needs an eligible selection.
- Check the provider account's balance, allowance and access to that model/host.
- Free models support brief explanations only; paid features do not fall back to paid usage automatically.
- A website subscription is not an API credential. See [connection details](AI-AND-PIPELINE.md).

Source users can also stop services, check their private `.env` and restart.
Never post a key in an issue or screenshot.

## Question or explanation generation fails

Read the stage and safe reason: missing evidence, conflicting givens, a repeated
task, answer disagreement or timeout need different responses. Ensure the course
has finished indexing and the topic is actually covered. Try a narrower covered
concept if necessary; do not keep clicking while a request is running.

No partial question is published. Existing study work is retained. Detailed
outcomes are in local Statistics/diagnostics. This is an AI study aid; checked
outputs can still be wrong. See [measured reliability](RELIABILITY-AND-COST.md).

## Files are missing from study or indexing seems stuck

- Check the selected course, search filter and upload/indexing status.
- Verify document types and whether files are excluded from **Any syllabus topic**.
- Use **Rebuild course index** only for a course containing documents, after active indexing finishes.
- Free disk space if the reserve is reached. The default reserve is 1 GiB plus the estimated new work.
- Scans and large images take longer than text PDFs. OCR does not interpret diagram relationships.
- Convert problematic old `.doc` files to `.docx` or PDF in Word/LibreOffice.

## Clipboard screenshot button does not work

Focus the attachment area and paste with **Ctrl+V** (Windows/Linux) or
**Command+V** (Mac). The clipboard button depends on the system WebView.
Normal text paste remains available. Review OCR symbols before starting tutoring.

## An update cannot install

Finish requests, uploads and indexing first. Ensure there is enough disk space
for the staged installer and backup. Run the Mac app from Applications; keep a
Linux AppImage writable, or approve package-manager permissions for a DEB.

A failed signature/version/hash check installs nothing. Do not replace the feed
or bypass verification. Reopen the app and check its installed version before
retrying. A manually downloaded current installer is a recovery option; preserve
study data and backups. Update signatures do not suppress OS trust warnings.

## Source-edition setup and startup

| Problem | What to check |
|---|---|
| `uv` not found | Open a new terminal after installation; ensure its install directory is on `PATH`. |
| Node missing/too old | Run `node --version`; install Node.js 20+ and reopen the terminal. |
| OPA download fails | Rerun setup; if needed install from the [official OPA distribution](https://www.openpolicyagent.org/docs). Setup checks `.tools/opa` before `PATH`. |
| OPA blocked on Mac | Only for the checksum-verified official binary: `xattr -d com.apple.quarantine .tools/opa`. |
| Busy port | Stop the existing instance, or set two different free ports in `.env`; the launcher never kills another service by port/name. |
| No browser page | Check status, then open `http://127.0.0.1:8002` directly (or your configured port). |
| Startup failure | Inspect `data/runtime/web-runtime.log` and `data/runtime/opa.log`. |

Use [source setup](SOURCE-SETUP.md) for the correct start/stop commands. Closing
its browser does not stop services. Keep ports in 1024–65535 and use different
web/OPA ports.

## Report a problem

Use [GitHub Issues](https://github.com/LeymansGuz/Study-Desk/issues). Include the
app version, operating system/chip, steps and visible error. Inspect diagnostics
before attaching anything; remove API keys, private notes, personal information
and copyrighted course excerpts. For suspected vulnerabilities, use [Security](../SECURITY.md).
