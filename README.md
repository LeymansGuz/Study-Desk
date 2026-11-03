# Study Desk

A private, document-grounded study workspace for your computer. The desktop
application opens in its own window, stores study data locally and uses your own
DeepSeek API key. The source edition can also run at **http://127.0.0.1:8002**.
Both editions open directly as the local owner.

## Install the desktop application

The current published beta is [v0.2.2-beta.2](https://github.com/LeymansGuz/Study-Desk/releases/tag/v0.2.2-beta.2).
Choose an installer for your computer; the source-code ZIP is for source setup.
Desktop users do not need Python, Node.js or a `.env` file.

| Computer | Download |
|---|---|
| Windows x64 | [Setup executable](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/Study-Desk_0.2.2_x64-setup.exe) |
| Apple Silicon Mac, macOS 14+ | [aarch64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/Study-Desk_0.2.2_aarch64.dmg) |
| Intel Mac, macOS 14+ | [x64 DMG](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/Study-Desk_0.2.2_x64.dmg) |
| Linux x64 | [DEB](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/Study-Desk_0.2.2_amd64.deb) or [AppImage](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/Study-Desk_0.2.2_amd64.AppImage) |

The release also provides [SHA256SUMS.txt](https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.2-beta.2/SHA256SUMS.txt)
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
sudo apt install ./Study-Desk_0.2.2_amd64.deb
```

**Linux AppImage:** make the downloaded file executable in its file properties,
then open it. The equivalent terminal commands are:

```bash
chmod +x ./Study-Desk_0.2.2_amd64.AppImage
./Study-Desk_0.2.2_amd64.AppImage
```

Linux builds target Ubuntu 22.04. Other distributions may need additional system
libraries. If the AppImage reports missing FUSE support, use the DEB on a compatible
distribution or install your distribution's FUSE compatibility package. Saving
an API key needs an available system credential store, such as Secret Service.

### First launch

1. Open **Study Desk**.
2. In **Settings → DeepSeek connection**, enter your API key and choose **Save API
   key**. The app stores it in the system credential store. No `.env` editing is
   needed, and saving a key makes no paid request.
3. Upload your course documents in **Workspace**, wait for indexing, and start
   studying. Close the app to stop its private services; reopen it to resume.

The installer bundles Python, Node.js, OPA and native processing dependencies.
Users need internet access for DeepSeek and may need an initial embedding-model
download. Study data is kept outside the installation directory, so program
updates preserve it. The initial installer is unsigned.

The four platform builds passed native CI builds, offline regression tests and
packaged-backend checks. Windows has also received graphical checks. macOS and
Linux graphical behaviour remains experimental and needs testing on your device.

Your documents and progress are kept in your operating system's application-data
folder. Close Study Desk before installing an update, and create a backup in
Settings first. Updating the program preserves the separate study-data folder.

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

Evidence reviewed **3 November 2026**. Reliability here means a generation
request returns a question accepted by the pipeline. It does **not** mean the
question, answer or difficulty has been proven correct.

For mostly routine questions from well-indexed, readable course notes, a
tentative planning estimate is **80–90% first-attempt acceptance**. Confidence
in that estimate is limited: it is informed by earlier mixed testing, not a
representative benchmark of the current release. Advanced proofs are a weaker
area, and newer checks can reject candidates that earlier versions accepted.

| Previous evaluation | Accepted / attempted | Acceptance |
|---|---:|---:|
| Earlier mixed-course/type run | 30 / 33 | 90.9% |
| Later proof-heavy stress baseline | 9 / 14 | 64.3% |
| Same stress cases after revisions | 8 / 14 | 57.1% |
| Selected stress-case confirmation | 5 / 7 | 71.4% |

These small runs used different revisions and deliberately difficult cases;
they must not be pooled into a production success rate. The favourable mixed
run does not establish a 90% current-release rate. Subsequent checks found that
model-based reviewers could miss mathematical errors and source-like questions.
There is no defensible universal answer-correctness percentage. Check important
answers independently, especially proofs. Source-clone screening reduces risk
but cannot guarantee that every generated question is original.

Accepted questions averaged approximately **30–40 seconds** in several retained
runs. Failed attempts may reach the 60/90-second deadline; queue wait is separate.
Bank reuse avoids fresh question generation. Offline regression tests establish
software behaviour, not these live model-quality estimates.

## Estimated AI cost

Study Desk charges no application subscription. AI requests use your own funded
DeepSeek account. Recent normal-use MCQ examples from the hosted deployment
recorded approximately **US$0.0025–$0.005 per operation**. Local evaluation logs
also recorded successful MCQs at roughly **US$0.004–$0.01 at peak rates**, before
adding failed attempts; equivalent off-peak token usage costs half as much.
Neither sample is a representative benchmark of this desktop release.
Older evaluations deliberately stressed harder
questions and retries; their generation logs suggest **US$0.01–$0.03 per accepted
question**, including failed attempts. These describe different workloads:

| Workload | Approximate unit cost (USD) | 100 questions/operations | 1,000 |
|---|---:|---:|---:|
| Recent MCQ operations, without additional failed attempts or follow-ups | $0.0025–$0.005 | $0.25–$0.50 | $2.50–$5 |
| Heavier evaluation workload, allowing for failed generation attempts | $0.01–$0.03 per accepted question | $1–$3 | $10–$30 |

For example, one mixed run recorded about $0.41536 for 33 generation attempts
yielding 30 accepted questions; a later stress run recorded about $0.21849 for
14 attempts yielding eight. These figures exclude extra evaluation-only audits.
Some cancelled requests have missing usage, so recorded costs are incomplete.
The normal-use examples are a small sample, not a measured average for every
course or type. These ranges are estimates, not spending caps or provider invoices.

Historical estimates used Flash rates of $0.30 per million uncached input tokens,
$0.006 per million cached input tokens and $1.20 per million output tokens.
Those match the published peak rates checked on 3 November 2026. The recent
MCQ examples used off-peak rates, which are half, and benefited from cached input.
For example, 16,196 input tokens (7,168 cached) plus 2,198 output tokens cost
approximately $0.002695 at those off-peak rates. This is not evidence of a
version-related price increase. Confirm [DeepSeek's current pricing](https://api-docs.deepseek.com/quick_start/pricing/)
before topping up. Model, cache hits, retries and output length affect spending.
The default model is `deepseek-flash`.

Answer feedback, hints and concept explanations can incur additional AI charges.
Opening bank questions or starting a bank exam makes no generation call, but
grading can use AI. Local OCR, embedding/indexing and index rebuilding make no
DeepSeek calls. **Settings → Local maintenance** shows recorded tokens, cached
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
