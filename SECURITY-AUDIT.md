# Local security and setup audit

Latest addendum: **7 November 2026**. Baseline review: 2 November 2026.

## 7 November 2026 generation-publication hardening

- Public verification receipts have a typed allowlist. New and resumed practice,
  mastery-path and bank-exam responses exclude private shuffle indices, keys and
  reviewer payloads. Private marking data remains behind the answer-disclosure
  policy; an MCQ key is not verification telemetry.
- Shuffling remaps ordinal references as well as option letters and per-part
  requirements. Discarded proof-search transcripts trigger bounded working repair
  and rechecking rather than publication.
- Independent challenges of alleged premise defects cannot approve a question:
  a withdrawn allegation requires a fresh solve and full reviews. Confirmed or
  uncertain defects remain withheld. Numerical/schema normalization does not
  change the public givens, source evidence or correctness decisions.
- **258 offline tests passed**, including response filtering, malformed private
  metadata, wrong numeric answers, changed loci, invalid proofs and publication
  rollback. Four browser captures cover safe errors and input preservation at two
  desktop widths in light/dark themes, with no page errors or inference calls.
- The rebuilt Windows backend passed its packaged self-check and isolated startup,
  session boundary, persistence, study routes and shutdown checks. No GitHub release
  or hosted-app deployment was performed. Mac/Linux graphical testing remains due.

This addendum adds no runtime dependency or external service. It is not a new
dependency-vulnerability scan or a guarantee of model correctness; see the dated
README evaluation and the platform limitations below.

## 7 November 2026 local release review

- Updated oauthlib 4.0.0 to patched 4.0.1 after the dependency audit reported
  CVE-2026-49272 / GHSA-3jp2-3mrg-2vxc. Lock and requirements export agree.
- Chroma was removed from the runtime dependency graph and replaced with a
  local-only SQLite vector store using the pinned MiniLM embedding model. The
  copied index retained all 371 records, the tested vectors matched exactly and
  three retrieval comparisons returned identical top-ten results. The current
  Python dependency audit reports no known vulnerabilities. npm packaging audit
  reports zero published vulnerabilities.
- Course search publishes only a complete current index. Course deletion purges
  derived search text, page notes, guide/plan metadata and scope snapshots.
  Search jobs serialize with workspace edits to avoid publication/delete races.
- Course ZIP checksums and archive budgets are enforced; queue failures clean up
  newly imported files, registry entries and jobs. Imported sheets/cards never
  become trusted bank questions or inherit external verification flags.
- Encrypted exports use scrypt and per-block AES-GCM with an authenticated end
  marker. Tampered, truncated or wrong-password archives are rejected and partial
  plaintext is removed. Passphrases are not retained. Restores are staged, not
  written over open databases. Export/restore routes are rate-limited.
- Paid truncated outputs receive at most one compact retry; incomplete results
  remain withheld. Free models stop at their output limit without quota-spiking
  retries. Repair never bypasses the independent solve, review or OPA checks.
- Panel padding, custom checkbox/radio styling, file controls, light/dark,
  accessible field labels, keyboard PDF dismissal, draft preservation and
  same-window source navigation are covered by the browser audit.

This review does not certify universal model correctness or Mac/Linux device
compatibility. The latest README reports live development-check limitations
rather than presenting historical acceptance rates as current guarantees.

Scope: ai-tutor-github only. Reviewed setup/process control, dependencies, local
access, policy service, secrets, uploads, archives, storage, backups, rendering,
errors and study workflows. The hosted app was not changed. This is a focused
code/dependency audit and testing, not a guarantee that every vulnerability or
LLM reasoning error has been found.

## Fixed findings

| Finding | Impact | Resolution |
| --- | --- | --- |
| Seven published pypdf advisories affected the locked parser | Malformed PDFs could cause excessive memory/CPU or infinite loops | Updated 6.21.2 to patched 6.21.4; refreshed minimum, lock and requirements |
| Manual policy startup used the hosted service's default port without API authorization | Policy manipulation or interference with another deployment | Dedicated port 8182, random bearer token and default-deny policy allowing only health/tutor decisions |
| AES PDF and Word dependencies were undeclared | Clean installs failed despite tests in a neighbouring development environment | Declared cryptography/python-docx; tested this app's own locked environment |
| Backup verifier required an absent account-session table | Valid local backups failed verification | Corrected required schema, tested actual archive/SQLite integrity and added Verify backup |
| Backups could overlap indexing or share a same-second filename | Inconsistent document/index snapshots or overwritten archives | Workspace serialization, refusal during indexing, rate limit and unique filenames |
| Word/ZIP inputs lacked a complete expansion budget | Excessive memory/parser work from compressed content | Entry-count/unpacked-size ceilings and Word DTD/entity rejection before parsing |
| HTML error handlers referenced missing pages | Error paths could themselves fail | Added usable 404/500 pages with security/no-cache headers and no internal exception details |
| Installer TLS issuer-chain failure in this environment | Automatic OPA download failed | Added current trusted CA roots without disabling certificate verification; real download/hash/policy checks passed |

## Reliability and usability

- Setup wizard plus one-click Windows Start/Stop/Status. Existing configuration
  and study data are retained. Setup makes no LLM requests.
- Windows controls use the built-in PowerShell path, so they work even when
  `powershell` is absent from PATH.
- Readiness waits, duplicate-start protection, cross-process control lock, busy
  port refusal, failed-start cleanup and stale-PID protection.
- Graceful stop plus scoped cleanup of verified process identities/OCR descendants.
  Unrelated hosted listener identities were preserved by the live lifecycle test.
- Managed storage/provider configuration does not inherit another project's key
  or database path. Runtime logs rotate; OPA logs errors only.
- Unneeded API documentation is not served; CSP does not trust external scripts.
- Bank counts show all 28 combinations; file selection matches supported formats;
  text previews do not trigger Word downloads; completed mastery paths retain state.
- Workspace polling stops when leaving the view. Connection failures provide
  Start.cmd guidance while preserving typed input.

## Verification

- Full offline suite in this app's locked environment: **63 passed**.
- Real setup/start/status/stop, duplicate activation, immediate restart, repeated
  stop, authenticated tutor decisions and rejected policy administration passed.
  Measured warm start **6.19 seconds**; stop **1.2 seconds**. First setup/cold
  startup can take longer. Windows wrappers also passed with runtime-only
  dependencies installed, and the local services were left stopped.
- Real pinned OPA download matched its official SHA-256 and compiled both policies.
- Browser checks: desktop windows, light/dark, view state, source preview, complete
  bank counts, backup verification, error pages and stopped-server guidance.
  No uncaught page errors. Evidence is under local audit/ (ignored by Git).
- A real isolated synthetic indexing/retrieval check produced and retrieved **3 chunks in 2.55 seconds** using the cached local embedding model.
- **Zero paid LLM calls.** No live question-generation success rate or provider-key
  validity is claimed by this audit.

## Remaining dependency risk

The final local dependency audit reports no known vulnerabilities for the
runtime environment after Chroma removal. This is a point-in-time scan, not a
guarantee against unknown vulnerabilities. The app uses a local SQLite vector
store with no HTTP vector server, no tenant/RBAC layer and no remote embedding
configuration. The OS-user/file-access boundary is described in SECURITY.md.

Primary references: [pypdf fixed-release advisory](https://osv.dev/vulnerability/GHSA-5849-834g-hvw5),
[OPA security configuration](https://www.openpolicyagent.org/docs/security).
Full dependency, lifecycle and browser evidence is retained locally in audit/.


## Local learning-workflow review — 3 November 2026

- Mastery requests validate a specific topic and explicit question type. Each
  stage uses one complete normal pipeline with queue-aware timeout and atomic
  publication. A failed continuation preserves the previous stage.
- Bank exams use current verified items only, with no generation fallback.
  Responses exclude private solutions; normal answer-disclosure policies apply.
  Course changes and quarantine are checked on resume and answer access.
- Corrected legacy retention triggers so hidden child questions cannot evict
  live paths/exams. Ten visible sessions are kept; their child records follow
  their parent lifecycle. Cached-token details come from retained provider traces.
- Removed unnecessary cross-origin middleware; the same-origin loopback boundary
  remains authoritative. No authentication, network exposure or paid tests added.


Final workflow verification: **62 offline tests passed**; **84 desktop screenshots**
(full-size/narrow windows, light/dark), zero uncaught page errors, zero paid model
calls. Frozen dependency metadata and JavaScript syntax checks passed. The local
service was restarted and the new endpoint validation checked on port 8002.
No new dependency vulnerability scan or live LLM quality benchmark was run in this
workflow pass. Evidence is under ignored `audit/refinement-*` paths.

## Published desktop beta review — 3 November 2026

The public Windows v0.2.2-beta.2 installer was downloaded and its SHA-256 checked
against the release checksum file. Installation into an isolated directory,
bundled backend self-checks, scanned-PDF upload, OCR, embedding/indexing and clean
backend shutdown passed. The installed window rendered and navigated correctly
in light and dark themes. Uninstallation removed the isolated program copy and
retained its separate study data. No paid model requests were made. The four native CI
targets also passed their offline suites and packaged-backend checks; macOS and
Linux graphical installation and credential-store behaviour still require
target-device testing. Unsigned installers remain a distribution limitation.

A new desktop browser pass covered 92 screenshots at two window widths in light
and dark mode, including source evidence, mastery progression, bank exams,
paper summaries, backup verification and safe failure messages. There were no
uncaught page errors. Generated study content in this pass used isolated
fixtures; these results do not measure LLM correctness or acceptance rates.

The current Windows offline regression suite passed **237 tests**. The tracked
source check found no local databases, build output, audit evidence or configured
provider credentials in the 157 tracked files. Documentation links and version
consistency checks also passed.

The current Python dependency audit reports no known vulnerabilities after the
Chroma runtime dependency was replaced with the local SQLite vector store. The
store uses bound SQL values, inert JSON metadata, an explicit embedding model
pin and no HTTP server or remote model configuration. The npm audit of the
desktop lock, including build dependencies, reports no known vulnerabilities.
These scans are point-in-time checks, not a guarantee against unknown
vulnerabilities or a full audit of every platform-specific native library.

An additional OSV check covered 444 registry packages in `Cargo.lock` and the
Intel Mac's ONNX Runtime 1.23.2. The Intel runtime had no advisory match. The
Rust graph includes Linux GTK's `glib` 0.18.5 unsound iterator advisory
[RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html).
Its upstream fix is in glib 0.20, outside Tauri's GTK3 dependency range; this is
also tracked by [Tauri upstream](https://github.com/tauri-apps/tauri/issues/12564).
The app does not directly call the affected iterator, but this review does not
prove that dependency paths cannot reach it. The Linux build therefore retains
this unresolved upstream risk. Replacing the GTK dependency with an incompatible
major version is not a validated repair.

Four other Rust matches are maintenance notices for `proc-macro-error`,
`zbus_names`, `zvariant` and `zvariant_derive`, rather than identified exploit
reports. Their replacement requires changes in upstream dependency chains.
Neither these notices nor the glib advisory were suppressed or described as
fixed. Cross-platform stable-release approval still requires dependency review
and graphical tests on the target devices.

## Course index maintenance — 3 November 2026

Source verification for version 0.2.3 passed 113 offline tests, 28 browser
screenshots across two desktop widths and both themes, and a real local
two-course upload/index/rebuild check. The selected course's document IDs,
document types, syllabus exclusions and scope settings were preserved; the
other course's chunks were unchanged. No paid provider calls were made.
Invalid/empty-course requests fail before checking storage or creating jobs;
concurrent rebuild requests are rejected while that course is indexing.
The default free-space reserve is 1 GiB plus estimated new work. Explicit
source-edition reserve settings remain respected. Model defaults use the
provider's documented `deepseek-flash` identifier; legacy source settings are
mapped only for the official DeepSeek endpoint.

The explicit DeepSeek request mode is covered by an additional transport-options
regression test (114 offline tests total). The current live check used runtime
revision `dacce90`, policy 19: nine generation attempts, eight accepted, one
Solver timeout, and one accepted item with an additional grounding-review flag.
No universal correctness claim follows from these results. The current README
records the generation-only costs, missing usage and retrieval limitations.
The shared live-evaluation ledger reserved 92 requests, including ten preliminary
diagnostic calls and eight final-sample review calls, below the authorized 100.
Private evidence remains under ignored `audit/workspace-refinement/`.

Private evidence is retained under ignored `audit/final-beta-audit/`; user study
data and provider credentials were not added to the repository.

Corrected v0.2.3-beta.2 native builds passed all four platform test suites and
packaged-backend checks. Its Windows installer passed isolated installation,
self-check, scanned-PDF OCR/indexing, selected-course rebuilding, shutdown and
uninstallation with study data retained. The tested Windows payload matches
the published SHA-256. All five installer links and all release payload digests
were checked. macOS/Linux graphical behaviour still needs target-device testing.

## Signed updates and data-use safeguards — 4 November 2026

The desktop updater pins the official feed and publisher key in Rust, restricts
downloads to versioned official release assets, requires signed-version matching,
and verifies packages before installation. Web content cannot supply URLs, paths,
signatures or native control results. Installation refuses active work/uploads/
indexing, freezes new writes and verifies a SQLite/document backup before stopping
the backend. Downloads use full packages. Update checks are manual.

Versioned data-use/usage notices are available in Settings. The backend blocks AI
requests without the current acknowledgement, supports withdrawal and requires
upload-rights confirmation. Notices describe provider transfers, costs, local
unencrypted data, deletion controls and licence responsibilities. Python licence
paths are preserved and native dependency notices accompany the installers.
These safeguards are not legal clearance; see COMPLIANCE.md.

Verification: 122 offline tests, including a clean Git export, plus two native
Rust tests; 128 desktop browser screenshots across light/dark and wide/narrow
windows, with no page errors. A production-updater test using an isolated
lower-version NSIS-marked client verified a public signed package, installed it,
restarted and preserved course/document data, acknowledgement and credential
configuration. The final 0.2.5 Windows installer passed native startup/update
checking, private-control/consent guards, frozen math/OCR/extraction/storage
checks, real scanned-PDF indexing, rebuilding and clean shutdown. No paid model
calls were made for this pass. Existing generation-quality limitations remain;
this was not a new LLM correctness evaluation.

Native dependency builds do not certify target-device GUI behaviour, eliminate
upstream dependency advisories, or replace OS code signing/notarization. Keep an
offline backup of the private updater key. Private evidence and signing material
remain outside Git under ignored directories.

The v0.2.5-beta.1 release passed all four native CI builds and independent
pre-publication signature checks. Post-publication checks matched all 18 asset
digests to the combined checksum file, verified all seven installer/update-payload
links, matched the complete five-target update feed to the release, and confirmed
that the tested Windows installer matches GitHub's public payload digest. The
published README matches the tracked source. The final installed Windows app also
passed its native update check against the published feed. macOS/Linux graphical
and installation/update testing on target devices remains outstanding.

## Bounded attachments and final beta verification — 4 November 2026

Version 0.2.6 adds shared file queues with picker/drop/screenshot paste, explicit
clipboard access, visible file sizes and local OCR review. Workspace limits are
50 files / 500 MiB per batch / 200 MiB per document. Question attachments are
limited to five files / 50 MiB total / 20 MiB each / 20 pages, with the existing
30,000-character combined question limit. Images are capped at 20 MiB / 16 MP.
Image format/integrity and PDF page limits are checked before OCR. Clipboard
reading happens only after a user action. OCR does not interpret diagrams.

Extraction runs through a bounded worker and a bounded text-only memory cache;
identical concurrent requests share extraction. Cancellation does not release
the worker while OCR is still running. Retries reuse successful text, and
discarding an interrupted workspace selection releases its staging reservation.
The updater refuses installation while extraction is active. No additional LLM
stages or larger question-context budgets were introduced.

Verification: 130 offline tests passed, including a clean tracked-source export,
plus two native Rust tests. Desktop browser checks produced 124 screenshots
across light/dark themes and wide/narrow windows with no page errors. They cover
attachment selection, limits, clipboard fallback, OCR review, retries, image
preview, interrupted-upload cleanup and the existing study flows. No paid
provider calls were made; this pass does not establish a new generation
acceptance or answer-correctness rate.

All four native CI builds passed for v0.2.6-beta.1. Public verification matched
all 18 asset digests to the checksum file, checked all seven installer/update
payload links, all four build revisions and the complete five-target update
feed. The public Windows installer was downloaded and matched to its digest.
A real installed public 0.2.5 client downloaded and verified 0.2.6, created a
verified backup, installed/restarted and preserved course/document data and
credential configuration. It required the updated privacy acknowledgement and
then reported the current version correctly.

The installed 0.2.6 backend passed multi-file OCR/progress/cache checks, workspace
image upload/indexing/preview and rebuilding with the existing OCR checkpoint.
The sample screenshot took 2.653 seconds to read initially and 0.007 seconds on
retry. A separate text-PDF sample added about 0.7 ms of worker/cache overhead.
These samples are not guarantees for large scanned documents.

Windows NSIS LZMA compression reduced the published installer from 288,020,735
bytes (0.2.5) to 216,551,151 bytes (0.2.6), about 24.8%. A controlled comparison
of the same application payload found all 3,051 runtime files identical after
extraction; LZMA archive extraction added about 4.8 seconds in that sample.
Application runtime performance is unaffected by the installer compressor.
macOS/Linux compression was retained. Target-device GUI/install/update testing
for those platforms remains outstanding; native CI checks are not a substitute.

Repository checks found no private test artifacts or configured credentials in
tracked files. Private reports, screenshots and signing material remain ignored.
The hosted website was not changed by this work. Uninstalling the disposable
Windows test installation removed its program files while preserving its
separate study database and backup.
