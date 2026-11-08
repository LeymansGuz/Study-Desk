# Study Desk

A private, document-grounded study workspace for your computer. The desktop
application opens in its own window, stores study data locally and uses your own
AI provider API key. The source edition can also run at **http://127.0.0.1:8002**.
Both editions open directly as the local owner.

## Install the desktop application

The current published beta is [v0.2.15-beta.3](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.15-beta.3).
Choose an installer for your computer; the source-code ZIP is for source setup.
Desktop users do not need Python, Node.js or a `.env` file.

| Computer | Download |
|---|---|
| Windows x64 | [Setup executable](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/Study-Desk_0.2.15_x64-setup.exe) |
| Apple Silicon Mac, macOS 14+ | [aarch64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/Study-Desk_0.2.15_aarch64.dmg) |
| Intel Mac, macOS 14+ | [x64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/Study-Desk_0.2.15_x64.dmg) |
| Linux x64 | [DEB](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/Study-Desk_0.2.15_amd64.deb) or [AppImage](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/Study-Desk_0.2.15_amd64.AppImage) |

The release also provides [SHA256SUMS.txt](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.15-beta.3/SHA256SUMS.txt)
and build manifests. For your own local build, installer files are in `dist/installers/`.

**Windows:** run the setup executable, install it for your Windows user, and open
**Study Desk** from its shortcut or the Start menu.

**macOS:** open the DMG, drag **Study Desk** into **Applications**, eject the DMG,
then open Study Desk from Applications. Beta builds are **ad-hoc signed but not
Apple-notarized**. If macOS blocks it, first verify the download against
`SHA256SUMS.txt` and check that you chose the matching architecture. A damaged-app
warning can also indicate a bad download or signing problem; do not assume it is
harmless. For a verified, trusted beta download blocked by quarantine, run:

```bash
xattr -cr "/Applications/Study Desk.app"
```

Then launch it from Applications. Do not disable Gatekeeper system-wide. Intel
and Apple Silicon DMGs use separate builds; do not mix them.

**Linux DEB:** on Ubuntu/Debian, install the downloaded file with your package
manager, or run this from the download folder:

```bash
sudo apt install ./Study-Desk_0.2.15_amd64.deb
```

**Linux AppImage:** make the downloaded file executable in its file properties,
then open it. The equivalent terminal commands are:

```bash
chmod +x ./Study-Desk_0.2.15_amd64.AppImage
./Study-Desk_0.2.15_amd64.AppImage
```

Linux builds target Ubuntu 22.04. Other distributions may need additional system
libraries, especially `libwebkit2gtk-4.1-0` and `libsecret-1-0`. If the AppImage
reports missing FUSE support, install `libfuse2` or run it without FUSE:

```bash
./Study-Desk_0.2.15_amd64.AppImage --appimage-extract-and-run
```

Use the DEB for a system installation with package-managed dependencies. Saving
an API key needs an available Secret Service or KWallet credential backend.

### First launch

1. Open **Study Desk**. Review the data-use notice and usage terms before enabling AI. You can defer this and use Workspace.
2. In **Settings → AI connection**, choose a provider and enter your own key.
   Click **Save and use** once to save the key; the model catalog then loads
   automatically. Select a model and (for OpenRouter) its hosting endpoint, then
   click **Save and use** again. Keys use the system credential store; no `.env`
   editing is needed. The current provider and model are shown above the form.
   Saving a key and listing models make no generation request.
3. Upload your course documents in **Workspace**, wait for indexing, and start
   studying. Close the app to stop its private services; reopen it to resume.

The installer bundles Python, Node.js, OPA and native processing dependencies.
Users need internet access for hosted AI providers and may need an initial embedding-model
download. Study data is kept outside the installation directory, so program
updates preserve it. The initial installer is unsigned.

The four platform builds passed native CI builds, offline regression tests and
packaged-backend checks. Windows has also received graphical checks. macOS and
Linux graphical behaviour remains experimental and needs testing on your device.

### Updates inside the app

In **Settings → App updates**, choose **Check for updates**, then **Download update**.
The app prepares a complete package from the official GitHub release and verifies
its signature and signed version. Choose **Install and restart** when requests,
uploads and indexing are finished. Study Desk creates and verifies a local backup
before replacing the program. Documents, progress and your system credential stay
separate from installation files. A failed check/download installs nothing.
If installation cannot finish, reopen the app and check its installed version
before retrying. Backups support recovery; they do not guarantee automatic
database downgrades.

Updates are manual. Cached package blocks can reduce the download, with a full
download as the safe fallback described below.
If your installed version has no **App updates** section, install the current
release manually from the links above.
On Linux, the AppImage must be writable by your user; DEB updates may request
administrator permission. On macOS, run from Applications rather than the DMG.
Update signatures do not remove OS warnings about unsigned/not-notarized apps.

### Smaller update downloads

The updater uses a signed content-defined block map to reuse matching bytes
from its last verified package or an interrupted download. Only missing blocks
are requested. It verifies block hashes, reconstructs a complete package and
checks its version-bound signature before allowing installation. The normal
installer then applies that complete verified version; running app files are
never patched by the downloader. The pre-install backup and idle checks apply.

Without a usable cache, the first download is a full package. A full download is
also used when reuse would save little, the server cannot supply byte ranges,
or acceleration metadata is unavailable. Download status distinguishes bytes
downloaded from bytes reused. Actual savings depend on how much the release
changes. Windows files are compressed individually to preserve reusable blocks;
this can make the initial installer larger than a solid compressed archive.

The app-data `update-cache` keeps one verified package and one partial download,
separate from study files and backups. Removing that cache while the app is
closed is safe; the next update may need a full download. Leave enough disk
space for the cached/staged packages and installation.

### AI providers, free allowance and model choice

Settings supports DeepSeek, OpenRouter, OpenAI API, Claude API and custom
OpenAI-compatible Chat Completions endpoints, including suitable loopback local
servers. Direct OpenAI uses the Responses API; Claude uses its Messages API.
Provider API credentials are required; signing into a chat website does not
configure an API connection. Model access depends on your account and location.
Direct OpenAI and Claude do not currently list Hong Kong as a supported region;
an aggregator does not waive a model provider's regional terms.

New connection setup opens with OpenRouter and **Free only** selected. Free models
are experimental and currently support **Brief overview** in Explain a concept
only. The tested free candidates performed substantially worse than the calibrated
paid DeepSeek Flash setup for question generation. Free connections cannot generate
questions, grade answers, run mastery paths or request deep explanations; these
restrictions are enforced on the backend even when Free only is unchecked for a
known free model. Brief explanations retain the independent example solve,
grounding, arithmetic and verifier checks and can be withheld when checks fail.
Existing working connections are preserved. Availability in a catalog does not
certify question quality or regional eligibility. Check both model and
hosting-provider terms. Free requests pin the selected host, disable fallback and
cap prompt/completion/request/image prices at zero.

The model catalog loads automatically when a key is saved or you return to a
provider with a saved key. Each provider retains its own key and last saved model
selection; leave the key field blank to reuse it. Save is unavailable while
connection details or hosting endpoints are loading, and after a failed hosting
lookup until an eligible endpoint is selected.

Text-generating models are shown; known non-text services are excluded. Price
labels distinguish Free and Paid from rates not provided by a catalog; incomplete
metadata is never treated as free. Direct DeepSeek Flash and Pro display official
peak/off-peak token rates (checked 6 November 2026), including cached input.
Provider invoices and current published rates control. Advanced controls
allow a manual model ID and JSON/reasoning settings. Mandatory-reasoning models
may be slow or exhaust the stage's output budget. Schema support does not replace
independent answer, grounding, arithmetic and source-copying checks.

Free allowance covers every provider request: generation, solving, verification,
repairs, explanations, feedback and hints. The app shows the provider's remaining
daily allowance when supplied. Local estimates cannot include other apps or
earlier runs. Free generation workflows queue locally, outside the generation
deadline; calls are paced and bounded, insufficient known allowance is rejected
before a workflow's first call, and quota errors stop retries. There is no
automatic paid fallback. Inputs and completed study work are retained on failure.

Paid connections may consume provider allowance or incur charges; the setup form
shows a plain notice rather than extra checkboxes. Statistics record the
provider/model and actual returned tokens; unsupported pricing is shown as
unknown rather than applying DeepSeek prices. Provider invoices control.

Source installations may use the optional credentials in `.env.example` or the
same Settings flow. Desktop installations ignore developer credential environment
variables and store separate keys per provider in the operating-system keyring.
Custom endpoint keys are scoped to the saved endpoint. Remote endpoints require
HTTPS; HTTP is allowed only for loopback servers. Models are experimental unless
explicitly marked tested, and no model switch takes place inside a running request.

### Data use and permissions

The [data-use notice](PRIVACY.md), [usage terms](TERMS.md) and
[third-party notices](THIRD-PARTY-NOTICES.md) are also in Settings. AI requests
send relevant excerpts, questions and attempts to your selected provider (and
OpenRouter hosting endpoint), consuming your account allowance and possibly
incurring charges. The backend requires current acknowledgement; withdrawal in Settings
blocks future AI requests. Upload only material you may lawfully process.
Working study data and ordinary local backups are unencrypted. Encrypted portable
backups are available in Settings; their passphrase is not saved.
See [compliance scope](COMPLIANCE.md) for remaining responsibilities.

## Platform support

| Platform | Status | How to run |
|---|---|---|
| Windows 10/11 (x64) | Primary desktop target; source lifecycle and packaged backend tested | Installer, or source launchers below |
| macOS 14+ Apple Silicon (arm64) | Published experimental DMG; target-device GUI untested | Download the aarch64 DMG above |
| macOS 14+ Intel (x86_64) | Published compatibility DMG; ONNX Runtime 1.23.2 | Download the x64 DMG above |
| Linux x86_64 | Published experimental DEB/AppImage; target-device GUI untested | Download the DEB or AppImage above |
| Linux arm64 | No packaged build; native dependencies not validated | Requires separate dependency/build work |
| Windows arm64 | No native validated package; dependency support is unverified | Requires separate compatibility/build work |

**The source edition is installable through the terminal.** The `.cmd` files are
Windows-only. Setup, start, status and stop are Python launcher commands that
also have macOS/Linux paths. Desktop packaging is described separately above.

The release tests pass on Windows. The macOS code paths use standard POSIX APIs
(`fcntl`, `ps`, process groups) and download the official `darwin_arm64` or
`darwin_amd64` OPA binary, but the full macOS setup/start/stop lifecycle has not
been live-tested in this release. The commands below are the supported path.

## Study tools

- Practice original, document-grounded questions at Easy, Medium, Hard or Insane.
- Multiple choice, short answer, calculation, long answer, essay, proof and
  true/false questions, with automatic mathematical figures where supported.
- Independent Solver and Verifier checks, bounded symbolic/calculator checks,
  source-clone screening and OPA rules for hints and answer disclosure.
- Course-grounded explanations, worked examples and a bridge to Medium practice.
- Socratic tutoring for your own questions and text extraction from attachments.
- Course documents, resumable uploads, background indexing, original-file
  previews, source evidence and per-document syllabus inclusion.
- A topic-specific, three-stage concept mastery path, saved sessions, a verified question bank,
  mistakes and FSRS review cards.
- Bank-only mock exams with 1–10 existing verified questions, saved progress,
  a final paper summary, in-place question review and Markdown export.
- Light/dark themes, cached-token and five-decimal USD cost diagnostics, and local backups.

Documents define the permitted methods and course-relative depth. Easy is a
direct application; Medium adds a small interpretation or method choice; Hard
requires a meaningful application or justification. Insane adds one bounded
insight within the selected objective, without stacking extensions or lengthy
arithmetic. There is no minimum subpart count: a long answer can be one coherent
worked task or at most two connected parts. Essay answers develop an argument
in paragraphs. The independent checks increase confidence; they cannot guarantee
every generated answer is correct.

### Repeated study requests

| Workflow | What stays consistent and what changes |
|---|---|
| Any syllabus topic | Prefer less-used eligible sections and primary chunks; course reindexing does not reset practice avoidance. |
| Specific-topic practice, mastery paths and follow-ups | Keep the requested concept and covered methods; change the task/inference, not only its numbers. Known repeats are withheld. |
| Explain and revision guides | Use stable, representative evidence and reuse a checked explanation for the same topic, depth and current course/check version. Do not randomly replace a thorough explanation with a niche fragment. |
| Ask a question | Preserve the supplied task and option order. Repeated input should receive a consistent verified answer, not an invented variant. |
| Bank exams and spaced review | These deliberately revisit verified material. Bank exams prefer less-practised items; the existing unseen-only filter prevents reuse. |
| Recall, marking and hints | Judge the current answer consistently, preserve previously correct parts and adapt hints to the student's actual error and attempt. |
| Plans, recommendations, search and source reading | Results change with study progress or documents; repetition is useful when the underlying state has not changed. Unchanged document extraction is cached. |

Primary question topics come from **Notes**, **Exercise / assignment** and
**Past paper** documents. **Syllabus / learning outcomes** constrains scope;
**Marking scheme** and **Exam report** material supports assessment and difficulty.
Administrative marking instructions and performance statistics are not selected
as study topics. The existing preflight compares the candidate's inference with
nearby previous tasks, in addition to source-copy and local duplicate checks;
this adds no separate model request per question. MCQ identity includes option
bodies and ignores their display order.

Practice avoidance checks the **2,000 most recent retained question exposures**,
across course index versions and source filters. Exact/number-only matches are
checked across that history; a bounded shortlist receives local semantic checks.
Worked examples already shown by Explain are also avoided by the practice bridge.
Only a compact relevant avoidance list is sent to the model. This avoids extra
provider calls and unbounded history growth. It cannot promise unlimited novel
questions from a finite topic; exhaustion is reported instead of silently
returning a known repeat. Explicit review remains available.

Cached explanations need the current validation version before they can be
reused as checked references or used to grade recall. Saved material remains
readable when a fresh check is needed. New practice-bank entries must meet the
current question-validation policy.

## Files, screenshots and local reading

Workspace and Ask a question accept file-picker selections, drag/drop and pasted
screenshots. Paste into the attachment area or form, or choose **Paste screenshot**.
Normal text paste still works. If the system WebView cannot read the clipboard
through that button, focus the attachment area and use Ctrl+V (Windows/Linux) or
Command+V (Mac). Clipboard access is user-initiated; it is not monitored.

Selected files show names, types, sizes and screenshot previews. Remove files
individually or clear the selection. Workspace selections are paged in groups of
ten. Selections survive tab switching and failed requests within the open app.

| Upload destination | Limits |
|---|---|
| Workspace | 50 files / 500 MB total per batch; 200 MB per document |
| Workspace screenshots | PNG/JPEG/WebP, 20 MB and 16 megapixels per image |
| Ask a question | 5 attachments for one question, 50 MB total, 20 MB per file |
| Question reading | 20 relevant pages across all attachments; 30,000 characters for the combined question/context |

Workspace also accepts PDF, TXT, Markdown and Word documents. The existing
300-page PDF safety limit remains. Larger batches queue background work; more
scanned pages naturally take longer. Text PDF pages use their existing text layer;
screenshots/scanned pages use local OCR. Unchanged workspace-image extraction is
checkpointed and can be reused on subsequent indexing.

In Ask a question, **Read attachments locally** shows editable extracted text and
per-file progress. Attachment-only questions are supported. OCR warnings require
confirmation that symbols and essential diagram facts have been checked before
tutoring. OCR reads text; it does not interpret graph/diagram relationships.
Reading attachments makes no AI call. Successful extraction is reused for
retries; the server text cache is bounded and expires for reuse after 30 minutes.
The normal Solver/Verifier pipeline runs once for the combined question. Context
limits are unchanged, and excess text is rejected rather than silently cut off.
Future AI requests still require the current data-use acknowledgement.

## Daily study, revision sheets and recall

**Progress → Today’s study queue** combines due FSRS cards, unfinished practice,
recoverable mistakes, a verified bank question and a recent revision sheet.
Choose **Start next** to open the activity in place. **Time and exam date** sets
a 5–180 minute daily budget and an optional exam countdown. The queue is rebuilt
from current saved work each time you review; its times are estimates. Planning
makes no AI calls. This is a daily queue and countdown, not a complete multi-week
syllabus timetable.

After a checked explanation, choose **Save revision sheet**. The checked text
and source references are reused without another generation call. In **Learning
tools**, open the sheet to edit Markdown alongside its preview, add personal
notes, view original source evidence, export Markdown or prepare practice for
the concept. Save controls remain visible while editing. Unsaved edits are kept
when changing views and you are warned before discarding them. Saving persists
them across restarts. Local edits are labelled as not independently checked.

The 20 most recently saved sheets are retained, shown five per page. Source
changes mark a sheet historical. Prepare a fresh explanation and save it to
refresh that topic; replacing local edits requires confirmation, preserves
personal notes and checks for changes made in another window. Export important
sheets if you need a separate permanent archive.

**Explain a concept** separates the covered principles from source exercise setups
before drafting an original application. A blind Solver supplies the worked
solution; local arithmetic, symbolic and formatting checks plus an independent
source review must pass before the explanation is saved. One bounded repair is
allowed for paid connections. Ordinary work has a 60-second deadline; a
feedback-guided practice repair may use one additional 15-second grace period.
Deep explanations and extended supplied tasks use the 90-second complex budget.
Queue waiting does not consume these processing deadlines. The same unchanged example reuses its checked
solution when only the surrounding explanation needs correction. Unsupported
course topics and copied examples are withheld.

**Ask a question** preserves the supplied question and option order. A faulty
private calculation plan gets one independent retry without changing the public
givens. Parameter-dependent results remain symbolic; the app does not invent
numbers to satisfy a calculator. Proofs and extended supplied tasks use the
existing bounded complex-task deadline, starting after the queue slot is acquired.
Missing essential information, invalid proof claims and incorrect options still
fail verification. Detailed local diagnostics distinguish private-plan retries
from explanation grounding, originality and mathematical failures.

**Recall checkpoint** sits below an explanation. Describe the concept in your
own words; the tutor identifies correct ideas and specific gaps. Corrections
need valid source references, rendered mathematics must compile, and a separate
review checks grounding, accuracy and fair assessment before feedback is shown.
Marking uses the checked explanation and its course evidence, never personal
sheet edits. A source change blocks a new check until the explanation is fresh.
The ten latest successful recall results are saved; the latest result for the
concept can be resumed. Switching views preserves the current typed draft.

Recall assessment sends the typed answer and relevant evidence to the selected
AI provider. It uses an assessment and independent review, and bounded repairs
can add requests. Calls and returned token usage appear in local Statistics.
Free connections remain limited to brief explanations and cannot grade recall.
Automated assessment can still make mistakes; passing review is not a guarantee.

**Search saved study work** searches saved explanations, revision sheets,
personal sheet notes and recent session titles. It is not a full-text search of
all uploaded PDF pages. **Export review cards for Anki** downloads up to 200
existing cards as a UTF-8 TSV file. Import it as tab-separated fields with HTML
enabled. No AI call is made for search, sheet editing, export or daily planning.

## Course planning and source tools

These tools are included in the desktop application and local source checkout.

**Progress → Course study plan** uses indexed source sections or your topic list.
Choose the course, exam date and minutes per course study day. Missed topics roll
forward automatically; the plan warns when work exceeds the remaining budget.
**Mark reviewed** is self-reported progress, not a mastery grade. The next planned
topic also appears in Today’s queue. Suggested practice uses local outcomes and
course evidence, while preserving the normal generation checks. Harder recommendations require first-attempt success on distinct questions across different days; repeated same-question attempts do not establish retention. It does not infer prerequisites or certify mastery.

**Learning tools → Course study library** keeps optional tools together:

- **Course revision guide** compiles checked explanations and citations, excludes
  personal edits, and shows source sections still to explain. New checked
  explanations automatically update the guide. Each course keeps up to 20
  checked sections independently of the ten-session history. Changes to cited documents or syllabus rules invalidate affected sections; unrelated course material preserves checked sections. Explain or refresh one section at a time using your paid
  connection. Compilation and Markdown export make no model calls; the guide
  does not automatically author a whole course textbook.
- **Search document text** builds a local index on first search, searches
  extracted text case-insensitively and opens the matching original page.
  Changed sources require a refreshed index; stale results are withheld.
  Diagrams without extracted text are not searchable. Results are capped at 25.
- **Page bookmarks and notes** save one note per document/page, with up to 200
  retained and ten shown per page. Original PDFs and OCR are unchanged.
- **Import and export personal study work** transfers original documents in a
  course ZIP, preserving document types and syllabus choices for Study Desk
  bundles. Choose a target course first. Imports use the normal local indexing
  queue and 50-file/500 MB batch and 200 MB individual-file limits. Bundled or
  JSON-imported sheets are personal, unverified material. Verification flags and
  trusted citations are never imported; imported items cannot enter the verified
  question bank.
- UTF-8 TSV imports accept plain-text front/back card pairs: up to 200 rows and
  2 MB. Cards use FSRS. Capacity is checked before import and duplicates do not
  consume another slot. **Manage review cards** removes cards without deleting
  original practice results. Anki HTML and cloze directives are not interpreted
  by this plain-text importer.

The app retains up to 20 course plans, 20 guides and 20 local jobs. Search indexes
allow up to 100,000 chunks per course and 40,000 characters per chunk; oversized
indexes are rejected rather than silently published as complete. Search-index
and backup jobs run one at a time, support queued cancellation and explicit
retry after interruption, and make no model calls.

**Settings → Backup protection** offers opt-in daily or weekly local backups
while the app is open. It waits for document indexing and keeps up to ten
unencrypted archives for 30 days. For an encrypted portable copy, expand
**Encrypted portable backup** and choose a 12–256 character passphrase. Streaming
AES-GCM encryption uses a scrypt-derived key and authenticated end marker to
detect tampering or truncation. The passphrase is not saved and cannot be
recovered. Provider keys remain in your system credential store and are excluded.
Encrypted restores accept up to 256 MB, validate the archive/database and replace
local study data on the next restart after confirmation.

DeepSeek-V4.1-Flash remains the paid baseline for checked AI flows. This batch
adds no mandatory generation calls. Free connections cannot generate practice or
new guide sections. Reading checked content, personal notes, search, planning and
transfer tools require no paid inference.

## Concept mastery and bank exams

Bank exams additionally support topic-word filters and excluding questions
already served to you. Filters can reduce availability; no new questions are
generated to fill an empty selection.

In **Practice a topic**, choose **Specific topic**, enter the topic, and choose a
question type. **Concept mastery path** uses that same type throughout Foundation
(Easy), Application (Medium), and Synthesis (Insane). Only the current question is
prepared. Pass it, then choose **Continue mastery path** to prepare the next one.
A failed next-stage request keeps your completed work and can be retried. Resume
saved paths in **Learning tools**. Path generation uses the same source-grounding,
originality, Solver, Verifier, workload and policy checks as ordinary practice.

Documents classified as **Syllabus / learning outcomes** supply the official
allowed scope in the prompt. Content methods still require supporting evidence;
a syllabus awaiting indexing blocks generation until its scope is available.

In **Workspace**, choose **Syllabus / learning outcomes**, Notes, Past paper,
Exercise / assignment, Marking scheme or Exam report for each document. Change
individual types in place, or select files (up to the ten shown on a page), choose
**Set document type** and **Apply to selected**. The current order, page and search
stay in place. Wait for indexing to finish before editing types; saved changes
update both the document registry and retrieval metadata. A failed batch keeps
its remaining files selected so you can retry without repeating successful edits.

Both exam-date fields in **Progress** use **dd/mm/yyyy** (for example,
`21/11/2026`), independently of your operating system's language.

In **Workspace → Course scope**, optionally specify learning objectives, allowed
methods or excluded topics for the selected course. Its index summary counts
extracted sections; it is not a guarantee of complete syllabus understanding.
Uploads index automatically. If existing documents cannot be found during study,
use **Index maintenance → Rebuild course index** for that course. The rebuild
runs in the background with progress, keeps document types and scope settings,
and makes no AI generation calls. It requires documents and cannot start while
the course is already being indexed. Study-file processing keeps at least 1 GiB
of disk space free by default, plus the estimated space needed for new work.

In **Learning tools**, **Verified bank mock exam** draws 1–10 distinct existing
verified questions from a selected course. Filter by difficulty and question type,
or allow a mixture. There is no AI question-generation request and no silent
fallback when too few verified questions match. Current evidence and assessment
versions are required; quarantined or extraction-flagged items are ineligible.
Answer feedback uses the normal tutoring/policy controls and may incur API cost.
Finish each question to proceed; saved exams resume at the current question.
After the last question, the paper summary shows solved questions, first-attempt
success, attempts and questions to revisit. Each question counts equally; the
percentage is practice completion, not a predicted examination mark. Review a
question directly from the summary or download the summary as Markdown.

Generation errors identify the failing stage and a safe reason, such as missing
course evidence, an inconsistent premise, answer disagreement or a timeout.
Technical traces and provider responses stay in local diagnostics. An unsuccessful
generation preserves existing study work and does not publish a partial question.

The generation deadline starts after acquiring a concurrency slot. The default
is 60 seconds; Hard/Insane proof and long-answer requests have a 90-second ceiling,
measured from the same start time. Configure `GENERATION_TIMEOUT_SECONDS` and
`GENERATION_COMPLEX_TIMEOUT_SECONDS` in the source edition's `.env`, then restart
its services. Desktop installers do not load the source checkout's `.env`. These are
upper bounds, not a promise that generation will succeed. Queue waiting is separate.

Independent public-premise and topic checks, strict response schemas, option-key
agreement and bounded working checks supplement the Solver/Verifier pipeline.
Hard and Insane questions receive an additional fresh review. Verified-bank
eligibility requires the current assessment policy and current course evidence.
Review calls use the configured AI provider, so agreement is not a proof of
correctness. Independently check important answers, especially complex proofs.
Some complex questions can still be withheld or time out.

## Estimated reliability

These **7 November 2026** measurements describe the development source checkout
(assessment policy 21), not an independently certified correctness rate. Tests used
DeepSeek Flash, actual question-generation routes and OPA, local semantic retrieval
over frozen excerpts from five real courses, and all seven types at all four levels.
Bank reuse was disabled; caches could warm. They exclude uploading/OCR time and are
not a representative user-traffic or multi-user load benchmark.

The final confirmation accepted **25/28 (89.3%)**,
averaging **29.2 seconds** per accepted question.
Extra same-provider audits marked **25/25** content-clean
and **24/25** clean including difficulty.

| Difficulty | Accepted / attempted | Mean accepted time |
|---|---:|---:|
| Easy | 7/7 (100.0%) | 23.9s |
| Medium | 7/7 (100.0%) | 32.4s |
| Hard | 6/7 (85.7%) | 28.7s |
| Insane | 5/7 (71.4%) | 32.6s |


The baseline accepted 22/28 (78.6%). Intermediate revisions accepted 20/28, 42/56
and 45/56; a later 56-case difficulty-policy run accepted 52/56 but its extra audit
flagged two worked solutions and one difficulty mismatch. The final confirmation
followed fixes for those publication defects. Each final difficulty/type cell has
only one attempt, so this table cannot establish stable per-category percentages.

Acceptance does not guarantee correctness, appropriate difficulty or originality.
Same-provider reviewers can share mistakes. The app retains independent solving,
calculator/symbolic checks, source-clone screening, grounding and OPA gates; uncertain
or rejected work is withheld. Important answers still deserve independent checking.
The 60/90-second ceilings start after slot acquisition; queue waiting is separate.
Normal use may reuse a current verified bank item instead of generating afresh.

### 8 November 2026 tutor-panel checks

A controlled live comparison used frozen excerpts from COMP2121, FINA1310,
MATH2014, DSE Math and DSE Biology, with real local vector retrieval.

| Valid-request confirmation | Accepted | Mean time for accepted requests |
|---|---:|---:|
| Explain: five Brief and five Deep topics | 10/10 | 24.09 seconds |
| Ask: supplied questions, parameters, proofs, multi-part and OCR text | 24/24 | 8.47 seconds |

Every accepted output passed a separate same-provider content audit; all five
invalid/out-of-course controls were withheld. The initial Explain comparison
accepted 7/10, including three examples flagged as source copies by the extra
audit; the final ten explanations had no such flags. Ask already passed all 14
initial ordinary cases: the changes address recorded failures and targeted edge
cases, rather than proving a statistical improvement from a low baseline there.
An additional current-policy smoke check accepted 5/5 valid requests and rejected
2/2 negative controls. These small development samples and same-provider audits
are **not** independent ground truth or a 100% future reliability guarantee.
A separate repeated-practice stress cohort accepted **20/24 (83.3%)**, averaging
**27.99 seconds** for accepted requests. All twenty passed the extra answer/working
audit, but one was flagged as a possible source reskin. All six multi-question
groups passed the cross-question inference-variety audit. Source-reskin screening
was subsequently tightened: a final focused confirmation accepted **5/6** requests
(mean **26.52 seconds**); all five passed the extra content/originality audit, and
the remaining request was withheld as repetitive. Both resulting course groups
passed the cross-question variety audit. These results
show that fresh, varied practice remains less reliable than the tutor-panel sample.
The broader question-generation matrix above and these stress checks measure
different workloads and should not be compared as one benchmark.

## Estimated AI cost

Study Desk charges no application subscription. Requests use your own provider
allowance/balance. Free-model allowances and features are restricted; unknown
pricing is never treated as zero. Settings records actual returned token usage,
cached input and estimated USD cost to five decimal places.

The **7 November 2026 final 28-attempt confirmation** returned the following
price-normalized estimates (including failures and repairs):

| Measure | Off-peak USD | Peak USD |
|---|---:|---:|
| All production generation attempts | $0.14277 | $0.28554 |
| Production cost per attempted question | $0.00510 | $0.01020 |
| Production cost per accepted question, including failed attempts | $0.00571 | $0.01142 |
| Extra evaluation-only audits, excluded from production figures | $0.01164 | $0.02327 |

Production returned 1,001,468 input tokens, including
487,680 cached input tokens, and 107,061 output tokens.
There were 0 missing-usage production records;
unknown/cancelled requests may still be billed. Estimates use the run's configured
peak rates of USD 0.30/M uncached input, 0.006/M cached input and 1.20/M output;
off-peak assumptions are half these rates. Simpler tasks, cache hits and off-peak
pricing can make individual Settings entries much cheaper than this mixed-difficulty
average. These are dated calculation assumptions, not a promise of current tariffs.
Check [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/) and your
provider dashboard for applicable rates and authoritative charges. Cached input is
already part of total input; do not add it twice. Other providers/models can differ.

Hints, grading and explanations can add costs. Bank selection makes no generation
call, although grading can use AI. Local OCR, embeddings and reindexing make no
DeepSeek inference calls. Model-catalog refreshes contact the selected provider.

## Desktop use

Study Desk runs on the Windows, macOS or Linux computer where it is installed.
Its loopback address is available only on that computer. The browser layout fits
both full-size and narrow desktop windows. Windows has graphical checks; all four
native build targets have CI backend checks. Mac/Linux graphical workflows and
the complete source-edition service lifecycle still need target-device testing.

## Source/build requirements

- **Python 3.12** — managed automatically by `uv`; a system Python is not required.
- **Node.js 20 or newer** — checked by setup.
- **OPA 1.21.3** — setup downloads and SHA-256 verifies it on supported platforms.
  A manually installed `opa` on `PATH` is also accepted.
- **Internet access** for the first dependency/OPA setup and for AI generation.
- A modern browser. The app serves only `127.0.0.1`; it is not a public server.

No Docker or separate database server is required. AI generation requires your
own provider API key. Both editions support the providers in Settings. The source
`.env` example uses DeepSeek; a suitable paid text model is required for question
generation. Eligible free OpenRouter models support verified brief explanations.

---

## Windows source setup, activate and deactivate

1. Extract the project into a private folder you can write to.
2. Double-click **`Setup.cmd`** once. Keep the window open until it says setup is
   complete. It installs missing `uv`/Node.js through Windows Package Manager,
   creates the locked Python environment, and checks OPA. When OPA is missing it
   downloads the pinned official binary and verifies its SHA-256 before use.
   Windows may ask you to approve an installer. Internet is needed for the first
   setup.
3. Enter your DeepSeek API key at the hidden prompt. Press Enter to do this later.
   Setup preserves your existing `.env` and study data. It makes no AI requests.
4. Double-click **`Start.cmd`**. It starts both local services, waits for readiness,
   then opens **http://127.0.0.1:8002**. You can close the launcher window.
5. Double-click **`Stop.cmd`** to deactivate the app and its private policy service.
   Your documents, sessions and settings are kept. Closing the browser alone does
   not stop the services.

**`Status.cmd`** shows whether the local services are running. Starting twice
reopens the same workspace; it does not launch a duplicate. Stopping twice is safe.
The app does not automatically start after reboot. Use `Start.cmd` when needed.

Setup uses [uv's documented Windows package](https://docs.astral.sh/uv/getting-started/installation/),
[Node.js](https://nodejs.org/en/download), and
[OPA's official release/checksum mechanism](https://www.openpolicyagent.org/docs).
If WinGet is unavailable, install uv and Node.js 20+ from these official sources,
then rerun `Setup.cmd`. If OPA downloads are blocked by your network, install OPA
from its official documentation and rerun `Setup.cmd`. `uv` selects Python 3.12
using `.python-version`. Setup installs runtime dependencies only; test tools are
optional.

## macOS source install (terminal)

These source instructions target macOS 14+ on Apple Silicon and Intel. The
prebuilt DMG is the simpler option. Apple Silicon users can use Homebrew or the
official tool installers; Intel source setup also needs the native build tools below.

### 1. Install `uv`

With Homebrew:

```bash
brew install uv
```

Or use the official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If the installer says it added `~/.local/bin` to your shell, open a new terminal
before continuing.

### 2. Install Node.js 20+

With Homebrew:

```bash
brew install node
node --version
```

Or install the official Node.js LTS package from
<https://nodejs.org/en/download>.

### 3. Get the source

```bash
git clone https://github.com/LeymansGuz/Study-Desk.git
cd Study-Desk
```

You can also download the ZIP from GitHub and extract it, then `cd` into the
extracted folder.

### 4. Install the locked environment

On **Intel Macs only**, the current cryptography package builds from source.
Install a C compiler with Apple's Command Line Tools if unavailable, then install
Rust, OpenSSL and pkg-config. With Homebrew:

```bash
brew install rust openssl@3 pkg-config
export OPENSSL_DIR="$(brew --prefix openssl@3)"
export OPENSSL_STATIC=1
```

Keep those environment variables in the terminal used for `uv sync` and setup.
The lock selects ONNX Runtime 1.23.2 on Intel Macs; other supported targets use
1.31.0. These build prerequisites are not needed by users installing the DMG.

```bash
uv sync --frozen --no-dev
```

This creates a `.venv` in the project folder. It does not make AI requests.

### 5. Install OPA (optional)

Setup normally downloads the pinned official release asset for your Mac:

- Apple Silicon: `opa_darwin_arm64`
- Intel: `opa_darwin_amd64`

If automatic download is blocked, install OPA with Homebrew:

```bash
brew install opa
```

The launcher checks `.tools/opa` first, then `opa` on `PATH`.

### 6. Configure and check the installation

```bash
uv run --no-dev python local_app.py setup
```

This command:

- copies `.env.example` to `.env` if needed;
- downloads and verifies OPA when it is missing;
- checks Node.js and OPA;
- optionally prompts for your provider API key with hidden input;
- makes **no AI requests**.

You can press Enter to skip the key and add it later in `.env`.

### 7. Start

```bash
uv run --no-dev python local_app.py start
```

The launcher starts the private policy service and the web app, waits for
readiness, and opens:

```text
http://127.0.0.1:8002
```

If the browser does not open automatically:

```bash
open http://127.0.0.1:8002
```

To start without opening a browser:

```bash
uv run --no-dev python local_app.py start --no-browser
```

### 8. Check status

```bash
uv run --no-dev python local_app.py status
```

A running app exits 0. A stopped app exits 1. Invalid commands or failures exit 2.

### 9. Stop

```bash
uv run --no-dev python local_app.py stop
```

This stops both the web app and its private OPA process. Your documents,
database, settings and backups are kept.

### 10. Run the tests (optional)

```bash
uv sync --frozen --group dev
uv run --frozen pytest -q
```

The release suite is offline and blocks paid model calls.

### macOS notes

- The `.cmd` files are **not** used on macOS.
- Do not run the app with `sudo`.
- The app and OPA bind only to loopback (`127.0.0.1`).
- If macOS blocks the downloaded OPA binary, remove the quarantine attribute:

  ```bash
  xattr -d com.apple.quarantine .tools/opa
  ```

  Only do this for the OPA binary downloaded by setup from the official release.
- Logs are in `data/runtime/`. The web log rotates at 5 MB.
- To change the API key, stop the app and edit `OPENAI_API_KEY` in `.env`.
- The app does not install a macOS LaunchAgent. It runs only while you start it
  and stop it explicitly.

---

## Linux source install (terminal)

These source commands target Linux x86_64. Install `uv`, Node.js 20+ and OPA using
your distribution or the official installers, then:

```bash
git clone https://github.com/LeymansGuz/Study-Desk.git
cd Study-Desk
uv sync --frozen --no-dev
uv run --no-dev python local_app.py setup
uv run --no-dev python local_app.py start
```

OPA setup downloads the static Linux binary for x86_64. If downloads are
blocked, install OPA manually and ensure `opa` is on `PATH`.

To avoid opening a browser:

```bash
uv run --no-dev python local_app.py start --no-browser
```

Stop with:

```bash
uv run --no-dev python local_app.py stop
```

The full Linux lifecycle has not been live-tested in this release.

---

### Repair or upgrade the source edition

Stop the app before changing an existing installation.

```text
git pull
```

Windows:

```text
Setup.cmd
Start.cmd
```

macOS/Linux:

```bash
uv sync --frozen --no-dev
uv run --no-dev python local_app.py setup
uv run --no-dev python local_app.py start
```

Setup installs the versions in `uv.lock`; it does not arbitrarily update
dependencies. To change an existing key, edit `OPENAI_API_KEY` in `.env` while the
app is stopped. `OPENAI_MODEL` and `OPENAI_BASE_URL` select your compatible
provider/model.

The default ports are **8002 for Study Desk** and **8182 for its private OPA**.
If a port is busy, the launcher refuses to stop or reuse the other service.
Change `LOCAL_PORT` / `LOCAL_OPA_PORT` in `.env` to two different free ports, then
start again. The launcher never stops services merely by their port or name.

Startup failures point to `data/runtime/` logs. Python service logs rotate at
5 MB with three archives. OPA logs errors only. A startup failure cleans up its
own services. Graceful stop lets requests finish; if they do not finish within
30 seconds, the launcher terminates only the recorded, still-matching process.
An interrupted generation can be retried; original documents are kept.

## Troubleshooting

### `uv: command not found`

After installing from the official script, open a new terminal or add
`~/.local/bin` to `PATH`. Homebrew installations normally put `uv` in the
Homebrew prefix already on `PATH`.

### `Node.js is missing` or Node is too old

Run:

```bash
node --version
```

Install Node.js 20 or newer and start a new terminal. macOS Homebrew users can use
`brew install node`.

### OPA download fails

Install OPA manually from the
[official documentation](https://www.openpolicyagent.org/docs), then rerun setup.
The launcher checks `.tools/opa` and then `opa` on `PATH`.

### A port is already in use

Stop an existing Study Desk instance first. If another service owns the port,
choose free ports in `.env`:

```dotenv
LOCAL_PORT=8002
LOCAL_OPA_PORT=8182
```

Ports must be between 1024 and 65535 and must differ.

### The app starts but no page opens

Open <http://127.0.0.1:8002> directly. Check `data/runtime/web-runtime.log` and
`data/runtime/opa.log`. Use `status` before starting a second copy.

### Old `.doc` files

Legacy `.doc` is an old binary format. The app tries Extractous/Tika, but this
format has fewer parser guarantees than `.docx`. If an old `.doc` cannot be
read, open it in Word/LibreOffice and save it as `.docx` or PDF, then upload the
converted file. `.docx` uses the dedicated parser and XML fallback.

### API key errors

Desktop application: replace the key in **Settings → DeepSeek connection** and
check that your DeepSeek account has available balance.

Source edition: stop the app, verify `OPENAI_API_KEY`, `OPENAI_BASE_URL` and
`OPENAI_MODEL` in `.env`, then start again. Neither edition returns the saved key
through its settings API.

### macOS says the OPA binary cannot be opened

See the quarantine note in the macOS section. Do not disable Gatekeeper globally.

## Data, diagnostics and backups

The source edition keeps SQLite records, documents, vector indexes and logs
under the project's `data/`. The Windows desktop app keeps them under
`%APPDATA%\link.spookelgoose.studydesk`, outside the program directory. The
default owner is an internal storage identity. No account
setup is required. Your provider receives relevant excerpts for AI generation;
this is a local interface, not an offline language model.

The 10 most recent study sessions are retained. Document lists are paginated;
course/document capacities protect storage. Detailed model traces and
generation events are bounded. **Settings → Local maintenance** shows usage,
estimated costs and recent outcomes. **Create backup** saves an archive in
the study-data folder's `backups` directory; **Verify backup** checks the newest
archive and SQLite integrity.
Wait for document indexing to finish before creating a backup.
Costs are estimates based on configured rates. Back up original material before
changing or deleting it. Backup archives contain private study data.

For the source edition, stop the app before copying the project folder or changing `.env`. The `.env`
file, `data/`, `audit/`, `.venv/` and `.tools/` are ignored by Git because they
contain local configuration, private study material or generated files.

## Removing the app

Desktop application: close Study Desk first. On Windows, use installed-apps
settings; on macOS, remove Study Desk from Applications; on Linux, remove the DEB
through your package manager or delete the standalone AppImage. Study data and the saved system credential are
retained for reinstalling. Create a backup before changing your installation.

Source edition: stop it first:

```bash
uv run --no-dev python local_app.py stop
```

Then delete the project folder. This deletes the local database, documents,
backups and logs inside that folder. Make a backup first if you need the data.

## Security and privacy

- The app and OPA bind to `127.0.0.1` only.
- Do not expose the app through a tunnel or reverse proxy.
- `SECURITY.md` describes the OS-user and file-access boundary.
- `SECURITY-AUDIT.md` records the dependency and local-lifecycle audit.
- Keep `.env`, `data/` and backups private.
- The desktop application stores its API key in the system credential store.
- The source edition uses `.env`, without adding separate file encryption.
- Knowledge of an API key is equivalent to access to the provider account.

## Tests

```text
uv sync --frozen --group dev
uv run --frozen pytest -q
```

Tests use temporary storage and block paid model calls. They cover local access
boundaries, uploads, session resume, arithmetic, formatting, grading and
feedback-derived calibration regressions. Offline tests do not establish live
generation accuracy. CI runs the 114-test suite on Windows, Apple Silicon Mac,
Intel Mac and Linux, then checks each frozen backend. Mac/Linux graphical and full
source-edition lifecycle testing remain separate from those checks.

## Publishing this source

The source includes `.env.example`, dependency locks and self-hosted renderer
assets. Review the files staged for your GitHub commit. Never add API keys,
personal course documents, diagnostic exports or backup archives.
Keep temporary paid-evaluation scripts, browser captures and intermediate reports
under `audit/` (ignored by Git). Additional temporary harness/report locations are
covered by `.gitignore`. Maintained offline regression tests in `tests/` belong
with the source; the runtime math checker in `scripts/` is also required by the app.

## License

MIT. See [LICENSE](LICENSE).

## Security audit

See [SECURITY-AUDIT.md](SECURITY-AUDIT.md) for the audit scope, fixed findings,
verification results and remaining dependency risk. Tests use this project's own
locked environment, not a neighbouring development environment. No live model
calls are needed for the setup, lifecycle or security checks.
