#!/usr/bin/env python3
"""End-to-end AI-juror pipeline for Level III.

Once AWS Bedrock access is approved, run:
    python run_ai_juror_pipeline.py

Steps:
1. Run Claude (Bedrock) over all 83 repos to correct each repo's head deps.
2. Blend corrections with L2 (Claude head + L2 tail), normalized per repo.
3. Build the full submission over pairs_to_predict.csv.
4. Score against L2PublicEval with the exact leaderboard metric.
5. Write submission_ai_juror.csv if it beats the 0.344 L2 baseline.

The expensive Claude step is cached to data/ai_juror_corrections.json, so steps
2-5 (and re-runs) are instant and free.
"""

from __future__ import annotations

import json

import pandas as pd

from src.ai_juror_generator import blend_corrections, generate_all
from src.local_score import score_submission
from src.validate import validate

L2_PATH = "data/seedReposWithDependenciesAndWeights.json"
PAIRS_PATH = "data/pairs_to_predict.csv"
OUT_PATH = "submission_ai_juror.csv"
BASELINE = 0.344


def _to_url(short: str) -> str:
    return f"https://github.com/{short}"


def build_submission(
    corrections: dict[str, dict[str, float]],
    l2: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Blend corrections with L2 and emit weights for every pair to predict."""
    pairs = pd.read_csv(PAIRS_PATH)

    # Per-repo blended weight maps.
    blended: dict[str, dict[str, float]] = {}
    for repo_url, l2_repo in l2.items():
        blended[repo_url] = blend_corrections(l2_repo, corrections.get(repo_url, {}))

    rows = []
    for _, r in pairs.iterrows():
        repo_url = _to_url(r["repo"])
        dep_url = _to_url(r["dependency"])
        w = blended.get(repo_url, {}).get(dep_url, 1e-8)
        rows.append({"dependency": dep_url, "repo": repo_url, "weight": w})

    sub = pd.DataFrame(rows, columns=["dependency", "repo", "weight"])
    # Re-normalize per repo over exactly the pairs we must predict.
    sub["weight"] = sub["weight"] / sub.groupby("repo")["weight"].transform("sum")
    return sub


def main() -> None:
    print("=" * 70)
    print("Deep Funding Level III - AI-Juror Pipeline")
    print("=" * 70)

    with open(L2_PATH) as f:
        l2 = json.load(f)

    print("\n[1/4] Generating Claude corrections (cached)...")
    try:
        corrections = generate_all(l2_path=L2_PATH)
    except Exception as e:
        print(f"ERROR: Bedrock generation failed: {e}")
        print("  Is AWS Bedrock access approved? Run: python check_readiness.py")
        return

    n_corrected = sum(1 for c in corrections.values() if c)
    print(f"  {n_corrected}/{len(corrections)} repos have corrections")

    print("\n[2/4] Blending corrections with L2 and building submission...")
    sub = build_submission(corrections, l2)
    sub.to_csv(OUT_PATH, index=False)
    print(f"  Wrote {len(sub)} rows to {OUT_PATH}")

    print("\n[3/4] Validating format...")
    validate(OUT_PATH)

    print("\n[4/4] Scoring against L2PublicEval (exact leaderboard metric)...")
    score = score_submission(sub)

    print("\n" + "-" * 70)
    print(f"AI-juror score: {score:.4f}   |   L2 baseline: {BASELINE:.4f}")
    if score < BASELINE:
        print(f"IMPROVED by {BASELINE - score:.4f}. Upload {OUT_PATH} to Pond:")
        print("  joinpond.ai -> Submissions -> +Submit")
    else:
        print("No improvement over baseline; keep current submission.csv.")
    print("=" * 70)


if __name__ == "__main__":
    main()
