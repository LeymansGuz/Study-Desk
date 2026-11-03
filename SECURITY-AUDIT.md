# Local security and setup audit — 2 November 2026

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

The final OSV scan checked **136 installed packages/vendor components**. It still
reports Chroma 1.5.9 advisories. No newer PyPI release was available at the check.
The affected HTTP-server/multi-tenant surfaces are not used: this single-owner app
uses embedded Chroma and starts no Chroma HTTP server. This limits exposure but
is not an upstream fix. Re-check before enabling a Chroma server or supporting
multiple untrusted users. The OS-user/file-access boundary is described in SECURITY.md.

Primary references: [Chroma HTTP-server advisory](https://osv.dev/vulnerability/GHSA-f4j7-r4q5-qw2c),
[pypdf fixed-release advisory](https://osv.dev/vulnerability/GHSA-5849-834g-hvw5),
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

The current Windows offline regression suite passed **106 tests**. The tracked
source check found no local databases, build output, audit evidence or configured
provider credentials in the 157 tracked files. Documentation links and version
consistency checks also passed.

The current Python dependency audit reports five advisory entries for Chroma
1.5.9 (four distinct advisories, including a duplicate entry). No fixed version
is listed by the scanner. The app still uses embedded `PersistentClient` and
does not expose Chroma's HTTP API or accept remote embedding configurations.
The upstream HTTP-server and multi-tenant risks therefore remain documented,
rather than being described as fixed. The npm audit of the desktop lock,
including build dependencies, reports no known vulnerabilities. These scans
are point-in-time checks, not a guarantee against unknown vulnerabilities or a
full audit of every platform-specific native library.

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
