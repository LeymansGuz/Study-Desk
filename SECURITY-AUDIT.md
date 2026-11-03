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
