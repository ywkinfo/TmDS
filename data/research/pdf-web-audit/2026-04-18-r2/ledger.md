# PDF ↔ Web Audit R2 Bundle (2026-04-18-r2)

## 1. Bundle mode

- mode: offline derived bundle
- source of truth: `data/generated/`
- manual/browser evidence: not regenerated here; any manual verification remains manual-only
- baseline reference: `data/research/pdf-web-audit/2026-04-18/`

## 2. Coverage summary

- page count: `1381`
- delivery modes: `reader-body 1298`, `toc-transform 18`, `search-only 65`
- text pages not exposed: `[]`
- uncovered body pages: `[]`
- toc span: `[11, 28]`

## 3. Special sections

- `front_preface`: `2` record(s)
- `front_notes`: `2` record(s)
- `toc`: `0` record(s)
- `part_intro`: `64` record(s)
- `revision_history`: `10` record(s)
- `legend`: `0` record(s)
- `appendix`: `46` record(s)
- `reconsideration_deadline`: `0` record(s)
- `fta_gi`: `16` record(s)

## 4. Offline search artifacts

- search corpus entries: `492`
- query count: `50`
- matched queries: `47`
- empty queries: `3`
- `search-checks.json` contains the offline expected runtime route summary for the fixed query set.

## 5. First-pass content fidelity diff

- compared pages: `752`
- residue pages included: `750`
- sampled high-risk prose pages: `30`
- statuses: `candidate-backed 687`, `ambiguous 65`, `unsupported 0`
- sampled high-risk token loss rate: `0.09197431781701444`
- `content-fidelity-diff.json` compares repaired page-review paragraph text to overlapping non-alias search-entry text, with only coarse chapter/section HTML evidence.

## 6. Regression diff

- changed artifacts vs baseline: `['special-sections.json']`
- unchanged artifacts vs baseline: `['page-coverage-ledger.json']`
- baseline-missing artifacts: `[]`

## 7. Generated files

- `page-coverage-ledger.json`
- `special-sections.json`
- `content-fidelity-diff.json`
- `regression-diff.json`
- `search-corpus.json`
- `search-results.json`
- `search-checks.json`
- `browser-verification.json`
- `ledger.md`

## 8. Limited browser verification status

- existing browser evidence is recorded in `browser-verification.json` and `screenshots/`
- verified search queries: `머리말`, `일러두기`, `개정 연혁`, `지리적 표시`, `FTA`
- verified representative pages: `35`, `45`, `46` in both reader and `/qa/page/:pageNumber`
- `머리말` now matches the canonical runtime expectation `#/chapter/front-preface`
- `일러두기` also matched its canonical runtime expectation `#/chapter/front-notes`
- `지리적 표시` matched the canonical runtime chapter route for the active top search result
- treat browser evidence as a limited manual layer on top of the offline bundle, not as exhaustive browser coverage for the full corpus.
