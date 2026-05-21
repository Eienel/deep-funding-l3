"""Validate the submission CSV before uploading to Pond.

Checks that the file has exactly the three required columns, contains no
NaN or negative weights, and that every repo's weights sum to ``1.0``
within a small tolerance.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_SUBMISSION_PATH = "submission.csv"
REQUIRED_COLUMNS = ["dependency", "repo", "weight"]
SUM_TOLERANCE = 1e-4


def validate(submission_path: str = DEFAULT_SUBMISSION_PATH) -> None:
    """Validate a submission CSV, raising ``ValueError`` on any problem.

    Args:
        submission_path: Path to the submission CSV to validate.

    Raises:
        ValueError: If columns, NaNs, negatives, or per-repo weight sums
            fail their checks.
    """
    submission = pd.read_csv(submission_path)

    if list(submission.columns) != REQUIRED_COLUMNS:
        raise ValueError(
            f"Expected exactly columns {REQUIRED_COLUMNS}, "
            f"found {list(submission.columns)}."
        )

    if submission.isna().any().any():
        bad = submission[submission.isna().any(axis=1)]
        raise ValueError(f"Found {len(bad)} row(s) containing NaN values.")

    weights = pd.to_numeric(submission["weight"], errors="coerce")
    if weights.isna().any():
        raise ValueError("Column 'weight' contains non-numeric values.")
    if (weights < 0).any():
        count = int((weights < 0).sum())
        raise ValueError(f"Found {count} negative weight(s).")

    sums = submission.groupby("repo")["weight"].sum()
    offenders = sums[(sums - 1.0).abs() > SUM_TOLERANCE]
    if not offenders.empty:
        sample = offenders.head(5).to_dict()
        raise ValueError(
            f"{len(offenders)} repo(s) have weights that do not sum to 1.0 "
            f"(within {SUM_TOLERANCE}). Examples: {sample}"
        )

    n_repos = submission["repo"].nunique()
    n_pairs = len(submission)
    print(f"✓ {n_repos} repos validated. {n_pairs} pairs. Ready to submit.")


if __name__ == "__main__":
    validate()
