# Claim Evaluation

`experiments/claim_evaluation/` is a derived, local-only, read-only evaluator
over `ClaimCandidate` values from `experiments/claim_extraction/`.

It produces advisory findings for:

- authority
- confidence
- sufficiency
- conflict
- supersession
- staleness-by-conflict
- operational readiness

It does not create a claim graph, decide canonical truth, write `.cerebro/`,
gate runtime actions, call network services, or mutate target projects.

The core epistemic rules are explicit:

- registered is not true
- retrieved is not relevant
- remembered is not trusted
- silence is not negative evidence
