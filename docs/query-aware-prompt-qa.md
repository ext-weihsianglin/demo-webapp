# Query-aware prompt QA — 2026-10-02

Select **gpt-4.1-mini → Experimental f2ef0597** in Content Studio's **Rewrite
prompt** dropdown. The shipped default remains **Baseline v7**. This hand-written
candidate is available for inspection, with no quality recommendation or GEPA
promotion. Other models retain their existing prompt catalogs.

The [registered artifact](../prompt-registry/p2/gpt-4.1-mini/candidates/gpt-4.1-mini--procedure--4dc3c4a39237157a3b1a3b02/prompt.json)
contains the expanded editorial strategy and exact effective prompt. It replaces
only the mutable editorial component, preserving every fixed v7 instruction.
Its SHA-256 is `f2ef0597491c588bd90b30a971498c4d286ec0f7624d5b608e78d3330801554c`.
It considers supported, partially supported and unsupported queries; asks for
targeted edits; and discourages feature gaming. The request payload, feature
feedback, URL, schema, model settings and fidelity policy are unchanged.

## Exploratory comparison

One live GPT-4.1 mini generation per variant/page, identical complete query sets,
P1 feedback and generation settings: 128K context, 16K output reserve, 120-second
timeout. This earlier comparison used an isolated copy of the QA worktree's
unmerged `body-content-v5` source-role fixes and advisory fidelity assessment.
Those changes are **not included here**. Current `main` uses `body-content-v4`
and rejects the request when fidelity fails, so these numbers are not an
end-to-end success claim for this branch.

| Page | Queries | Baseline P1 change | Candidate P1 change | Baseline unsupported / edits | Candidate unsupported / edits |
| --- | ---: | ---: | ---: | ---: | ---: |
| aging.ca.gov | 8 | +0.195 | +7.240 | 3 / 7 | 14 / 17 |
| blog.blazingcdn.com | 9 | +0.963 | +0.935 | 17 / 22 | 8 / 8 |
| bettsrecruiting.com | 10 | +0.205 | +0.108 | 4 / 5 | 7 / 8 |

P1 changes are equal-weight mean differences on a 0–100 scale, not citation
uplift. Unsupported counts are the fallible GPT-5 fidelity judge's findings;
the CDN baseline also had one uncertain edit. All six generations passed
mechanical validation and all six received rejected fidelity assessments.
Cats.com was originally selected but exceeded context limits for both prompts
before provider calls; Betts was the declared replacement, without prompt
changes or retries. All eight outcomes remain in the
[compact evidence record](../verification/query-aware-prompt-qa.json), together
with snapshot identities, code hashes and manual-review findings.

Manual review found unsupported 24-hour staffing claims on Aging, a removed
pricing qualification and unsupported provider comparisons on CDN, and label/
byline expansion on Betts. The candidate is not established as an improvement.
Three previously inspected P1 test pages and one stochastic attempt per variant
do not constitute an untouched P2 final evaluation or a repeatability result.
No explanation matrices or missingness weights were added to either prompt.

## Manual inspection

Load a saved example and retain all distinct queries. Draft once with Baseline
v7 and once with Experimental f2ef0597, retaining each response before switching.
Check source support, qualifiers, language and block purpose, then compare every
query's P1 change. Check response telemetry for the selected prompt hash.
Fidelity rejection remains possible under the current application policy.

The existing dropdown discovers this committed candidate without UI changes.
An alternate `PROMPT_REGISTRY_ROOT` needs the same relative candidate directory
copied into it. No `selected.json` pointer is shipped or modified. URL path
proposals are tracked separately in [issue #14](https://github.com/ext-weihsianglin/demo-webapp/issues/14).
