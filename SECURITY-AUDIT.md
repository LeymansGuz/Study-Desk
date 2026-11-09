# Security review and verification status

Usability and upload integrity reviewed **10 November 2026** for **0.2.17**. This is a summary of
recorded checks, not a new vulnerability scan or a certification of security.

[Security boundary and reporting](SECURITY.md) · [Historical audit records](docs/SECURITY-AUDIT-HISTORY.md) · [AI reliability](docs/RELIABILITY-AND-COST.md)

## Current release evidence

| Check | Recorded result |
|---|---|
| Offline regression suite | 350 passed in the full local suite; native CI repeats the suite |
| Native builds | Windows x64, Apple Silicon, Intel Mac and Linux x64 passed |
| Packaged backends | Self-checks passed on all four native CI targets |
| Mac packages | Native signature and DMG checks passed for both architectures |
| Linux packages | DEB and AppImage checks passed |
| Published release | Five installer downloads, four provenance manifests and 28 assets; checksums and signed updater feed verified |
| Interface | Windows browser checks covered light/dark and full/narrow desktop windows with no browser errors |
| Apple Silicon device | User-reported launch after the per-app macOS security override; not an exhaustive independent GUI test |
| Intel Mac / Linux devices | GUI and complete install/update workflows still need device testing |

The current release is [0.2.17 beta](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.17-beta.3). The dated security findings below describe the earlier review; the usability update does not constitute a new comprehensive security audit.
The repository documentation can be updated without replacing its installers.

## 10 November upload and review checks

- Same-name document replacement extracts and stages a complete index before
  switching the file, registry and index pointer. A durable recovery journal
  preserves the previous version if publication fails or the app stops mid-swap.
- Per-file results isolate failures; retries and deterministic kept-copy names
  avoid duplicating successful uploads. Types and syllabus flags are preserved.
- Mistake retries enforce ownership, current evidence/check versions and quarantine
  eligibility without exposing keys. Deliberate review is excluded from mastery.
- Desktop browser verification covers upload choices, planning, grouped search,
  source bookmarks and check details at 900/1440 pixels in both themes.
- Sidebar coordinates remain stable during repeated workspace scrolling in the
  Windows browser test. Native Linux scrolling still needs device confirmation.

## Reviewed safeguards

- Local-only services, protected native controls, credential-store keys and
  restricted window navigation.
- Bounded extraction, archive/path/XML checks, sanitised rendering and bounded
  mathematical evaluators.
- Atomic study publication and rollback; private solver keys/reviewer output
  excluded from public verification receipts.
- Source freshness, checked-cache versions and untrusted personal imports.
- Verified backups and encrypted portable exports; passphrases are not retained.
- Signed/version-bound updates and verified block reuse with a full-download fallback.
- Official CI tool downloads with HTTPS/API authentication, size/digest checks,
  a temporary private gateway and no packaged credentials.

These statements describe implemented boundaries and recorded tests. They do
not certify every possible call path, native library, model output or device.

## Dependency review dates and unresolved risk

The recorded Python/npm dependency reviews are dated **7 November 2026** and
reported no known published vulnerabilities at that time. They are not presented
as fresh scans for this documentation pass.

The recorded Rust review includes Linux GTK's `glib` 0.18.5 advisory
[RUSTSEC-2024-0429](https://rustsec.org/advisories/RUSTSEC-2024-0429.html), also tracked
[upstream in Tauri](https://github.com/tauri-apps/tauri/issues/12564). Its fix is
outside the reviewed GTK3 dependency range. No validated repair is claimed here,
and absence of a direct app call does not prove it is unreachable through dependencies.

Recorded maintenance notices for `proc-macro-error`, `zbus_names`, `zvariant`
and `zvariant_derive` remain distinct from identified exploit reports. See the
[dated audit history](docs/SECURITY-AUDIT-HISTORY.md) for scan scope and details.
A stable-release claim still needs current dependency review and target-device tests.

## Distribution and AI limits

Windows has no publisher certificate; macOS bundles are ad-hoc signed and not
Apple-notarized. A signed updater does not remove OS trust warnings. Use
[opening instructions](docs/TROUBLESHOOTING.md), not global security disabling.

Acceptance is not correctness. Solver/verifier agreement, source checks and
policy gates reduce risk but cannot guarantee truth, originality or difficulty.
Read [dated evaluation results](docs/RELIABILITY-AND-COST.md), not a single test
percentage as a universal reliability claim. Legal/licensing scope is covered
separately in [Compliance](COMPLIANCE.md) and [Third-party notices](THIRD-PARTY-NOTICES.md).
