# Deep Funding Level II: Repository Originality Scores

## The Problem

Assign each of the 98 seed repos an **originality score** in [0, 1]: the share
of credit that belongs to the repo *itself* versus flowing to its dependencies.
Per the contest rubric:

- **~0.2** — a fork or thin wrapper; most value is in the dependencies.
- **~0.5** — heavy dependency use, but also substantial original work.
- **~0.8** — largely original work; dependencies are generic and replaceable.

Score = sum of absolute errors against the jury's averaged originality scores.

## Why There Is No Trained Model

Unlike Level I (which ships `train.csv` with real juror pairwise votes), Level II
provides **no public originality labels**. There is nothing to fit or
cross-validate against, so a supervised model would be guessing at its own
accuracy. We therefore use **direct expert (LLM-juror) assessment** — the same
technique the strongest Level I / III entries use, applied to originality.

## The Approach

Each repo is scored against the rubric using what the project actually is in the
Ethereum ecosystem, grouped by archetype:

| Archetype | Originality | Rationale |
|---|---|---|
| Compilers / languages (solidity, vyper) | 0.76-0.78 | Original toolchains, generic deps |
| Specs / standards (EIPs, consensus-specs) | 0.70-0.74 | Original writing, few deps |
| Low-level crypto / EVM (blst, mcl, evmone) | 0.62-0.70 | Original primitives |
| Clients (geth, reth, lighthouse, ...) | 0.55-0.68 | Large original impl atop real libs |
| Frameworks / tools (foundry, hardhat, viem) | 0.42-0.55 | Substantial work, real dependency trees |
| Packaging / ops / configs (eth-docker, helm-charts) | 0.25-0.35 | Mostly orchestration of others' work |
| Forks / thin wrappers (scaffold-eth-2, hardhat-deploy) | 0.28-0.35 | Value concentrated in dependencies |

Scores land in [0.25, 0.78] with mean ≈ 0.51, matching the rubric's expected
spread (no repo is purely a fork or purely standalone).

## Reproduction

```bash
python build_originality.py
```

Output: `submission_originality.csv` with columns `repo,originality`, one row per
of the 98 seed repos.

## Possible Extensions

With juror originality data (if released), this becomes a supervised problem:
fit a model on features such as `is_fork`, dependency count, repo-vs-dependency
star ratio, and language, validated against jury labels — the same Bradley-Terry
+ GitHub-feature hybrid that works for Level I.
