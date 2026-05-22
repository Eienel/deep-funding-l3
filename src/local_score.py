"""Exact local replica of the Level III leaderboard scorer.

The leaderboard metric is the **sum of absolute errors per repo, averaged
across repos** (NOT mean absolute error per pair). This was reverse-engineered
by matching the local score (0.3440) to the reported leaderboard score (0.34)
on the current L2-baseline submission.

    score = mean_over_repos( sum_over_deps( |pred - truth| ) )

Use this to validate any candidate submission against L2PublicEval before
uploading to Pond.
"""

from __future__ import annotations

import pandas as pd


DEFAULT_EVAL_PATH = "data/L2PublicEval.csv"


def score_submission(
    submission: pd.DataFrame,
    eval_path: str = DEFAULT_EVAL_PATH,
    verbose: bool = True,
) -> float:
    """Score a submission against L2PublicEval using the leaderboard metric.

    Args:
        submission: DataFrame with columns ``dependency``, ``repo``, ``weight``.
        eval_path: Path to L2PublicEval.csv (ground-truth jury weights).
        verbose: Print per-repo breakdown if True.

    Returns:
        The leaderboard metric: mean over repos of (sum of abs errors per repo).
    """
    eval_df = pd.read_csv(eval_path)

    merged = eval_df.merge(
        submission,
        left_on=["repo_url", "dep_url"],
        right_on=["repo", "dependency"],
        how="left",
    )
    merged["weight"] = merged["weight"].fillna(0.0)
    merged["abserr"] = (merged["weight"] - merged["user_weight"]).abs()

    sum_per_repo = merged.groupby("repo_url")["abserr"].sum()
    metric = float(sum_per_repo.mean())

    if verbose:
        print(f"Leaderboard metric (sum-per-repo, avg): {metric:.4f}")
        for repo, s in sum_per_repo.items():
            short = repo.replace("https://github.com/", "")
            print(f"  {short}: {s:.4f}")

    return metric


def score_file(
    submission_path: str = "submission.csv",
    eval_path: str = DEFAULT_EVAL_PATH,
) -> float:
    """Score a submission CSV file against L2PublicEval.

    Args:
        submission_path: Path to the submission CSV.
        eval_path: Path to L2PublicEval.csv.

    Returns:
        The leaderboard metric.
    """
    submission = pd.read_csv(submission_path)
    return score_submission(submission, eval_path)


if __name__ == "__main__":
    score_file()
