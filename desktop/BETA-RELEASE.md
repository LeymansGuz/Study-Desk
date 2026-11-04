Study Desk desktop beta — configure your own AI provider key in Settings. Free OpenRouter models are experimental and restricted to verified brief concept explanations; use a suitable paid model for question generation and tutoring.

This beta includes drag/drop and screenshot paste, visible file queues, bounded
larger Workspace batches, multi-attachment questions, local OCR review/cache,
and signed in-app updates. Windows uses stronger installer archive compression;
the installed runtime remains complete. AI context budgets remain bounded and
attachment reading makes no paid model request. See README for exact limits.

Download the installer for your computer:

- Windows x64: setup executable.
- Apple Silicon Mac, macOS 14+: aarch64/arm64 DMG.
- Intel Mac, macOS 14+: x64 DMG. This compatibility build uses ONNX Runtime 1.23.2; it requires separate testing on Intel hardware.
- Linux x64: DEB or AppImage. The build targets Ubuntu 22.04; other distributions may need additional system libraries and a working Secret Service/KWallet keyring.

The pipeline checks each native build and its packaged backend, then validates architecture, source commit, file format and checksums before publication. This is not a GUI/device compatibility certification. macOS/Linux installers are experimental; test installation, key storage, indexing, generation and shutdown on your own devices. Installers are unsigned and macOS builds are not notarized, so operating-system trust checks can prevent opening them.

AI questions and solutions can contain mistakes, particularly difficult proofs. Automated verification does not guarantee correctness. Study data stays on your computer; relevant excerpts are sent to your selected provider and hosting endpoint for AI requests. No developer key or course documents are included.

See the [current README](https://github.com/LeymansGuz/Study-Desk#install-the-desktop-application)
for installation, updates and backups. SHA256SUMS.txt covers every installer and
build manifest attached to this release. Remaining Chroma and Linux GTK dependency
risks are documented in the [security audit](https://github.com/LeymansGuz/Study-Desk/blob/main/SECURITY-AUDIT.md).

AI connections: secure separate provider keys, refreshable text-model catalogs, hosting selection, free-only price caps, allowance handling and a plain provider-charge notice. DeepSeek, OpenRouter, OpenAI API, Claude API and custom compatible endpoints are available; eligibility and model quality vary. Existing connections are retained.
