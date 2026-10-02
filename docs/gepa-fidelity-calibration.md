# Procedure validation and fidelity calibration — 2026-10-02

The procedure registration defect is addressed: generated procedures now receive deterministic completeness and known-contract checks before registration, with at most one explicitly logged repair. A 12-edit source audit does **not** establish a reason to weaken the fidelity judge. Three new faithful controls pass after restoring details omitted by their corresponding generated rewrites. The main remaining obstacle is producing useful rewrites while preserving all material source facts.

## Procedure registration

New reflection instructions target roughly 3,900 characters under the default 6,000-character maximum. The validator checks length/envelope, unfinished endings, an empty final step, and known conflicts such as new page blocks, numbered-list output, or invented nested `review_flags` fields. These are conservative syntax and contract checks, not proof that arbitrary natural-language instructions are semantically consistent. Fixed P2 schema, preservation and fidelity validation remain authoritative.

Invalid output receives one repair request containing the entire original feedback, exact invalid response and validation errors. Both requests pass the complete context/input/schema/output-reserve preflight. No text is truncated. An invalid repair retains the parent candidate and logs rejection. Refusals do not trigger repair. Repair consumes a reflection call, not a page-rewrite attempt; usage totals include both calls. The component manifest freezes the new validation profile, so older incompatible runs cannot promote without reevaluation.

Every new request now saves `reflection-output-N` (and optional `-repair-1`) with the provider's verbatim returned JSON text, response status/model, usage and validation errors. No hidden reasoning is captured. The reflection-trace endpoint exposes responses beside their corresponding inputs; full exports preserve both. This closes the previous observability gap: historical candidate files alone cannot establish why the old responses ended at exactly 6,000 characters.

A [live diagnostic](../verification/gepa-procedure-validation-live-v1.json) using two saved reflection pages returned a complete **5,226-character** procedure on its first call. The raw provider string exactly matches the registered strategy, so this check shows no application truncation. Repair, double failure, known contract conflicts and repair context overflow are exercised with stubbed responses. This is not proof that every future generated procedure will be complete.

## Frozen fidelity audit

[The fixture](../verification/gepa-fidelity-calibration-cases-v1.json) contains 12 actual saved reflection-page edits, their complete original chunks, exact changes, prior judge findings, artifact hashes and source-only assessments frozen before replay. Four cases were initially assessed faithful, four unsupported and four borderline. The assessments are by the coding assistant, **not independent human gold labels**. No selection/test pages were used.

[The initial replay](../verification/gepa-fidelity-calibration-replay-v1.json) made 12 GPT-5 fidelity calls: 11 returned verdicts and one timed out. Eight matched the initial assessment. Three disagreed; the unavailable result remains visible and is not counted as a substantive rejection. All six cases assessed unsupported were rejected, including the two borderline cases with added intensity or an unsupported chronological comparison.

| Case | Initial assessment | Replay | Source audit |
|---|---|---|---|
| Fuel interval | Supported | Supported | Preserves interval, professional attribution, conditions and possible benefits. |
| Fuel user reports | Supported | Unsupported | Omits the original direct-injection-specific scope. The initial assessment was too permissive. |
| Fuel introduction | Supported | Supported | Retains the main mechanism, risks and qualified claims. |
| NEC description | Supported | Unsupported | Drops the explicit integration/optimisation capability attributed to the alliances. Materiality is debatable, but this is not a demonstrated false positive under strict fact preservation. |
| Turbo inference | Unsupported | Unsupported | Turbocharging is not stated in this source chunk. |
| API attribution | Unsupported | Unsupported | Replaces named API attribution with vague industry reporting. |
| SAE attribution | Unsupported | Unsupported | Removes named SAE attribution and direct-injection context. |
| Pricing average | Unsupported | Unsupported | Turns a flat-rate price into an average. |
| 5G intensity | Unsupported, borderline | Unsupported | Adds “significant” growth; a synonym alone should not justify rejection. |
| Older systems | Unsupported, borderline | Unsupported | Replaces precise port-injection comparison with an unstated age generalization. |
| Professional interval | Supported, borderline | Unsupported | Short-trip evidence does exist in the same chunk, so part of the reason is wrong; however, the edit also drops maintaining engine performance. The overall rejection is defensible. |
| Cisco paraphrase | Supported, borderline | Unavailable; explicit follow-up rejected | Follow-up cites removal of “all 5G Cores” and other source claims. “Unique value” materiality is debatable; the universal scope omission gives a substantive reason. |

The judge is fallible: prior saved batch verdicts accepted several edits that these individual replays rejected, and one explanation overlooked allowed same-chunk evidence. This small, selected audit cannot estimate a general false-positive rate. It also cannot cleanly separate batch-context effects from model variability. Do not report 8/12 agreement as model accuracy.

## Faithful controls and decision

[Four follow-up calls](../verification/gepa-fidelity-calibration-controls-replay-v1.json) used [a separately frozen control set](../verification/gepa-fidelity-calibration-controls-v1.json): three authored paraphrases restoring omitted scope/capabilities/benefits, and one explicit retry of the unavailable Cisco case. These controls use the same original chunks; they are diagnostic edits, not GEPA candidates. All **three faithful controls passed**. The unchanged Cisco edit was rejected. The follow-up used a 120-second diagnostic timeout, with SDK retries disabled; the served judge configuration was not changed.

**Decision:** retain the existing judge prompt/policy. The evidence supports improving P2 preservation and monitoring judge disagreement, not globally weakening the gate. The three accepted controls demonstrate that faithful rewriting is possible, but have not been scored by P1 and do not establish score uplift. No P2 calls, embeddings, held-out evaluation, prompt promotion or new full GEPA run occurred during this calibration.

## Reproduction and verification

Use a fresh report path for each opt-in replay:

```sh
backend/.venv/bin/python backend/scripts/calibrate_gepa_fidelity.py --live \
  --fixture verification/gepa-fidelity-calibration-cases-v1.json \
  --output verification/new-calibration-replay.json
```

The same command accepts the four-case control fixture with `--timeout-seconds 120`. It caps fixtures at 12 cases, checks original before text and reflection provenance, and saves each result incrementally. Calls are explicitly enabled; ordinary tests use stubs.

Validation: **175 backend tests passed, two opt-in checks skipped**; diff checks passed. No frontend code changed in this update. The diagnostic provider use comprised one reflection call, 12 initial fidelity calls and four follow-up fidelity calls. One initial fidelity call timed out and remains recorded.
