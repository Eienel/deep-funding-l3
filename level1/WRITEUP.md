# Deep Funding Level I: Repository Contribution Weights

## The Problem

Assign a weight to each of 98 open-source repositories representing its
contribution to Ethereum. All 98 weights sum to 1.0. Lower sum of absolute
errors against the jury-derived weights means a better score.

## Key Observation

The jury's weights are computed from **pairwise comparisons** ("repo A is N times
more important than repo B"), aggregated by taking log-ratios and minimizing a
Huber loss. Two public sources let us reconstruct that signal:

1. **`oss-evals/train.csv`** — 627 real jury pairwise votes (37 jurors) over a
   47-repo subset, with the same parent (`ethereum`) and the same comparison
   format the contest scores against.
2. **GG24 Deep Funding Market Weights** — ELO scores derived from 41,000+
   pairwise comparisons across all 98 repos.

The human votes are the most faithful signal but only cover 47 repos. ELO covers
all 98. We combine them.

## The Approach

**ELO base (all 98 repos).** The published GG24 ELO market weights are used as
the base signal. They are derived from the same pairwise-comparison process the
contest uses and cover every repo.

**Human-vote refinement (47 voted repos).** We reconstruct repo weights from the
627 human votes using the contest's own method: each vote gives a signed
log-ratio `log(w_a / w_b)`; we solve for log-weights minimizing a Huber loss
(robust to outlier multipliers, which reach 999x), then exponentiate and
normalize. For repos that have human votes, we blend this signal with ELO via a
geometric mean, nudging the estimate toward the human jury without over-reacting
to extreme single votes.

**Normalization.** All 98 weights are normalized to sum to 1.0.

## Validation

With no public answer key for the full 98-repo set, we validate the vote model
by cross-validation on the 627 votes: holding out 25% of votes and predicting
their outcome from weights fit on the rest.

- Bradley-Terry from human votes: **75.8%** held-out vote-direction accuracy.
- ELO weights alone: **72.4%**.

The human-vote model is measurably better at predicting jury behavior, which is
why it is blended into the final weights for the repos it covers.

## Reproduction

```bash
pip install -r ../requirements.txt
python build_submission.py
```

Outputs:

- `submission_elo.csv` — ELO market-weight baseline.
- `submission_blend.csv` — ELO blended with the human jury-vote signal.

Both use the required format: `repo,parent,weight` with `parent=ethereum`.
