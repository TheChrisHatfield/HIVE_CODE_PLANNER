# Impact packet — bug-likelihood blend

Date: 2026-11-05

## Change

`rank_queue_score` keeps the six-signal mix, trust, and place. When the queue passes bug likelihood, that mix is squashed with tanh into (−4, 4) and the likelihood term is added. Likelihood is not a learned slope.

## Primary

`src/hive_planner/bug_hunt.py` (`bug_likelihood`, `_count_surface`, `score_unopened`, the hunt prompt sentence).

## Secondary

`docs/specs/bug-hunt/spec.md` ranking paragraph. `tests/test_bug_hunt.py` two new tests. The extreme-slope test still expects the two-line high-churn file to lead, because both files are tiny and the cap still leaves room for activity.

## Not touched

H-drive repos. Installed copies of `scripts/bug-hunt.md` there stay as they were until a later install.

## Validation

`py -3.11 -m pytest tests/test_bug_hunt.py` — 211 passed.
