# Licensing and third-party notices

[README](README.md) · [Usage terms](TERMS.md) · [Build instructions](DESKTOP.md)

## Study Desk source code

Study Desk's own code is MIT licensed. The complete grant, copyright notice and
warranty disclaimer are in [LICENSE](LICENSE). Dependencies retain their own
licences; the project's MIT licence does not relicense them.

## Bundled software

| Component | Licence / where to find its notices |
|---|---|
| Python | PSF licence and included historical notices |
| Python dependencies and native document/OCR libraries | Distribution-provided licences and notices in the packaged backend |
| Node.js and its bundled components | Node distribution licence and component notices |
| Open Policy Agent | Apache-2.0 |
| Tauri and native dependencies | Locked Rust dependency licence inventory and packaged notices |
| KaTeX and its fonts | MIT; licence retained under `static/vendor/katex` |
| Marked | MIT; licence retained under `static/vendor/marked` |
| DOMPurify | Apache-2.0 OR MPL-2.0; licence retained under `static/vendor/dompurify` |
| PyInstaller | GPL with the bootloader exception permitting bundled-application distribution; other component obligations still apply |

Exact versions are recorded in `uv.lock`, `desktop/src-tauri/Cargo.lock` and
`desktop/package-lock.json`. PDFium, OCR and other native components can carry
additional notices; preserve their bundled files.

## Windows installer template

`desktop/src-tauri/windows/installer.nsi` comes from Tauri CLI 2.12.4,
Copyright 2017–Present Tauri Apps Contributors, under MIT. Its functional
modification selects per-file compression for differential downloads.
The [full template licence](desktop/src-tauri/windows/TAURI-NSIS-LICENSE.txt)
is retained beside it and bundled as `licenses/Tauri-NSIS-template-MIT.txt`.

## Notices included with installers

Builds include `THIRD-PARTY-NOTICES.txt`, Python distribution and dependency
licence files, Node/OPA licences and the locked Rust dependency licence inventory.
Python notice subdirectories are preserved under the backend's `licenses` folder.

## Redistributing a modified build

- Review the exact dependency and binary inventory for that build.
- Preserve copyright, licence and attribution notices.
- Meet applicable source/relinking obligations for copyleft components.
- Review Linux GTK/WebKit and AppImage component requirements separately.
- Follow [build and release instructions](DESKTOP.md), including signing and provenance checks.

A list of licence identifiers is not a complete legal audit or a guarantee of
universal compatibility. See [compliance scope](COMPLIANCE.md) for the limits of
these safeguards. User course documents are not licensed by Study Desk; their
processing and redistribution permissions remain separate.
