# Study Desk

A private, document-grounded study workspace for your computer. The desktop
application opens in its own window, stores study data locally and uses your own
AI provider API key. The source edition can also run at **http://127.0.0.1:8002**.
Both editions open directly as the local owner.

## Install the desktop application

The current published beta is [v0.2.8-beta.1](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.8-beta.1).
Choose an installer for your computer; the source-code ZIP is for source setup.
Desktop users do not need Python, Node.js or a `.env` file.

| Computer | Download |
|---|---|
| Windows x64 | [Setup executable](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/Study-Desk_0.2.8_x64-setup.exe) |
| Apple Silicon Mac, macOS 14+ | [aarch64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/Study-Desk_0.2.8_aarch64.dmg) |
| Intel Mac, macOS 14+ | [x64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/Study-Desk_0.2.8_x64.dmg) |
| Linux x64 | [DEB](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/Study-Desk_0.2.8_amd64.deb) or [AppImage](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/Study-Desk_0.2.8_amd64.AppImage) |

The release also provides [SHA256SUMS.txt](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.8-beta.1/SHA256SUMS.txt)
and build manifests. For your own local build, installer files are in `dist/installers/`.

**Windows:** run the setup executable, install it for your Windows user, and open
**Study Desk** from its shortcut or the Start menu.

**macOS:** open the DMG, drag **Study Desk** into **Applications**, eject the DMG,
then open Study Desk from Applications. These beta builds are unsigned and not
notarized. If macOS blocks opening, review [Apple's app-opening guidance](https://support.apple.com/en-hk/102445)
before deciding whether to approve this app. Do not disable system-wide protection.

**Linux DEB:** on Ubuntu/Debian, install the downloaded file with your package
manager, or run this from the download folder:

```bash
sudo apt install ./Study-Desk_0.2.8_amd64.deb
```

**Linux AppImage:** make the downloaded file executable in its file properties,
then open it. The equivalent terminal commands are:

```bash
chmod +x ./Study-Desk_0.2.8_amd64.AppImage
./Study-Desk_0.2.8_amd64.AppImage
```

Linux builds target Ubuntu 22.04. Other distributions may need additional system
libraries. If the AppImage reports missing FUSE support, use the DEB on a compatible
distribution or install your distribution's FUSE compatibility package. Saving
an API key needs an available system credential store, such as Secret Service.

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
The app downloads a full package from the official GitHub release and verifies
its signature and signed version. Choose **Install and restart** when requests,
uploads and indexing are finished. Study Desk creates and verifies a local backup
before replacing the program. Documents, progress and your system credential stay
separate from installation files. A failed check/download installs nothing.
If installation cannot finish, reopen the app and check its installed version
before retrying. Backups support recovery; they do not guarantee automatic
database downgrades.

Updates are manual, with full downloads rather than changed-file downloads.
If your installed version has no **App updates** section, install the current
release manually from the links above.
On Linux, the AppImage must be writable by your user; DEB updates may request
administrator permission. On macOS, run from Applications rather than the DMG.
Update signatures do not remove OS warnings about unsigned/not-notarized apps.

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

The model catalog loads automatically when a key is saved. Text-generating models
are shown; known non-text services are excluded. Price labels are Free, Paid or
Pricing unknown; incomplete metadata is never treated as free. Advanced controls
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
Local study data and backups are not encrypted by the app.
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

Documents define the permitted methods. Insane adds one meaningful reasoning
extension without unlimited subparts or arithmetic. The independent checks
increase confidence; they cannot guarantee every generated answer is correct.

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

## Concept mastery and bank exams

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
is 60 seconds; Insane proof and long-answer requests have a 90-second ceiling,
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

Latest measured DeepSeek live check: **3 November 2026**, version **0.2.3-beta.2**, runtime revision
[`dacce90`](https://github.com/LeymansGuz/Study-Desk/commit/dacce908734f9b057295dfd70a411ce374c760c4),
assessment policy 19, DeepSeek Flash with explicit non-thinking JSON stages.
These results replace older runs as the basis of the estimates below.

| Dated DeepSeek check | Result |
|---|---:|
| Complete generation attempts | 9 |
| Accepted by the production pipeline | 8 / 9 (88.9%) |
| Timeouts | 1 (Medium essay, Solver stage) |
| Mean time for accepted questions | 33.5 seconds |
| Accepted questions with no additional model-review flags | 7 / 8 |

The sample covered five courses and all seven question types, spanning Easy,
Medium, Hard and Insane. One course used a copy of the real local vector index;
the other four used frozen excerpts from real course files with simplified
retrieval. Bank reuse was disabled. This is a small, selected generation and
validation check, not a representative end-to-end benchmark of normal traffic.
**88.9% is this sample's acceptance rate, not a guaranteed production rate.**

Acceptance is not correctness. Further model review flagged one accepted biology
item whose microscopy explanation used resolving-power material unsupported by
the supplied passages; inspection of the retained passages confirmed the evidence
gap. The answer itself was not flagged as false. All eight reviews considered
their answers and working correct, but these are same-provider model judgements,
not expert certification. There is no defensible universal correctness percentage.
Originality screening also cannot guarantee the absence of every source clone.
Check important answers independently, especially proofs.

Requests may still reach the 60/90-second deadline; queue waiting is separate.
Bank reuse avoids fresh generation. Offline regression tests establish software
behaviour rather than live question quality.

## Estimated AI cost

Study Desk charges no application subscription. AI requests consume your own
provider allowance or balance. Free OpenRouter usage is limited; unknown model
pricing is not estimated as zero. The **same dated DeepSeek live check** recorded:

| Cost measure | Recorded USD |
|---|---:|
| Medium MCQ generation example | $0.00250 |
| Mean successful generation operation | $0.00504 |
| Successful generation operation range | $0.00250–$0.00637 |
| All nine generation attempts combined | $0.04795 |
| Generation spending divided by eight accepted questions, including the failed attempt | $0.00599 |
| Extra evaluation-only reviews, excluded from generation figures | $0.00396 |

One timed-out provider call has missing token usage, so these totals are
**incomplete recorded estimates**, not provider invoices or spending caps.
At this sample's off-peak rates and workload, 100 accepted questions would record
roughly **$0.60**, or roughly **$1.20 at peak rates**, plus any unreported usage
and follow-up costs. Different course context, retries and response lengths can
change the result substantially. Nine attempts do not establish a stable average.

The check made 82 provider requests: 74 production generation/validation calls
and eight extra evaluation reviews. Including ten diagnostic requests before the
model-mode correction, **92 of the authorized 100 requests** were used. All
internal retries and validation calls counted toward that ceiling.

Rates verified on 3 November 2026: off-peak Flash input costs $0.15 per million
uncached tokens or $0.003 per million cached tokens; output costs $0.60 per
million tokens. Peak rates are twice these figures. Cached input is already part
of total input, not an extra category to add twice. Confirm
[DeepSeek's current pricing](https://api-docs.deepseek.com/quick_start/pricing/)
before topping up. These figures apply to `deepseek-flash`, not other providers
or models, and are not a new evaluation of the provider integrations.

Answer feedback, hints and concept explanations can incur additional AI charges.
Opening bank questions or starting a bank exam makes no generation call, but
grading can use AI. Local OCR, embedding/indexing and index rebuilding make no
DeepSeek calls. **Settings → Local maintenance** shows recorded tokens, cached
input and estimated costs; the provider dashboard is authoritative for billing.

**Settings → Local maintenance** shows recorded tokens, cached
input and estimated USD costs; the provider dashboard is authoritative for billing.

**Settings → Local maintenance** shows the last 30 days of tokens and estimated
USD cost, with five decimal places. Cached input is part of total input, not an
additional charge. Cached counts and question details cover retained provider
traces; daily cost totals may cover a longer window when detailed traces expire.

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
own provider API key. The desktop application uses DeepSeek; the source edition
defaults to DeepSeek and can configure a compatible provider.

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
