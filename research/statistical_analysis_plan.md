# Statistical analysis plan

**Draft pending independent review.** The previous matched-budget and horizon estimates remain exploratory. This plan is prospective for a separate, ungenerated synthetic cohort.

## Co-primary target and denominator

Compare T2 minus B3 and T2 minus H-paced in chronological replay with a fixed two-call ceiling per planned history. For each policy, an end-of-day state check passes only if the set of visible authorized values for the gold predicate and date matches exactly. Score six predeclared current checks per history, including one final-state check. Average those six scores for each history, difference policies within history, average the four differences within family, then average families equally. The target design has 360 histories and 2,160 current checks per policy, using 90 inferential units. Five historical checks per history and one reader question are secondary, with 1,800 and 360 planned outcomes per policy. Same-day events use source sequence for replay and the completed day for checkpoints.

Equal ceiling is the primary policy estimand. Equal realized calls asks a different question because eligibility and underspend vary with earlier choices. Report an exact frozen quota on the fixed stream and an explicitly descriptive realized-call subset in chronological replay without using either to replace the primary. Equal token expenditure is a separate resource estimand. Report both token directions and physical versus logical load with cold-cache and warm-cache accounting. No equal-token causal effect is claimed.

## Missing data and unfavorable outcomes

Freeze any pre-score fixture exclusions and reasons. Retain every approved history and all planned checks in the denominator regardless of output. Terminal verifier errors and timeouts consume a logical attempt and take the existing conservative disposition while the replay continues. For a missing or incomplete whole replay with no trustworthy state, assign all planned checks zero, report its reason, and do not use complete-case filtering as the primary. Unresolved authorization gives zero and does not call the reader on unsafe material. A reader timeout, malformed response, unsupported citation, missing output or incorrect answer scores zero. Explicit, well-formed abstention scores one only for a prereviewed unanswerable question. An empty provider return is missing. Report complete-only metrics separately. An unlogged crash or coding error invalidates that execution and requires investigation before unblinding, with affected records preserved.

## Bootstrap and interpretation

Sort families and histories by their frozen IDs. Resample 90 family IDs with replacement in each of 10,000 draws, seed **360091**, using the same draw for both contrasts. Compute the means of paired family differences. For each contrast take the linearly interpolated 1.25th and 98.75th percentiles. The two 97.5% marginal intervals implement a 5% Bonferroni family-wise error target, subject to the usual bootstrap approximation and family assumptions. Secondary intervals are descriptive. A lower bound above zero for both contrasts supports a positive result in this cohort. Upper bounds below zero for both support a negative result. A definite result in only one contrast or opposite signs is mixed. Both intervals including zero is inconclusive, not evidence of equivalence. Report interval widths even when they miss the target. Safety failures limit applicability independently of statistical direction.

## Precision sensitivity

The planning calculation is the smallest n satisfying `t(0.9875, n-1) × family_SD / sqrt(n) <= 0.05`. This is an approximate planning formula for the adjusted bootstrap, not a power guarantee. The examined ten-family SDs were 0.091 and 0.101 for T2 versus B3 and H-paced. Their small, patterned cohort motivates a larger planning SD. With 0.20, the normal approximation gives 81 and the finite-sample calculation gives 84.

| Paired family SD | Minimum families | Half-width at 90 (percentage points) |
| ---: | ---: | ---: |
| 0.08 | 16 | 1.92 |
| 0.10 | 24 | 2.40 |
| 0.12 | 32 | 2.88 |
| 0.15 | 49 | 3.60 |
| 0.18 | 69 | 4.33 |
| 0.20 | 84 | 4.81 |
| 0.25 | 129 | 6.01 |
| 0.30 | 184 | 7.21 |

The target remains 90 structural families. If fewer pass independent review, keep the main run pending or prospectively approve a narrower exploratory study. Never increase within-family variants or treat policy conditions, readers or candidates as replacement clusters.
