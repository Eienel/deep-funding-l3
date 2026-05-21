"""Turn fetched features into normalized dependency weights.

Reads ``data/features.csv``, computes a heuristic ``raw_score`` per
(dependency, repo) pair, and normalizes the scores so that every repo's
dependency weights sum to ``1.0``. The result is written to
``submission.csv`` in the contest's required format.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

DEFAULT_FEATURES_PATH = os.path.join("data", "features.csv")
DEFAULT_SUBMISSION_PATH = "submission.csv"

# Heuristic weights for the raw score components.
W_DIRECT = 5.0
W_STARS = 0.5
W_FORKS = 0.3
W_LANGUAGE = 0.5
W_RECENCY = 0.2

# Floor so that no pair ever receives a zero raw score.
MIN_RAW_SCORE = 0.001


def score(
    features_path: str = DEFAULT_FEATURES_PATH,
    submission_path: str = DEFAULT_SUBMISSION_PATH,
) -> pd.DataFrame:
    """Compute normalized weights and write the submission CSV.

    Args:
        features_path: Path to the feature CSV produced by ``fetch_features``.
        submission_path: Path where the submission CSV is written.

    Returns:
        The submission :class:`pandas.DataFrame` with ``dependency``,
        ``repo`` and ``weight`` columns.
    """
    features = pd.read_csv(features_path)

    # Defensive cleaning so the arithmetic below is always well-defined.
    numeric_cols = ["stars", "forks", "days_since_push", "is_direct_dependency"]
    for col in numeric_cols:
        features[col] = pd.to_numeric(features[col], errors="coerce").fillna(0)
    for col in ["dep_language", "repo_language"]:
        features[col] = features[col].fillna("").astype(str)

    stars_log = np.log(features["stars"] + 1.0)
    forks_log = np.log(features["forks"] + 1.0)
    language_match = (
        (features["dep_language"] != "")
        & (features["dep_language"] == features["repo_language"])
    ).astype(float)
    recency = 1.0 / (1.0 + features["days_since_push"] / 365.0)

    raw_score = (
        features["is_direct_dependency"] * W_DIRECT
        + stars_log * W_STARS
        + forks_log * W_FORKS
        + language_match * W_LANGUAGE
        + recency * W_RECENCY
    )
    raw_score = raw_score.clip(lower=MIN_RAW_SCORE)

    submission = features[["dependency", "repo"]].copy()
    submission["raw_score"] = raw_score

    group_totals = submission.groupby("repo")["raw_score"].transform("sum")
    submission["weight"] = submission["raw_score"] / group_totals

    submission = submission[["dependency", "repo", "weight"]]
    submission.to_csv(submission_path, index=False)
    print(f"Wrote {len(submission)} weighted rows to {submission_path}")
    return submission


if __name__ == "__main__":
    score()
