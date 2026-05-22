"""Local scorer for the Level II (Farm to Forest / originality) task.

The contest scores originality predictions by mean absolute error (MAE) against
the jury's originality values. Point this at a submission CSV (repo,originality)
and an eval CSV (repo,originality) downloaded from Pond to get the exact local
score before spending a real submission.

Usage:
    python level2/score_local.py SUBMISSION.csv EVAL.csv
"""

from __future__ import annotations

import sys

import pandas as pd


def _norm(url: str) -> str:
    return str(url).replace("https://github.com/", "").strip().lower()


def score(submission_path: str, eval_path: str) -> float:
    sub = pd.read_csv(submission_path)
    ev = pd.read_csv(eval_path)
    # value is whatever the last column is (tolerates "originality" or other names)
    sub = sub.rename(columns={sub.columns[0]: "repo", sub.columns[-1]: "val_sub"})
    ev = ev.rename(columns={ev.columns[0]: "repo", ev.columns[-1]: "val_eval"})
    sub["k"] = sub["repo"].map(_norm)
    ev["k"] = ev["repo"].map(_norm)

    m = ev[["k", "val_eval"]].merge(sub[["k", "val_sub"]], on="k")
    missing = sorted(set(ev["k"]) - set(sub["k"]))
    if missing:
        print(f"WARNING: {len(missing)} eval repos missing from submission:")
        for k in missing[:20]:
            print(f"  {k}")

    err = (m["val_sub"] - m["val_eval"]).abs()
    mae = err.mean()
    print(f"\nScored {len(m)} repos | MAE = {mae:.4f}")
    worst = m.assign(err=err).sort_values("err", ascending=False).head(15)
    print("\nWorst 15 repos (largest error):")
    for _, r in worst.iterrows():
        print(f"  {r['k']:45s} err={r['err']:.3f}")
    return mae


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python level2/score_local.py SUBMISSION.csv EVAL.csv")
        raise SystemExit(1)
    score(sys.argv[1], sys.argv[2])
