# User guide

[README and downloads](../README.md) · [Troubleshooting](TROUBLESHOOTING.md) · [AI connection and pipeline](AI-AND-PIPELINE.md)

## Choose a study view

| View | Use it for |
|---|---|
| Today | The active course, next actions, exam countdown and quick starts. |
| Study | Practice, Explain and Ask in one place; switch modes without losing your course. |
| Workspace | Course files, document types, previews, indexing and course scope. |
| Progress | Review totals, mistakes, exam planning and practice suggestions. |
| Library | Saved sessions, unified search, checked guides, sheets, mock exams and transfers. |
| Settings | AI connection, usage statistics, backups and application updates. |

Switching views preserves the current inputs and work. Save changes to revision
sheets before closing the application.

## Add and organise course files

1. In **Workspace**, choose or create a course and add its files.
2. Use the file picker, drag/drop, or paste a screenshot into the attachment area.
3. Choose each selected file’s document type before upload, or apply the shared type to all selected files.
4. For existing filenames, choose **Replace**, **Keep both** or **Skip** in one review. Identical files are skipped. A replacement keeps the existing document type, syllabus choice and bookmarks; the old PDF and index remain available until the new index is ready.
5. Wait for indexing to finish; per-file upload results and background jobs appear in Workspace. Failed files stay selected for retry; successful files are not uploaded again.
6. You can also set document types individually or select visible files and use
   **Set document type → Apply to selected**. Editing keeps their order and page.

| Document type | How it is used |
|---|---|
| Syllabus / learning outcomes | Allowed course scope and exclusions. |
| Notes | Primary teaching material and supported methods. |
| Past paper | Assessed methods and course-relative depth. |
| Exercise / assignment | Primary practice methods. |
| Marking scheme | Supporting reasoning and assessment evidence. |
| Exam report | Supporting expectations and assessment context. |

The per-document syllabus toggle excludes a file from **Any syllabus topic**
selection. **Course scope** adds learning objectives, allowed methods or excluded
topics for the selected course. It requires a specific course selection.
Administrative instructions are not learning objectives.

Uploads index automatically. Use **Index maintenance → Rebuild course index**
only when existing files cannot be found during study. Rebuilding keeps document
types and scope settings, runs in the background and makes no AI generation calls.

### File limits

| Input | Limits |
|---|---|
| Workspace batch | 50 files, 500 MB total; 200 MB per document |
| Workspace formats | PDF, TXT, Markdown, Word, PNG, JPEG and WebP |
| PDF | 300 pages |
| Screenshot | 20 MB, 16 megapixels |
| Ask a question | 5 attachments, 50 MB total; 20 MB each |
| Question extraction | 20 relevant pages across attachments; 30,000 combined characters |

Selections show names, sizes and image previews. Remove individual files before
uploading; failed requests preserve the remaining selection. Scans take longer
than text PDFs because OCR runs locally. Unchanged extraction is reused.

## Practice and feedback

- Choose a course, topic selection, difficulty and question type, then start.
- **Easy:** direct application. **Medium:** a small interpretation or method choice.
- **Hard:** meaningful application or justification. **Insane:** one bounded extra insight.
- Long answers use structured results; essays use connected paragraphs.
- Figures are added automatically when the evidence supports a checked maths diagram.
- Submit an answer to see which parts are correct. Hints address the current error;
  solution disclosure follows the configured attempt rules.
- For an unsuccessful generation, read the named stage and reason. Existing work
  is preserved and partial questions are not saved.

**Concept mastery path** requires a specific topic and one question type. It
prepares Foundation (Easy), Application (Medium) and Synthesis (Insane) one at a
time. Pass the current stage, then select **Continue mastery path**. A failed
continuation can be retried without losing completed stages.

New practice avoids retained tasks and number-only variants. Deliberate bank
review and flashcard review can repeat them. See [repetition rules](AI-AND-PIPELINE.md#repeated-study-requests).

## Explain a concept

1. Select the course and topic, then choose **Brief overview** or **Deep dive with examples**.
2. Read **Core Concept**, **Key Formulas**, **Worked Example** and **Common Pitfalls**.
3. Use **Test my understanding** to open Practice with the topic and Medium difficulty.
4. Use **Recall checkpoint** to explain the concept in your own words and receive checked feedback.
5. Choose **Save revision sheet** to reuse the explanation without another generation call.

Recall uses checked explanations and course evidence, not your personal edits.
Changed sources require a fresh checked explanation before new recall grading.

## Ask a question with attachments

1. Type a question or add its files/screenshots. Attachment-only questions are supported.
2. Choose **Read attachments locally** and review the extracted text.
3. Correct OCR mistakes and confirm essential symbols and diagram facts before tutoring.
4. Start tutoring once the complete question is readable.

OCR reads text; it does not understand arbitrary graph or diagram relationships.
Reading attachments makes no AI call. Successful extraction is temporarily cached
for retries; questions over the context limit are rejected rather than cut off.
If **Paste screenshot** is unavailable, focus the attachment area and use
**Ctrl+V** on Windows/Linux or **Command+V** on Mac.

## Review, plans and the study library

**Continue studying** shows your three latest sessions first; expand to see all ten.
Each card identifies its course, activity and status. One course selection applies
to document search, the checked guide, bookmarks and bank exams. Imports, exports,
Anki and card management are grouped under one expandable utility panel.

In **Progress**, first-attempt accuracy and eventual completion are separate.
**Try again** on a mistake reuses the same currently eligible verified question.
If it is stale or quarantined, prepare fresh practice or explain the concept.
This review makes no generation call; answer feedback can use AI. Bank exams and
deliberate retries do not increase independent-practice or mastery totals.

| Tool | How to use it |
|---|---|
| Today's study queue | In Progress, choose **Start next** for due cards, unfinished work, mistakes or a revision activity. |
| Time and exam date | Set a daily budget of 5–180 minutes and an optional countdown. Dates use **dd/mm/yyyy**. |
| Course study plan | Choose a course and exam date. Uses your daily study time by default; a course-specific override and custom topics are tucked under optional settings. Missed topics roll forward; mark reviewed topics yourself. |
| Next-topic suggestions | Appear automatically with the reason for each suggestion. Uses local outcomes and source evidence; repeated same-question attempts do not establish retention. |
| Revision sheets | Edit Markdown with a preview, add personal notes, export or prepare practice. Edits are labelled unverified. |
| Checked course guide | Open to read collected checked explanations and source sections still to explain. Creating or refreshing a section uses AI. Editable revision sheets remain separate personal copies. |
| Find your study work | One search shows saved work and extracted text from the selected course in separate groups. Open a result’s original page. Diagrams without extracted text are not searchable. |
| Page bookmarks and notes | In an original document or source preview, expand **Bookmark this page**. The referenced page is prefilled; if you navigate inside the PDF, enter that page manually. Changed sources and missing pages are flagged. |
| Verified bank mock exam | Uses the library’s shared course selector. Select 1–10 existing checked questions; optionally filter topic, difficulty, type or unseen items. No questions are generated to fill a shortage. |
| Paper summary | Review solved questions, first-attempt results, attempts and revisit items; export Markdown. Its percentage is practice completion, not a predicted exam mark. |
| FSRS cards | Review due cards using the rating controls. Full practice questions keep their review history. Export concise cards to Anki as UTF-8 TSV with HTML enabled. |
| Personal imports | Import up to 200 plain-text TSV card pairs, at most 2 MB. HTML/cloze directives are not interpreted. |
| Course transfer | Import/export course ZIPs with original files, document types, syllabus choices and personal revision sheets. Imported sheets/cards do not inherit verification. |

Bank selection, local planning, search, personal editing and export make no AI
inference calls. New explanations, tutoring, grading and hints can use your provider.
Plans use estimates and self-reported review; they do not certify mastery.

### Retention and bounded lists

| Item | Retention/display |
|---|---|
| Saved study sessions | 10 most recent visible sessions; child questions follow their parent path/exam |
| Revision sheets | 20; displayed five per page |
| Recall results | 10 latest successful results |
| Checked guide sections | Up to 20 per course |
| Course plans / guides / local jobs | Up to 20 of each |
| Page notes | Up to 200; displayed ten per page |
| Document search results | Up to 25 |
| Practice avoidance | 2,000 retained exposures across index revisions |

Export important work if you need a permanent archive outside these limits.

## Backups and data

| Edition/system | Study-data directory |
|---|---|
| Windows desktop | `%APPDATA%\link.spookelgoose.studydesk` |
| macOS desktop | `~/Library/Application Support/link.spookelgoose.studydesk` |
| Linux desktop | `$XDG_DATA_HOME/link.spookelgoose.studydesk`, usually `~/.local/share/link.spookelgoose.studydesk` |
| Source edition | The project's `data/` folder |

- **Settings → Local maintenance:** usage, estimated costs, recent outcomes,
  **Create backup** and **Verify backup**. Wait for indexing to finish first.
- **Backup protection:** optional daily/weekly local backups while the app is open;
  up to ten unencrypted archives are kept for 30 days.
- **Encrypted portable backup:** use a 12–256 character passphrase. It is not saved
  or recoverable. Restores accept up to 256 MB and apply on restart after confirmation.
- API keys stay in the system credential store and are excluded from backups.
- Ordinary working files and local backups are unencrypted; keep them private.

Close Study Desk before copying its data. For a source-to-desktop transfer, stop
both editions, back up `data/`, then copy its contents into the desktop data
folder. Do not copy `.env`, `.tools`, `.venv` or `audit/`; enter keys in Settings.

## Updates and removal

Use **Settings → App updates** to check, download, then install while idle.
The app verifies a complete package and a pre-install data backup. Cached blocks
can reduce download size; initial/unsupported downloads use the full package.
A failed verification installs nothing. A backup does not promise automatic
rollback to an older database version.

Close the app before uninstalling. Use Windows installed-apps settings, remove
the Mac app from Applications, uninstall the Linux DEB, or delete the AppImage.
Uninstalling preserves desktop study data and saved credentials. To erase them,
remove the data directory, backups/exports and provider credentials separately;
see [Privacy](../PRIVACY.md). Source users should stop services before deleting
the project folder, which also contains their study data.

## Recall cards and exports

- In **Progress**, choose **Create a short recall card**. Write one idea: prompt
  up to 25 words, answer up to 50 words. Keep essential conditions. Personal cards
  are not independently checked.
- In **Library → Import, export and manage personal study work → Manage
  review cards**, full practice questions offer **Propose short cards (AI)**.
  The original must be completed, have a disclosed solution and remain eligible
  in the verified bank. A suitable paid model drafts and separately reviews
  1–3 cards. Preview them, then save. This uses AI only when requested.
- The original question and its FSRS history stay intact. New recall cards have
  separate schedules. Anki export includes concise cards only; a full problem is
  kept for practice rather than cut down arbitrarily.
- Exports open a native **Save** dialog in the desktop app. Choose the folder;
  the app reports the saved path, cancellation or a readable error beside the
  action. Source/browser users should check their browser's Downloads list.
- A **portable course bundle** includes documents, roles, syllabus choices and
  personal revision sheets. **Export revision sheets** is a smaller JSON transfer
  for sheets only, not a readable study document. Use a sheet's Markdown export
  for reading or printing. Select the course before exporting its sheets.
- Empty exports show an explanation and keep the app open. Anki cards export
  across courses; revision sheets and course bundles use the selected course.

## Send beta feedback

Choose **Send feedback** in the sidebar. Optionally copy the previewed app version,
operating system, provider and model into the form. Keys, documents and diagnostic
logs are not attached automatically. Describe what happened and what you expected.
Screenshots are optional file uploads: up to five images, 10 MB each. Google sign-in
is required; automatic email collection is off, but Google associates uploads
with your account and warns that account identity is recorded. Only enter contact details if you
want a reply, and hide private content in screenshots. Submissions go to the
maintainer through Google Forms/Drive; see [Privacy](../PRIVACY.md).
