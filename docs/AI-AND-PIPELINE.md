# AI connections and the checking pipeline

[README](../README.md) · [User guide](USER-GUIDE.md) · [Measured reliability and cost](RELIABILITY-AND-COST.md)

## Connect a provider

1. Open **Settings → AI connection** and choose a provider.
2. Enter its API key and choose **Save and use** to save it and load the model catalog.
3. Choose a text model and, for OpenRouter, a hosting endpoint. Save the connection.
4. When returning to a provider, leave the key blank to reuse its saved key.

Each provider keeps its own key and last saved selection. Custom keys are scoped
to their saved endpoint. Saving is disabled while models/endpoints are loading
or no eligible endpoint is selected. Catalog requests do not send course content.
An explicitly approved connection test sends a small synthetic JSON request.

| Connection | Notes |
|---|---|
| DeepSeek | Flash is the tested paid baseline; Pro can also be selected. |
| OpenRouter | Select the model and host. Free endpoints are restricted below. |
| OpenAI API | Uses the Responses API; a ChatGPT website subscription is not an API key. |
| Claude API | Uses the Messages API; a Claude website subscription is not an API key. |
| Custom compatible endpoint | Uses OpenAI-compatible Chat Completions. Remote URLs require HTTPS; HTTP is allowed only on loopback. |

Catalog availability does not certify answer quality or account/regional eligibility.
Check your selected model and hosting provider's access and data-processing terms.
A running workflow retains its original connection when you change Settings.

## Free and paid capabilities

| Capability | Eligible free connection | Suitable paid connection |
|---|---|---|
| Brief concept explanation | Experimental, with checks | Supported |
| Deep explanation | Not enabled | Supported |
| New practice / mastery path | Not enabled | Supported |
| Tutoring, marking, recall and hints | Not enabled | Supported |
| Read saved work, search, planning, exports | Local; no inference needed | Local; no inference needed |

Free candidates tested worse than the paid baseline for question generation.
The backend enforces restrictions even if **Free only** is unchecked for a known
free model. Free explanations retain solving, grounding, arithmetic and review
checks; unsupported outputs are withheld.

Free requests pin the chosen host, disable fallback and require zero advertised
prompt/completion/request/image prices. Unknown or incomplete pricing is not
free. The provider's daily allowance applies to every internal request, including
validation and repair. The app paces requests, checks known allowance before
starting and stops retries on quota errors. There is no automatic paid fallback.

Settings shows provider/model usage, returned input/output tokens, cached input
and estimated USD costs. Catalog/configured rates are estimates; invoices control.
Advanced manual model IDs and reasoning/JSON options do not certify quality.
Mandatory-reasoning models may be slow or exhaust the output budget.

## Where data goes

Extraction, OCR, embeddings and indexing run locally. Requested AI work sends
relevant evidence, the problem and necessary attempts/history to your selected
provider and OpenRouter host, when applicable. Verification may resend them.
See the [data-use notice](../PRIVACY.md).

Desktop keys use the OS credential store, never frontend assets, study backups
or the repository. Source users may use Settings or private `.env` configuration.
A locked/unavailable credential store causes saving to fail visibly; there is
no plaintext desktop fallback.

## Practice pipeline

1. **Plan and retrieve:** respect course scope, source roles, exclusions and retained exposure history.
2. **Abstract evidence:** give the Writer reusable covered principles and prohibited source-task patterns, not tempting exercise stems.
3. **Write:** design a new public problem with a compact private feasibility witness.
4. **Preflight:** check topic, public premises, supported methods, source cloning and nearby previous inferences.
5. **Blind solve:** the Solver sees the public question/options, not the Writer's answer.
6. **Local checks:** evaluate arithmetic and supported symbolic checks; check formatting, option uniqueness, key agreement and requested parts.
7. **Review:** check correctness, grounding, originality, difficulty, workload and assumptions. Higher-complexity work receives additional review.
8. **Policy and publication:** enforce applicable app/OPA rules and publish atomically. Do not hold write locks across model calls.
9. **Tutor:** grade each part, tailor hints to the actual attempt and apply answer-disclosure policy.

OPA is a policy engine, not a mathematical proof checker. Agreement between
same-provider reviewers is not independent ground truth.

### Explain and Ask use the relevant stages

- **Explain:** draft from covered principles; independently solve the original
  application; check formulas, example calculations, assumptions, citations and
  source originality. Reuse the checked solution only when the example is unchanged.
- **Ask:** preserve the supplied question and option order. Repair faulty private
  calculation plans, not public givens. Missing essential diagram facts stay missing;
  OCR cannot infer them.
- **Recall:** grade against a current checked explanation and its course evidence,
  never personal revision-sheet edits; independently review the feedback.

## Source roles and difficulty

Notes, exercises and past papers are primary topic evidence. Syllabuses constrain
scope; marking schemes and exam reports support assessment. Administrative
instructions/performance statistics are not subject objectives unless that is
what the course genuinely teaches. Institution/course names supply no missing methods.

Easy is direct application; Medium adds a small interpretation or choice. Hard
requires a meaningful application/justification. Insane adds one bounded insight,
without piling on workload. Long answer is structured; essay is paragraph-based.
A metadata row count or word count does not establish reasoning depth.

## Repairs, deadlines and failure messages

- Give retries concrete failure feedback; keep attempts bounded.
- Syntax repair changes only the broken calculator string. Re-run its evaluator
  and independent syntax Solver before accepting it.
- Parameter formulas are symbolic; do not invent scalar values for them.
- Public-question changes require a fresh independent solution and full checks.
- Ordinary processing uses 60 seconds; complex proof/extended/deep work uses
  90 seconds. One feedback-guided practice repair may have 15 seconds of grace.
- Processing deadlines start after acquiring a slot; queue waiting is separate.
- Safe errors identify the stage. Technical diagnostics stay local. Failed work
  does not publish half-written questions, sessions or exposure reservations.

Source configuration uses `GENERATION_TIMEOUT_SECONDS`,
`GENERATION_COMPLEX_TIMEOUT_SECONDS` and `GENERATION_REPAIR_GRACE_SECONDS`.
Desktop installers do not read the source checkout's `.env`.

## Repeated study requests

| Process | Standard |
|---|---|
| Any syllabus topic | Prefer less-used eligible sections and primary chunks while preserving source quality. |
| Specific-topic practice, paths and follow-ups | Change the defining inference, not only numbers/names. Reindexing does not reset retained avoidance. |
| Explain / checked guides | Stable representative evidence and checked reuse for the same topic, depth and current course/check version. |
| Ask | Preserve the task; return a consistent checked answer rather than inventing a variant. |
| Bank exams / FSRS | Deliberate review can repeat; bank exams prefer less-practised items and offer an unseen-only filter. |
| Marking / hints | Judge the actual answer consistently, preserve correct parts and adapt hints to the current error/attempt. |
| Plans / search / source reading | Stable results are useful while the underlying evidence and progress are unchanged. |

Avoidance uses 2,000 retained exposures across index revisions and source filters.
Number-only identity is checked throughout; local semantic work uses a bounded
shortlist. The existing preflight compares nearby prior inferences without an
extra model request. MCQ identity includes choice bodies, independent of order.
Explained examples are avoided by the practice bridge. A finite topic can run out
of useful new tasks; known repeats are withheld rather than served silently.

Checked explanation caches and bank items require current validation/evidence
versions before reuse as trusted study/marking references. Historical saved text
remains readable. Personal imports do not inherit external verification claims.
