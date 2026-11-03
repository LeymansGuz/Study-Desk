# Local security boundary

Study Desk Local is a personal, single-owner workspace. Other software or OS
users on the same computer may access its loopback service or files. It is not
an isolation boundary between OS users. Keep the project folder, `.env`, study
data and backups private. API keys are stored locally, not encrypted by the app;
file access follows your OS account and folder permissions.

Use Setup.cmd, Start.cmd, Stop.cmd and Status.cmd. The web service binds to
127.0.0.1:8002, ignores proxy headers and rejects unexpected Host, Origin and
cross-site browser requests. Private OPA binds separately to 127.0.0.1:8182,
requires a fresh token, and permits that token only for health and tutor decisions.
Policy/data administration is denied. Tutor decisions fail closed if OPA fails.

Stop verifies process birth identities before terminating anything. It requests
a graceful shutdown with a separate private control token, then cleans up its
recorded processes and captured OCR workers. It never kills processes just by
name or port. Start refuses occupied ports. Runtime tokens stay in data/runtime,
are not returned by the browser API and are cleared on stop.

Uploads have size/page/type limits and validated paths. ZIP/DOCX packages have
entry-count and unpacked-size limits. Word DTD/entity declarations are rejected
before parsing. Markdown and SVG are sanitized, mathematical rendering disables
trusted commands, and CSP permits only local scripts. Configuration, databases,
control state and backups are not statically served. Mathematical expressions
use bounded evaluators, not arbitrary Python execution. Results are independently
checked before atomic publication.

Backups use a consistent SQLite snapshot, serialize workspace changes and refuse
creation while indexing is queued/running. Verification checks archive/database
integrity against the local schema. Backups contain private educational content.

Setup installs the locked dependencies. Missing OPA binaries come from a pinned
official HTTPS release and must match its published SHA-256. TLS certificate
verification stays enabled, with current trusted CA roots. Windows prerequisite
installation uses WinGet. Keys use hidden input and are not process arguments.
Providers receive relevant excerpts when you request generation. Tracing is off.

Chroma is used through its embedded PersistentClient, not an exposed HTTP server.
Known upstream dependency advisories remain documented in SECURITY-AUDIT.md.
Do not publish this personal app or Chroma through a tunnel or network. Review
updates and re-run setup/tests when changing the dependency lock.
