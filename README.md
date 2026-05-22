# deep-funding-l3

Submission for the Deep Funding Contest Level III on joinpond.ai ($5,000 prize, deadline May 26 2026).

## What This Does

Assigns a weight to each (dependency, repo) pair so that all weights for a given repo sum to 1.0. Lower mean absolute error against jury market prices = better leaderboard score.

3,677 pairs across 83 repos.

## Approach

1. **Reverse-engineered the metric** — sum of absolute errors per repo, averaged across repos (matches the leaderboard exactly). `src/local_score.py` replicates it.
2. **Found the error concentration** — the top ~6 deps per repo cause 85-100% of the error.
3. **LLM-juror head correction** — Claude judges each repo's top dependencies by technical centrality; the funding baseline keeps the tail. Validated 0.344 -> 0.121 on the public eval; leaderboard confirmed 0.1206.

We deliberately did NOT paste the public answer key (which scores ~0 but proves nothing on hidden repos). Our submission carries genuine judgment for all 83 repos.

See `WRITEUP.md` for the full methodology.

## Setup

```bash
pip install -r requirements.txt
```

Place these files in `data/` (already included in this repo):

- `pairs_to_predict.csv`
- `seedReposWithDependenciesAndWeights.json`
- `seedReposWithNoTransitiveDependencies.json`
- `seedReposWithDependencies.json`
- `unweighted_graph.csv`

## Run

```bash
python run_ai_juror_pipeline.py    # builds the LLM-juror submission
python -c "from src.local_score import score_file; score_file('submission_ai_juror_full.csv')"
```

Output: `submission_ai_juror_full.csv` (the submission), scored locally against the public eval.

Upload at joinpond.ai -> Submissions -> +Submit.
