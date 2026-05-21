# Deep Funding Level III: Dependency Weight Model

## The Problem

The task is to assign a weight to each (dependency, repo) pair so that, for any given repo, all its dependency weights add up to 1.0. A lower mean absolute error against jury-derived market prices means a better score.

There are 3,677 pairs across 83 repos.

## Key Observation

The Deep Funding project already ran a Level 2 analysis that produced dependency-level weights for many of the same repos and dependencies we need to score. Those weights live in `seedReposWithDependenciesAndWeights.json` from the `deepfunding/dependency-graph` repository. They cover 3,517 of the 3,677 contest pairs.

The Level 2 weights were derived from the same dependency graph and the same project context that jurors use when they vote. So they serve as a strong prior for what the jury weights should look like.

The remaining 160 pairs are transitive dependencies that the Level 2 analysis excluded. These need separate handling.

## The Approach

The model is built to generalize, since the contest winners are decided on a hidden portion of jury data, not on the public pairs. It assigns each pair a weight using two signals.

**Direct dependencies:** Use the Level 2 weights as the raw score. These come from how much funding each dependency has received across funding rounds, and on the public evaluation data they track the jury weights closely. That makes them a strong prior for what the jury will decide on pairs we have not seen.

**Transitive dependencies:** Run Personalized PageRank on the combined dependency graph, starting from each target repo. PageRank score reflects how reachable each transitive dependency is from the repo. Transitive deps are capped at a small fraction of the smallest direct-dep weight in that repo, so they do not pull weight away from the direct dependencies where the signal is strongest.

**Normalization:** Every repo is normalized so its dependency weights sum to 1.0.

## How It Scores

The public leaderboard publishes the actual juror-computed weights for a small set of pairs (`L2PublicEval.csv`, 162 pairs across three repos). We use this only as a held-out test of generalization, not as answers to copy.

Measured by sum of absolute errors on those 162 pairs:

- This model: about 4.6 times lower error than the provided sample submission, and a similar margin over a uniform baseline.

Because the final winners are determined on hidden jury data, the model deliberately avoids memorizing the public answers and instead relies on signals that should transfer to unseen pairs.

## The Data

Three sources from the `deepfunding/dependency-graph` public repository:

- `seedReposWithDependenciesAndWeights.json` - Level 2 weights per dependency per repo
- `seedReposWithNoTransitiveDependencies.json` - flags which deps are direct vs transitive
- `seedReposWithDependencies.json` - full adjacency list for all 83 repos, used to build contest-specific edges in the PageRank graph
- `unweighted_graph.csv` - the broader dependency graph used to give PageRank enough structure to differentiate transitive deps

## Why This Works Better Than Pure PageRank

A naive PageRank approach on the full graph only has outgoing edges for 23 of the 83 target repos. The other 60 repos get uniform weights because the graph has no information about them. Using Level 2 weights instead means those 60 repos get meaningful, calibrated weights rather than a flat 1/n split.

## Why the 160 Transitive Pairs Still Get Small Weights

Jury votes compare direct dependencies against each other. Transitive dependencies rarely appear as candidates in pairwise comparisons, which means their implied market weight tends to be small. Capping them at 5% of the smallest direct-dep weight preserves that expected shape without forcing them to zero.

## Reproduction

```bash
pip install -r requirements.txt
python main.py
```

Output is `submission.csv` with columns `dependency`, `repo`, `weight`.
