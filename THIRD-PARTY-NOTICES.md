# Third-party software

The Windows installer template in `desktop/src-tauri/windows/installer.nsi` is
from Tauri CLI 2.12.4, Copyright 2017–Present Tauri Apps Contributors, used under
the MIT licence. Its only functional modification selects per-file compression
for differential downloads. The full licence is beside the template and included
in desktop bundles as `licenses/Tauri-NSIS-template-MIT.txt`.

Study Desk's own code is MIT licensed. Dependencies retain their own licences; the project's MIT licence does not relicense them. Exact Python and Rust versions are recorded in `uv.lock` and `desktop/src-tauri/Cargo.lock`; the desktop tooling is recorded in `desktop/package-lock.json`.

Desktop bundles include Python and its installed packages, Node.js, Open Policy Agent, the Tauri runtime and system/webview integration libraries. Browser assets include KaTeX and its fonts (MIT), Marked (MIT) and DOMPurify (Apache-2.0 OR MPL-2.0). Their licence files accompany `static/vendor`. Node's distribution licence includes its bundled components. OPA is Apache-2.0. Python uses the PSF licence and its included historical notices.

The build copies distribution-provided Python licence/notice files into `backend/licenses`, preserving subdirectories, and includes Node/OPA licences and the Python distribution's licence. It also records Python dependency metadata. Rust dependency licence notices are generated from the locked native dependency graph. PyInstaller's GPL licence has a bootloader exception permitting distribution of bundled applications; this does not waive other dependency obligations. PDFium, OCR and native libraries may include additional notices; preserve their bundled licence files when redistributing.

Before distributing a modified build, review its exact dependency and binary inventory, preserve notices, and meet any source/relinking obligations of copyleft components. Linux uses system GTK/WebKit libraries and AppImage packaging components; a list of licence identifiers is not a complete legal audit. Source/build instructions are in DESKTOP.md and the source repository. This notice does not assert universal licence compatibility or legal certification.
