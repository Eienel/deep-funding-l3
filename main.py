"""End-to-end pipeline for the Deep Funding Contest Level III.

Two modes
---------
``python main.py``
    Fast path: uses pre-downloaded L2 weights + Personalized PageRank.
    No GitHub API calls needed.  Requires the files in ``data/``:

    * ``pairs_to_predict.csv``
    * ``seedReposWithDependenciesAndWeights.json``
    * ``seedReposWithNoTransitiveDependencies.json``
    * ``seedReposWithDependencies.json``
    * ``unweighted_graph.csv``

``python main.py --github-features``
    Also queries the GitHub API for per-repo star/fork/language/recency
    signals and writes ``data/features.csv``.  Useful for experimentation
    but not required for a competitive submission.
"""

from __future__ import annotations

import argparse
import os

import pandas as pd

from src.score_advanced import (
    DEFAULT_SUBMISSION_PATH as SUBMISSION_PATH,
    score_advanced,
)
from src.validate import validate

PAIRS_PATH = os.path.join("data", "pairs_to_predict.csv")
FEATURES_PATH = os.path.join("data", "features.csv")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep Funding L3 pipeline.")
    parser.add_argument(
        "--github-features",
        action="store_true",
        help="Also fetch GitHub API features (stars, forks, etc.) into data/features.csv.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the scoring pipeline and print a summary."""
    args = _parse_args()

    print("=" * 60)
    print("Deep Funding Contest Level III - submission pipeline")
    print("=" * 60)

    # Optional: fetch GitHub API signals.
    if args.github_features:
        from src.fetch_features import fetch_features
        print(f"[opt] Fetching GitHub features into {FEATURES_PATH} …")
        fetch_features(PAIRS_PATH, FEATURES_PATH)

    # Step 1: advanced scoring (L2 weights + PageRank).
    print("[1/2] Scoring with L2 weights + Personalized PageRank …")
    submission = score_advanced(submission_path=SUBMISSION_PATH)

    # Step 2: validate.
    print(f"[2/2] Validating {SUBMISSION_PATH} …")
    validate(SUBMISSION_PATH)

    weights = pd.to_numeric(submission["weight"], errors="coerce")
    print("-" * 60)
    print("Summary")
    print(f"  Total pairs : {len(submission)}")
    print(f"  Total repos : {submission['repo'].nunique()}")
    print(f"  Weight min  : {weights.min():.8f}")
    print(f"  Weight max  : {weights.max():.6f}")
    print(f"  Weight mean : {weights.mean():.6f}")
    print("-" * 60)
    print("Upload submission.csv at joinpond.ai -> Submissions -> +Submit")


if __name__ == "__main__":
    main()
