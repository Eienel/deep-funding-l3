"""End-to-end pipeline for the Deep Funding Contest Level III.

Requires the following files in ``data/``:

* ``pairs_to_predict.csv``
* ``seedReposWithDependenciesAndWeights.json``
* ``seedReposWithNoTransitiveDependencies.json``
* ``seedReposWithDependencies.json``
* ``unweighted_graph.csv``

Run::

    python main.py
"""

from __future__ import annotations

import os

import pandas as pd

from src.score_advanced import (
    DEFAULT_SUBMISSION_PATH as SUBMISSION_PATH,
    score_advanced,
)
from src.validate import validate

PAIRS_PATH = os.path.join("data", "pairs_to_predict.csv")


def main() -> None:
    """Run the scoring pipeline and print a summary."""
    print("=" * 60)
    print("Deep Funding Contest Level III - submission pipeline")
    print("=" * 60)

    print("[1/2] Scoring with L2 weights + Personalized PageRank ...")
    submission = score_advanced(submission_path=SUBMISSION_PATH)

    print(f"[2/2] Validating {SUBMISSION_PATH} ...")
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
