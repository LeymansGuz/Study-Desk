# Contributing to Study Desk

Study Desk is a desktop/local-owner application for Windows, macOS and Linux.
Keep the source edition bound to loopback. Read the README before changing
setup, storage paths, AI configuration or the update flow.

## Development checks

Install the locked development dependencies with `uv sync --frozen --group dev`.
Run `uv run --frozen --group dev pytest -q`. Tests use temporary databases and
block real provider inference. Do not add paid requests to the default suite.
Check changed JavaScript with `node --check <file>`.

Native updater tests: `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml`.
Building installers requires the desktop-build dependency group and the platform
tools described in DESKTOP.md. Test actual installation on each target OS;
successful compilation is not a device compatibility guarantee.

## Extension points

- Providers and catalog adapters: `providers.py`. Keep credentials in the OS
  keyring and snapshot the connection for a whole workflow. Unknown pricing must
  never be represented as free. Preserve server-side free-model restrictions.
- Public form choices: `study_catalog.py`. Workspace uploads, document edits,
  course imports and source filters share `DocumentType`; the UI loads labels
  from `/local/catalog`. Extend the shared catalog and contract tests together.
  Keep document edits in place and keep API dates in ISO format while showing
  exam dates as `dd/mm/yyyy`.
- Document readers: `extraction.py`, `pdf_text.py`, `document_ocr.py`. Keep OCR
  selective and cached; preserve page references and cancellation limits.
- Difficulty and workload: `assessment_level.py` is the shared Writer/Verifier
  policy. Match covered learning objectives; never infer scope from a course name.
  Do not add minimum subpart counts, metadata-row quotas or repeated difficulty
  rules in other prompts. Stem length is only an outer verbosity limit.
- Question validation: `tools.py`, `math_checks.py`, `originality.py`. Preserve
  blind solving, grounding, originality, workload checks and atomic publication.
  A higher acceptance rate is not evidence of higher correctness.
  Calculus checks declare `with_respect_to` separately from all free symbols.
  Equation rearrangements use `equation_equivalence` with zero residuals, not
  identities over arbitrary points. Unknown checks require independent scrutiny.
  Keep MCQ key, ordinal/letter references and part requirements consistent when
  shuffling. Public verification receipts must pass `verification_metadata.py`;
  never include private keys, indices or reviewer text in them, including resumes.
- Study tools: `study_companion.py`, `static/companion.js`. Planning and revision
  sheet saving are local operations. Recall assessments use quoted course
  evidence plus independent review. Personal edits are not a marking authority.
- Differential updates: `update_blocks.py`, `desktop/src-tauri/src/updates.rs`.
  Reconstruct a complete package in the app-data cache. Verify signed metadata,
  hashes and the version-bound package signature before installation. Keep the
  ordinary signed full-download fallback. Never patch a running application.
  The Windows template is pinned to CLI 2.12.4; when upgrading that tool, refresh
  the upstream template and retain its licence and single compression change.

## Interface and data

Use the existing typography, spacing, themes and components. Keep common tasks
within the existing views. Preserve unsaved inputs after errors, disable duplicate
submissions, check narrow desktop windows and both themes, and capture screenshots
for changed flows. Do not add mobile/PWA functionality to this desktop edition.

Bound stored records, lists, request bodies, concurrent jobs and retries. Never
hold SQLite write locks across model calls, network downloads, OCR or file I/O.
Validate source freshness before publishing generated study content.

Keep credentials, private course materials, temporary scripts, installers and
evaluation reports out of commits. Private evaluation artifacts belong under
ignored `audit/`. Add small original/anonymised regression fixtures to `tests/`.
For live evaluations freeze each code revision, cap every provider HTTP request
(including retries, reviews and cancelled requests), and report all attempts by
difficulty and type. Separate production costs from evaluation-only audits.
Keep intermediate regressions in the report rather than selecting the best run.
Security reports should follow SECURITY.md.
# Local study-library modules

`study_library.py` owns planning, checked-guide assembly, page notes and personal
imports. `local_jobs.py` runs bounded local search-index/backup jobs; it must not
make provider requests. `backup_tools.py` owns opt-in schedules and encrypted
exports/restores. `course_bundle.py` transfers original files and unverified
personal sheets through the existing ZIP importer. External verification claims
must never be trusted on import. Checked guide writes join generation publication
through the deferred transaction boundary.

Keep optional controls inside existing views. Browser checks must assert panel
padding as well as overflow, theme consistency and input preservation. Private
harnesses, reports and screenshots belong under ignored `audit/`.
