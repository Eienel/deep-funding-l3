# deep-funding-l3

Submission pipeline for the **Deep Funding Contest Level III** on
[joinpond.ai](https://joinpond.ai) ($5,000 prize, deadline May 26 2026).

## Problem

Given pairs of `(dependency, repo)`, assign a `weight` to each pair so that,
for every repo, all of its dependency weights sum to `1.0`. A lower absolute
error versus market prices yields a better leaderboard score.

## Approach

For each dependency repo we pull GitHub signals (stars, forks, language,
recency of pushes) and check whether the dependency is actually declared in
one of the target repo's manifest files (`package.json`, `requirements.txt`,
`go.mod`, `Cargo.toml`, `setup.py`, `pyproject.toml`, `composer.json`). These
signals are combined into a `raw_score` and normalized per repo so the weights
sum to `1.0`.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Add a GitHub token (a classic or fine-grained token with public-repo read
   access is enough) to a `.env` file:

   ```bash
   cp .env.example .env
   # then edit .env and set GITHUB_TOKEN=...
   ```

3. Place the contest input file at `data/pairs_to_predict.csv`. It must have
   the columns `dependency` and `repo`, each a full GitHub URL.

## Run

```bash
python main.py
```

This runs the full pipeline (fetch -> score -> validate) and writes
`submission.csv`. To re-score without hitting the GitHub API again (reusing
`data/features.csv`):

```bash
python main.py --skip-fetch
```

You can also run the steps individually:

```bash
python -m src.fetch_features   # writes data/features.csv
python -m src.score            # writes submission.csv
python -m src.validate         # checks submission.csv
```

## Output

`submission.csv` has exactly three columns:

```csv
dependency,repo,weight
https://github.com/ethereum/web3.py,https://github.com/ethereum/ethereum,0.3
```

Upload `submission.csv` on Pond: **joinpond.ai -> Submissions -> +Submit**.

## Files

| Path                      | Purpose                                            |
| ------------------------- | -------------------------------------------------- |
| `src/fetch_features.py`   | Fetch GitHub features into `data/features.csv`.     |
| `src/score.py`            | Compute normalized weights into `submission.csv`.   |
| `src/validate.py`         | Validate the submission before upload.              |
| `main.py`                 | Run the full pipeline end to end.                  |
| `requirements.txt`        | Python dependencies.                               |
| `.env.example`            | Template for your `GITHUB_TOKEN`.                  |

Errors during fetching are logged to `logs/errors.log`.
