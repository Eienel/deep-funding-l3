# Deep Funding Level III: Dependency Weight Model

## The Problem

For each of 83 repositories, assign a weight to every one of its dependencies
so that each repo's weights sum to 1.0. There are 3,677 (dependency, repo) pairs.
Submissions are scored against jury-derived weights; **lower error is better.**

## 1. We Reverse-Engineered the Scoring Metric

Most entries optimize blind, because the exact metric is not stated. We pinned it
down. The public evaluation set (`L2PublicEval.csv`, 162 pairs across 3 repos)
lets us score locally — but only if we use the *right* formula.

- Mean absolute error **per pair** gave 0.006 — nowhere near the leaderboard.
- **Sum of absolute errors per repo, averaged across repos** gave **0.3440**,
  matching our baseline's reported leaderboard score of **0.34** to four decimals.

```
score = mean_over_repos( sum_over_deps |predicted - jury| )
```

With an exact local replica of the scorer (`src/local_score.py`), we can evaluate
any idea before spending a submission.

## 2. The Error Lives in Each Repo's Top Dependencies

With local scoring, we measured where error comes from. Across the public repos,
**the top ~6 dependencies account for 85-100% of each repo's error.** The hundreds
of tiny dependencies are already close and barely matter.

The funding-derived baseline weights (`seedReposWithDependenciesAndWeights.json`)
have the right *shape* but mis-rank the head: they over-concentrate on one
dependency and mis-weight a few major libraries relative to how a human juror
values technical centrality.

## 3. The Fix: an LLM Juror that Corrects the Head

Rather than discard the funding baseline (which is well-calibrated in the tail),
we use a language model (Claude) as an **expert juror** that *corrects only the
head*. For each repo it is shown the top dependencies and assigns each a weight
reflecting how central and irreplaceable it is to what that repo actually does.
The tail keeps the baseline weight; everything is normalized per repo.

Crucially, the juror judges **each dependency on its own merits** — it is not told
which categories to favor. This keeps the method general rather than fitted to the
handful of repos we can see.

## Validation

Scored locally with the exact metric on the 3 public-eval repos:

| Model | Score (sum-per-repo) |
|---|---|
| Funding baseline | 0.344 |
| Crude directional corrections | 0.237 |
| LLM-juror head correction | **0.121** |

The public leaderboard confirmed this end to end: our corrected submission
returned **0.1206**, matching the local 0.121. The prior public leader *cluster*
sat at ~0.18; our generalizing model is below it.

## Why We Did Not Paste the Answer Key

`L2PublicEval.csv` is the public scoring set, so a submission that simply copies
those values scores ≈ 0 on the public board. Many top entries do exactly this. We
deliberately did **not**, because:

- The prize is decided on **hidden** repos, where no answer key exists.
- A copied submission demonstrates nothing that transfers to unseen data.

Our submission therefore carries the LLM-juror's genuine judgment for **all 83
repos** — the 3 public repos at ~0.12 (not 0), and the 80 hidden repos with the
same principled method. It is the strongest *generalizing* model we can defend,
not the lowest *public* number.

## Honest Limitations

We can only validate 3 of 83 repos. Those 3 confirm the mechanism (0.34 → 0.12).
The other 80 carry the same method applied fresh, which we expect to transfer but
cannot directly verify. This is an informed bet grounded in a validated mechanism.

## Reproduction

```bash
pip install -r requirements.txt
python run_ai_juror_pipeline.py   # or use the committed submission_ai_juror_full.csv
python -c "from src.local_score import score_file; score_file('submission_ai_juror_full.csv')"
```

The LLM-juror corrections are recorded in `data/claude_juror_corrections.py`;
`run_ai_juror_pipeline.py` blends them with the funding baseline and writes the
submission. `src/local_score.py` reproduces the exact leaderboard metric.

## Data Sources

From the `deepfunding/dependency-graph` public repository:

- `seedReposWithDependenciesAndWeights.json` — funding-derived baseline weights
- `seedReposWithDependencies.json` / `seedReposWithNoTransitiveDependencies.json` — dependency structure
- `L2PublicEval.csv` — public jury weights, used only as a held-out check
