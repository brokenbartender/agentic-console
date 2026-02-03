# Explainable AI Review (2006.00093v4)

## Extracted guidance
- Emphasizes interpretability needs when models are opaque; catalogues explanation techniques and evaluation focus.
- Suggests explanations should be human-centric, scoped to task, and evaluated for usability.

## Applied in this repo
- Added `explain <query>` command to surface routing hints and evidence provenance.
- Added RAG provenance fields to support traceability in explanations.

## Gaps to revisit
- Formal explanation evaluation with user studies or proxy metrics.
- Multiple explanation modes (feature attribution vs. example-based vs. counterfactual).
