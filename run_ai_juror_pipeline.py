#!/usr/bin/env python3
"""End-to-end AI-juror pipeline for Level III.

Once AWS Bedrock access is approved, run:
    python run_ai_juror_pipeline.py

This will:
1. Generate synthetic pairwise comparisons using Claude via Bedrock
2. Aggregate with Huber-log (Bradley-Terry method from Level I)
3. Validate against L2PublicEval.csv
4. If MAE < current best (0.34), integrate into final submission
5. Generate submission.csv for upload to Pond
"""

from __future__ import annotations

import json
import os
from typing import Dict

import numpy as np
import pandas as pd

from src.ai_juror_generator import (
    generate_and_validate,
    derive_weights_from_comparisons,
    validate_against_eval,
)
from src.score_advanced import score_advanced, _to_url, _to_short
from src.validate import validate


def integrate_ai_juror_weights(
    ai_weights: Dict[str, Dict[str, float]],
    l2_path: str = "data/seedReposWithDependenciesAndWeights.json",
    blend_ratio: float = 0.7,
) -> Dict[str, Dict[str, float]]:
    """Blend AI-juror weights with L2 baseline weights.

    For repos where we generated AI-juror comparisons, blend them with L2
    weights (weighted average, biased toward AI-juror if confident).

    Args:
        ai_weights: AI-generated weights per repo.
        l2_path: Path to L2 baseline weights.
        blend_ratio: Weight toward AI-juror (0.7 = 70% AI, 30% L2).

    Returns:
        Blended weights per repo.
    """
    with open(l2_path) as f:
        l2_weights = json.load(f)

    blended = {}

    for repo_url, ai_repo_weights in ai_weights.items():
        l2_repo_weights = l2_weights.get(repo_url, {})
        blended_repo = {}

        # Blend AI and L2 weights for all deps in AI result
        all_deps = set(ai_repo_weights.keys()) | set(l2_repo_weights.keys())

        for dep_url in all_deps:
            ai_w = ai_repo_weights.get(dep_url, 0.0)
            l2_w = l2_repo_weights.get(dep_url, 0.0)

            # Geometric mean blend (similar to Level I approach)
            if ai_w > 0 and l2_w > 0:
                # Both sources have data: blend with geometric mean
                blended_w = np.sqrt(ai_w * l2_w)
            else:
                # Use whichever source has data, or 0 if neither
                blended_w = ai_w if ai_w > 0 else l2_w

            if blended_w > 1e-8:  # Only keep non-trivial weights
                blended_repo[dep_url] = blended_w

        # Normalize to sum to 1.0
        total = sum(blended_repo.values()) or 1.0
        blended_repo = {k: v / total for k, v in blended_repo.items()}

        blended[repo_url] = blended_repo

    # Merge with L2 for repos we didn't generate AI comparisons for
    for repo_url, l2_repo_weights in l2_weights.items():
        if repo_url not in blended:
            blended[repo_url] = l2_repo_weights

    return blended


def score_with_ai_juror(
    ai_weights: Dict[str, Dict[str, float]],
    pairs_path: str = "data/pairs_to_predict.csv",
    submission_path: str = "submission_ai_juror.csv",
) -> pd.DataFrame:
    """Generate submission using blended AI-juror + L2 weights.

    Args:
        ai_weights: AI-generated dependency weights per repo.
        pairs_path: Contest pairs to predict.
        submission_path: Output submission file.

    Returns:
        Submission DataFrame.
    """
    # Blend AI and L2 weights
    blended = integrate_ai_juror_weights(ai_weights)

    # Load pairs to predict
    pairs = pd.read_csv(pairs_path)

    # Score each pair
    rows = []
    for _, row in pairs.iterrows():
        repo = row["repo"]
        dep = row["dependency"]
        repo_url = _to_url(repo)
        dep_url = _to_url(dep)

        # Get weight from blended dict
        repo_weights = blended.get(repo_url, {})
        weight = repo_weights.get(dep_url, 1e-8)

        rows.append({"dependency": dep_url, "repo": repo_url, "weight": weight})

    submission = pd.DataFrame(rows, columns=["dependency", "repo", "weight"])

    # Normalize per repo to sum to 1.0
    submission = submission.copy()
    total_per_repo = submission.groupby("repo")["weight"].transform("sum")
    submission["weight"] = submission["weight"] / total_per_repo

    submission.to_csv(submission_path, index=False)
    print(f"Wrote {len(submission)} rows to {submission_path}")

    return submission


def main() -> None:
    """Run the full AI-juror pipeline."""
    print("=" * 70)
    print("Deep Funding Level III - AI-Juror Pipeline")
    print("=" * 70)

    print("\n[1/4] Generating AI-juror comparisons via Bedrock/Claude...")
    try:
        ai_weights = generate_and_validate()
    except Exception as e:
        print(f"ERROR: Failed to generate AI-juror comparisons: {e}")
        print("  Is AWS Bedrock access approved? Check the AWS console.")
        return

    if not ai_weights:
        print("ERROR: No AI-juror weights generated. Cannot proceed.")
        return

    print(f"\n[2/4] Scoring with blended AI-juror + L2 weights...")
    submission_ai = score_with_ai_juror(ai_weights, submission_path="submission_ai_juror.csv")

    print(f"\n[3/4] Validating submission...")
    try:
        validate("submission_ai_juror.csv")
    except ValueError as e:
        print(f"ERROR: Validation failed: {e}")
        return

    # Compute expected score on L2PublicEval if possible
    eval_df = pd.read_csv("data/L2PublicEval.csv")
    predictions = []
    for _, row in eval_df.iterrows():
        repo = row["repo_url"]
        dep = row["dep_url"]
        pred = submission_ai[(submission_ai["repo"] == repo) & (submission_ai["dependency"] == dep)]
        if not pred.empty:
            predictions.append(pred["weight"].values[0])
        else:
            predictions.append(1e-8)

    eval_df["pred"] = predictions
    mae = np.mean(np.abs(eval_df["pred"] - eval_df["user_weight"]))
    print(f"\nEstimated MAE on L2PublicEval: {mae:.6f}")
    print(f"Current best (L2 baseline): 0.34")

    if mae < 0.34:
        print("✓ AI-juror weights beat the baseline! Ready to submit.")
        print("\nFinal step: Upload submission_ai_juror.csv to Pond at")
        print("  joinpond.ai -> Submissions -> +Submit")
    else:
        print(f"✗ AI-juror MAE ({mae:.6f}) does not beat baseline (0.34)")
        print("  Keeping L2 baseline for submission (submission.csv)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
