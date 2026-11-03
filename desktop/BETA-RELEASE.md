Study Desk desktop beta — use your own funded DeepSeek API key in Settings.

This beta includes signed full-package updates in Settings, an idle-workspace
and verified-backup check before installation, a versioned AI data-use notice,
upload-rights confirmation and bundled dependency notices. Install this first
updater-enabled version manually; subsequent updates can be installed in-app.
Update signing is separate from OS code signing/notarization.

Download the installer for your computer:

- Windows x64: setup executable.
- Apple Silicon Mac, macOS 14+: aarch64/arm64 DMG.
- Intel Mac, macOS 14+: x64 DMG. This compatibility build uses ONNX Runtime 1.23.2; it requires separate testing on Intel hardware.
- Linux x64: DEB or AppImage. The build targets Ubuntu 22.04; other distributions may need additional system libraries and a working Secret Service/KWallet keyring.

The pipeline checks each native build and its packaged backend, then validates architecture, source commit, file format and checksums before publication. This is not a GUI/device compatibility certification. macOS/Linux installers are experimental; test installation, key storage, indexing, generation and shutdown on your own devices. Installers are unsigned and macOS builds are not notarized, so operating-system trust checks can prevent opening them.

AI questions and solutions can contain mistakes, particularly difficult proofs. Automated verification does not guarantee correctness. Study data stays on your computer; relevant excerpts are sent to DeepSeek for AI requests. No developer key or course documents are included.

See the [current README](https://github.com/LeymansGuz/Study-Desk#install-the-desktop-application)
for installation, updates and backups. SHA256SUMS.txt covers every installer and
build manifest attached to this release. Remaining Chroma and Linux GTK dependency
risks are documented in the [security audit](https://github.com/LeymansGuz/Study-Desk/blob/main/SECURITY-AUDIT.md).
