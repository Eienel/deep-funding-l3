# deep-funding-l3

Submission for the Deep Funding Contest Level III on joinpond.ai ($5,000 prize,
deadline May 26 2026).

Repository: https://github.com/Eienel/deep-funding-l3

## What This Does

Assigns a weight to each (dependency, repo) pair so that all weights for a given
repo add up to 1.0. A lower mean absolute error against the jury's market prices
means a better leaderboard score.

There are 3,677 pairs across 83 repos.

## Our Approach

1. **We reverse-engineered the scoring metric.** It is the sum of absolute errors
   per repo, averaged across repos (this matches the leaderboard exactly).
   `src/local_score.py` reproduces it so we can test ideas locally.
2. **We found where the error lives.** The top 6 or so dependencies per repo
   cause 85 to 100 percent of the error. The long tail barely matters.
3. **We correct the head with an expert juror.** Claude judges each repo's top
   dependencies by how central they are to the project, while the funding
   baseline keeps the tail. This took us from 0.344 to 0.121 on the public eval,
   and the leaderboard confirmed 0.1206.

We deliberately did NOT paste the public answer key (it scores near zero but
proves nothing on hidden repos). Our submission carries genuine judgment for all
83 repos.

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
python run_ai_juror_pipeline.py
python -c "from src.local_score import score_file; score_file('submission_ai_juror_full.csv')"
```

Output: `submission_ai_juror_full.csv` (the submission), scored locally against
the public eval.

Upload it at joinpond.ai, under Submissions, +Submit.
