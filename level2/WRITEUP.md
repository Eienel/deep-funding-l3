# Deep Funding Level II: Repository Originality Scores

## The Problem

Assign each of the 98 seed repos an **originality score** in [0, 1]: the share
of credit that belongs to the repo *itself* versus flowing to its dependencies.
Per the contest rubric:

- **~0.2** — a fork or thin wrapper; most value is in the dependencies.
- **~0.5** — heavy dependency use, but also substantial original work.
- **~0.8** — largely original work; dependencies are generic and replaceable.

The score is mean absolute error against the jury's averaged originality values.
As with the other levels, the visible leaderboard reflects only a **public test
subset**; the prize is decided on a **held-out private test set**. We therefore
optimize for generalization, not for the public board.

## Originality Is Not a Graph Formula

The natural first guess is that originality is computable from the dependency
graph — e.g. `1 − sum(outgoing dependency weights)`. We tested this directly
against the organizers' baseline on all 98 repos:

| Feature | Correlation with originality |
|---|---|
| Sum of outgoing dependency weights | **0.19** |
| Number of dependencies | **0.15** |
| log(1 + number of dependencies) | **0.19** |

Not only is the signal weak, its **sign is counter-intuitive**: repos that route
essentially all of their credit to dependencies (`sum ≈ 1`) tend to score
*higher* on originality (e.g. `blockscout` 0.77, `ethdebug/format` 0.74), while
repos with no tracked dependencies score *lower* (e.g. `argotorg/act` 0.33).
Originality here is a genuine **qualitative jury judgment** — how much original
engineering a project represents — not a quantity hiding in the edge weights.
There is no formula to fit and nothing to reverse-engineer mathematically.

## Why There Is No Trained Model

Unlike Level I (which ships `train.csv` with real juror pairwise votes), Level II
provides **no public originality labels**. There is nothing to fit or
cross-validate against, so a supervised model would be guessing at its own
accuracy. Instead we combine two **independent expert estimates** of each repo.

## The Approach: Ensemble of Two Independent Estimates

For every repo we average two estimates produced by different methods:

1. **LLM-juror assessment.** Each repo is scored against the rubric using what
   the project actually is in the Ethereum ecosystem, grouped by archetype:

   | Archetype | Originality | Rationale |
   |---|---|---|
   | Compilers / languages (solidity, vyper) | 0.76-0.78 | Original toolchains, generic deps |
   | Specs / standards (EIPs, consensus-specs) | 0.70-0.74 | Original writing, few deps |
   | Low-level crypto / EVM (blst, mcl, evmone) | 0.62-0.70 | Original primitives |
   | Clients (geth, reth, lighthouse, ...) | 0.55-0.68 | Large original impl atop real libs |
   | Frameworks / tools (foundry, hardhat, viem) | 0.42-0.55 | Substantial work, real dependency trees |
   | Packaging / ops / configs (eth-docker, helm-charts) | 0.25-0.35 | Mostly orchestration of others' work |
   | Forks / thin wrappers (scaffold-eth-2, hardhat-deploy) | 0.28-0.35 | Value concentrated in dependencies |

2. **Organizers' baseline** (`originality-predictions.csv`), a separately
   produced estimate shipped with the contest data.

The submitted value is the **mean of the two**. With two independent, roughly
unbiased estimators and no labels to choose between them, averaging is the
textbook way to reduce error variance on the unseen (private) test set: it
keeps the consensus where the two methods agree and splits the difference where
they disagree, instead of betting everything on either one. This is strictly
more defensible than hand-tuning 98 numbers toward a public board we cannot
validate against — and it is exactly the held-out set that decides the prize.

The effect is measurable: the ensemble preserves the mean originality (≈ 0.51)
while compressing the standard deviation from 0.167 (baseline alone) to 0.111,
pulling in the most extreme — and most error-prone — individual guesses. The
largest corrections are where the baseline disagrees sharply with the rubric,
e.g. `ethereum/eips` (0.25 → 0.48; specs are original writing, not derivative)
and `herumi/mcl` (0.30 → 0.50; an original cryptographic primitive).

## Reproduction

```bash
python level2/build_originality.py
```

Inputs: `level2/data/repos_to_predict.csv` (the 98 repos) and
`level2/data/originality-predictions.csv` (the baseline). Output:
`level2/submission_originality.csv` with columns `repo,originality`, one row per
repo.

## Possible Extensions

If juror originality labels are released, this becomes a supervised problem: fit
a model on features such as `is_fork`, dependency count, repo-vs-dependency star
ratio, and language, validated against jury labels — and learn the ensemble
weight between the LLM-juror and baseline estimates instead of fixing it at 0.5.
