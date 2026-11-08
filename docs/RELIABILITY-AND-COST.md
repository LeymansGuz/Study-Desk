# Reliability and estimated AI cost

[Back to README](../README.md) · [AI pipeline](AI-AND-PIPELINE.md)

## 8 November 2026 tutor-panel checks

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

## 7 November 2026 practice matrix

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

