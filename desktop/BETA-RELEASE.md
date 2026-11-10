# Study Desk 0.2.21 beta

- Consistent desktop header/theme spacing across every view and a clear gap before expanding saved sessions.
- Native Save dialogs for exports, saved-location confirmations, cancellation feedback and readable empty-export errors. Failed downloads keep the app open.
- Short personal recall cards and explicit, independently checked AI proposals from completed verified questions. Original practice questions and FSRS history are preserved; Anki exports concise cards.
- Clear course bundles versus revision-sheet transfer, plus cleaner saved-session previews and a first-run course-material shortcut.
- Sidebar feedback form with optional screenshot file uploads (five images, 10 MB each). Google sign-in is required for uploads; automatic email collection is off, but Google associates uploads with the signed-in account. No logs or keys are attached automatically.

Builds cover Windows x64, Apple Silicon, Intel Mac and Linux x64. Native CI checks
are required for publication. Windows Save/cancel workflows have local GUI testing;
complete Mac/Linux GUI testing still needs device confirmation. Apple notarization
and Windows publisher signing are not included. Automated AI checks can miss mistakes.

- Redesigned the shell around Today, Study modes and Library sections.
- Added Ctrl+K / Command+K jump palette, scroll-aware Library tabs, a Progress-to-Today shortcut, and actionable empty states.

- Restored missing apostrophes in workspace copy so Today’s queue renders correctly.

- Consistent custom file pickers and empty-state actions placed below their explanatory text.
