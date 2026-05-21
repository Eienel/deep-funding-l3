"""End-to-end pipeline for the Deep Funding Contest Level III.

Runs three steps in order:

1. **fetch**    - query GitHub for features (skippable with ``--skip-fetch``)
2. **score**    - turn features into normalized per-repo weights
3. **validate** - sanity-check the submission before upload

Usage::

    python main.py                # full pipeline
    python main.py --skip-fetch   # reuse data/features.csv, no API calls
"""

from __future__ import annotations

import argparse
import os

import pandas as pd

from src.fetch_features import (
    DEFAULT_OUTPUT_PATH as FEATURES_PATH,
    DEFAULT_PAIRS_PATH as PAIRS_PATH,
    fetch_features,
)
from src.score import DEFAULT_SUBMISSION_PATH as SUBMISSION_PATH, score
from src.validate import validate


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Deep Funding L3 pipeline.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse the existing data/features.csv and skip all GitHub API calls.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the fetch -> score -> validate pipeline and print a summary."""
    args = _parse_args()

    print("=" * 60)
    print("Deep Funding Contest Level III - submission pipeline")
    print("=" * 60)

    # Step 1: fetch features (or reuse).
    if args.skip_fetch:
        if not os.path.exists(FEATURES_PATH):
            raise FileNotFoundError(
                f"--skip-fetch was given but {FEATURES_PATH} does not exist. "
                "Run without --skip-fetch first."
            )
        print(f"[1/3] Skipping fetch; reusing {FEATURES_PATH}.")
    else:
        print(f"[1/3] Fetching features from GitHub using {PAIRS_PATH} ...")
        fetch_features(PAIRS_PATH, FEATURES_PATH)

    # Step 2: score.
    print(f"[2/3] Scoring features and writing {SUBMISSION_PATH} ...")
    submission = score(FEATURES_PATH, SUBMISSION_PATH)

    # Step 3: validate.
    print(f"[3/3] Validating {SUBMISSION_PATH} ...")
    validate(SUBMISSION_PATH)

    weights = pd.to_numeric(submission["weight"], errors="coerce")
    print("-" * 60)
    print("Summary")
    print(f"  Total pairs : {len(submission)}")
    print(f"  Total repos : {submission['repo'].nunique()}")
    print(f"  Weight min  : {weights.min():.6f}")
    print(f"  Weight max  : {weights.max():.6f}")
    print(f"  Weight mean : {weights.mean():.6f}")
    print("-" * 60)
    print("Upload submission.csv at joinpond.ai -> Submissions -> +Submit")


if __name__ == "__main__":
    main()
