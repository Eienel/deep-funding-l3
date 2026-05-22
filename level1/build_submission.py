"""Build Level I submissions: weight 98 repos by contribution to Ethereum.

Format required by Pond: columns ``repo,parent,weight`` where ``parent`` is the
literal string ``ethereum`` and weights over the 98 repos sum to 1.0.

Two outputs:
* ``submission_elo.csv``   - published GG24 ELO market weights (safe baseline).
* ``submission_blend.csv`` - ELO with the human jury signal (Bradley-Terry on
  627 votes) blended in via geometric mean for the repos that have votes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ELO_PATH = "level1/data/elo_phase2.csv"
VOTES_PATH = "level1/data/train.csv"
PARENT = "ethereum"


def _norm(url: str) -> str:
    return url.replace("https://github.com/", "").strip().lower()


def derive_bt_weights(votes: pd.DataFrame) -> dict[str, float]:
    """Solve for log-weights minimising a Huber loss over signed log-ratios."""
    votes = votes.copy()
    votes["a"] = votes["repo_a"].map(_norm)
    votes["b"] = votes["repo_b"].map(_norm)
    repos = sorted(set(votes["a"]) | set(votes["b"]))
    idx = {r: i for i, r in enumerate(repos)}
    n = len(repos)

    obs = []
    for _, r in votes.iterrows():
        lr = np.log(max(r["multiplier"], 1.0))
        sign = 1.0 if r["choice"] == 1 else -1.0
        obs.append((idx[r["a"]], idx[r["b"]], sign * lr))

    x = np.zeros(n)
    for _ in range(300):
        A = np.zeros((n, n))
        b = np.zeros(n)
        for ai, bi, r in obs:
            res = (x[ai] - x[bi]) - r
            w = 1.0 if abs(res) <= 1.0 else 1.0 / abs(res)  # Huber weight
            A[ai, ai] += w
            A[bi, bi] += w
            A[ai, bi] -= w
            A[bi, ai] -= w
            b[ai] += w * r
            b[bi] -= w * r
        A += 1e-6 * np.eye(n)
        A[0, :] += 1.0  # anchor to make the system identifiable
        xn = np.linalg.solve(A, b)
        xn -= xn.mean()
        if np.abs(xn - x).max() < 1e-10:
            x = xn
            break
        x = xn

    w = np.exp(x)
    w /= w.sum()
    return dict(zip(repos, w))


def main() -> None:
    elo = pd.read_csv(ELO_PATH)
    votes = pd.read_csv(VOTES_PATH)
    bt = derive_bt_weights(votes)

    elo = elo.copy()
    elo["repo"] = "https://github.com/" + elo["item"]
    elo["norm"] = elo["item"].map(lambda s: s.strip().lower())

    # --- pure ELO baseline
    base = elo[["repo"]].copy()
    base["parent"] = PARENT
    base["weight"] = (elo["weight"] / elo["weight"].sum()).values
    base.to_csv("level1/submission_elo.csv", index=False)

    # --- ELO blended with human votes (geometric mean where votes exist)
    blended = np.array(elo["weight"].astype(float).values, dtype=float)
    for i, nm in enumerate(elo["norm"].values):
        if nm in bt:
            blended[i] = np.sqrt(elo["weight"].values[i] * bt[nm])
    blended = blended / blended.sum()
    out = elo[["repo"]].copy()
    out["parent"] = PARENT
    out["weight"] = blended
    out.to_csv("level1/submission_blend.csv", index=False)

    n_voted = sum(nm in bt for nm in elo["norm"])
    print(f"Repos: {len(elo)}  with human votes: {n_voted}")
    print("Wrote level1/submission_elo.csv and level1/submission_blend.csv")
    print(f"  ELO   sum={base['weight'].sum():.6f}")
    print(f"  Blend sum={out['weight'].sum():.6f}")


if __name__ == "__main__":
    main()
