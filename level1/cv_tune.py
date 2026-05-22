"""Cross-validate the ELO<->human-vote blend for Level I.

The submission blends published GG24 ELO weights with a Bradley-Terry fit on the
627 human jury votes. The blend is done in log space:

    x_blend = (1 - alpha) * log(elo) + alpha * log(bt)

with alpha fixed at 0.5 (a plain geometric mean) in build_submission.py. This
script sweeps alpha by k-fold CV on the votes, scoring held-out vote-direction
accuracy, to find whether 0.5 is actually optimal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ELO_PATH = "level1/data/elo_phase2.csv"
VOTES_PATH = "level1/data/train.csv"


def _norm(url: str) -> str:
    return url.replace("https://github.com/", "").strip().lower()


def fit_bt(votes: pd.DataFrame) -> dict[str, float]:
    """Bradley-Terry log-weights via Huber-weighted least squares on log-ratios."""
    a = votes["repo_a"].map(_norm).to_numpy()
    b = votes["repo_b"].map(_norm).to_numpy()
    repos = sorted(set(a) | set(b))
    idx = {r: i for i, r in enumerate(repos)}
    n = len(repos)

    lr = np.log(np.maximum(votes["multiplier"].to_numpy(), 1.0))
    sign = np.where(votes["choice"].to_numpy() == 1, 1.0, -1.0)
    obs = list(zip((idx[r] for r in a), (idx[r] for r in b), sign * lr))

    x = np.zeros(n)
    for _ in range(300):
        A = np.zeros((n, n))
        rhs = np.zeros(n)
        for ai, bi, r in obs:
            res = (x[ai] - x[bi]) - r
            w = 1.0 if abs(res) <= 1.0 else 1.0 / abs(res)
            A[ai, ai] += w
            A[bi, bi] += w
            A[ai, bi] -= w
            A[bi, ai] -= w
            rhs[ai] += w * r
            rhs[bi] -= w * r
        A += 1e-6 * np.eye(n)
        A[0, :] += 1.0
        xn = np.linalg.solve(A, rhs)
        xn -= xn.mean()
        if np.abs(xn - x).max() < 1e-10:
            x = xn
            break
        x = xn
    return dict(zip(repos, x))  # log-weights, mean-centered


def cv_accuracy(alpha: float, votes: pd.DataFrame, log_elo: dict[str, float],
                folds: list[np.ndarray], rng_votes: pd.DataFrame) -> float:
    correct = total = 0
    for k in range(len(folds)):
        test_idx = folds[k]
        train = rng_votes.drop(index=test_idx)
        test = rng_votes.loc[test_idx]
        bt = fit_bt(train)
        for _, r in test.iterrows():
            a, b = _norm(r["repo_a"]), _norm(r["repo_b"])
            if a not in bt or b not in bt or a not in log_elo or b not in log_elo:
                continue
            xa = (1 - alpha) * log_elo[a] + alpha * bt[a]
            xb = (1 - alpha) * log_elo[b] + alpha * bt[b]
            pred_a_wins = xa > xb
            actual_a_wins = r["choice"] == 1
            correct += int(pred_a_wins == actual_a_wins)
            total += 1
    return correct / total if total else float("nan")


def main() -> None:
    votes = pd.read_csv(VOTES_PATH).reset_index(drop=True)
    elo = pd.read_csv(ELO_PATH)
    log_elo = {_norm(i): np.log(w) for i, w in zip(elo["item"], elo["weight"])}

    rng = np.random.default_rng(42)
    perm = rng.permutation(len(votes))
    folds = [perm[i::5] for i in range(5)]  # 5-fold

    print(f"votes: {len(votes)}  | 5-fold CV vote-direction accuracy by blend alpha")
    print(f"  alpha=0.0 is pure ELO, alpha=1.0 is pure Bradley-Terry\n")
    best = (-1.0, None)
    for alpha in np.round(np.arange(0.0, 1.01, 0.1), 2):
        acc = cv_accuracy(alpha, votes, log_elo, folds, votes)
        flag = ""
        if acc > best[0]:
            best = (acc, alpha)
            flag = "  <- best so far"
        print(f"  alpha={alpha:.1f}   acc={acc:.4f}{flag}")
    print(f"\nBEST: alpha={best[1]:.1f}  acc={best[0]:.4f}   (current build uses 0.5)")


if __name__ == "__main__":
    main()
