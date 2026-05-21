# deep-funding-l3

Submission for the Deep Funding Contest Level III on joinpond.ai ($5,000 prize, deadline May 26 2026).

## What This Does

Assigns a weight to each (dependency, repo) pair so that all weights for a given repo sum to 1.0. Lower mean absolute error against jury market prices = better leaderboard score.

3,677 pairs across 83 repos.

## Approach

For the 3,517 pairs covered by the Level 2 Deep Funding analysis, the model uses the existing L2 weights directly. These are well-calibrated against the same signals that jurors use.

For the remaining 160 transitive-dependency pairs that L2 did not cover, the model runs Personalized PageRank on the full dependency graph and assigns proportionally small weights.

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
python main.py
```

Output: `submission.csv`

Upload at joinpond.ai -> Submissions -> +Submit.
