"""Advanced dependency-weight scorer combining L2 weights and Personalized PageRank.

Strategy
--------
The contest pairs include both **direct** and **transitive** dependencies:

* **Direct deps** (3 517 / 3 677 pairs): present in the L2 predictions file
  ``seedReposWithDependenciesAndWeights.json``.  L2 weights are already
  well-calibrated and used as the primary signal.

* **Transitive deps** (160 pairs): not scored by L2.  Personalized PageRank
  (``alpha=0.85``) over the combined dependency graph is used to score them
  relative to direct deps.  Transitive deps are capped so they receive
  proportionally smaller weights than direct ones.

Final weights are normalised per-repo to sum to exactly 1.0.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple

import networkx as nx
import numpy as np
import pandas as pd

# ---------- default paths --------------------------------------------------
DEFAULT_PAIRS_PATH = os.path.join("data", "pairs_to_predict.csv")
DEFAULT_L2_PATH = os.path.join("data", "seedReposWithDependenciesAndWeights.json")
DEFAULT_NOTRANS_PATH = os.path.join("data", "seedReposWithNoTransitiveDependencies.json")
DEFAULT_DEPS_PATH = os.path.join("data", "seedReposWithDependencies.json")
DEFAULT_GRAPH_PATH = os.path.join("data", "unweighted_graph.csv")
DEFAULT_SUBMISSION_PATH = "submission.csv"

# Transitive deps get at most this fraction of the weight that the smallest
# direct dep receives.  Keeps them small but non-zero.
TRANSITIVE_SCALE = 0.05

# PageRank damping factor (higher = more weight to direct neighbours)
PR_ALPHA = 0.85
PR_MAX_ITER = 500
PR_TOL = 1e-8

# Absolute floor so no weight is ever truly zero
MIN_WEIGHT = 1e-7


def _to_url(short: str) -> str:
    return f"https://github.com/{short}"


def _to_short(url: str) -> str:
    return url.replace("https://github.com/", "")


def _build_graph(
    graph_csv_path: str,
    extra_deps_json_path: str,
) -> nx.DiGraph:
    """Build the combined dependency DiGraph.

    Edges go ``seed -> package`` (i.e. *seed* depends on *package*).
    The graph is built from:

    * ``unweighted_graph.csv`` – broad historical dependency graph.
    * ``seedReposWithDependencies.json`` – contest-specific edges, which
      ensures all 83 target repos have outgoing edges.

    Args:
        graph_csv_path: Path to ``unweighted_graph.csv``.
        extra_deps_json_path: Path to ``seedReposWithDependencies.json``.

    Returns:
        A :class:`networkx.DiGraph` with ``owner/repo`` node labels.
    """
    G: nx.DiGraph = nx.DiGraph()

    # 1. CSV graph (short owner/repo labels)
    df = pd.read_csv(graph_csv_path)
    for _, row in df.iterrows():
        seed = f"{row['seed_repo_owner']}/{row['seed_repo_name']}"
        pkg = f"{row['package_repo_owner']}/{row['package_repo_name']}"
        G.add_edge(seed, pkg)

    # 2. Contest-specific adjacency (full URLs → convert to short)
    with open(extra_deps_json_path) as fh:
        extra: Dict[str, list] = json.load(fh)
    for repo_url, dep_list in extra.items():
        seed = _to_short(repo_url)
        for dep_url in dep_list:
            pkg = _to_short(dep_url)
            G.add_edge(seed, pkg)

    return G


def _pagerank_for_repo(
    G: nx.DiGraph,
    repo: str,
) -> Dict[str, float]:
    """Run PersonalizedPageRank starting from *repo*.

    Returns an empty dict if *repo* has no outgoing edges.

    Args:
        G: Dependency DiGraph.
        repo: Short ``owner/repo`` label of the target repository.

    Returns:
        Mapping of ``owner/repo`` → PageRank score.
    """
    if repo not in G.nodes() or G.out_degree(repo) == 0:
        return {}
    try:
        return nx.pagerank(
            G,
            alpha=PR_ALPHA,
            personalization={repo: 1.0},
            max_iter=PR_MAX_ITER,
            tol=PR_TOL,
        )
    except nx.PowerIterationFailedConvergence:
        return nx.pagerank(
            G,
            alpha=PR_ALPHA,
            personalization={repo: 1.0},
            max_iter=PR_MAX_ITER * 2,
            tol=PR_TOL * 10,
        )


def score_advanced(
    pairs_path: str = DEFAULT_PAIRS_PATH,
    l2_path: str = DEFAULT_L2_PATH,
    notrans_path: str = DEFAULT_NOTRANS_PATH,
    deps_path: str = DEFAULT_DEPS_PATH,
    graph_path: str = DEFAULT_GRAPH_PATH,
    submission_path: str = DEFAULT_SUBMISSION_PATH,
) -> pd.DataFrame:
    """Compute weights and write the submission CSV.

    Args:
        pairs_path: Contest pairs CSV (``dependency``, ``repo``).
        l2_path: L2 predictions JSON (full URLs).
        notrans_path: No-transitive deps JSON (marks direct deps).
        deps_path: Full deps JSON used to build contest-specific graph edges.
        graph_path: ``unweighted_graph.csv`` for the broader dependency graph.
        submission_path: Output path for ``submission.csv``.

    Returns:
        The submission :class:`~pandas.DataFrame`.
    """
    # ------------------------------------------------------------------ load
    pairs = pd.read_csv(pairs_path)
    with open(l2_path) as fh:
        l2_weights: Dict[str, Dict[str, float]] = json.load(fh)
    with open(notrans_path) as fh:
        direct_sets: Dict[str, list] = json.load(fh)

    print("Building dependency graph …")
    G = _build_graph(graph_path, deps_path)
    print(f"  nodes={G.number_of_nodes():,}  edges={G.number_of_edges():,}")

    # ----------------------------------------------------------- score pairs
    rows = []
    all_repos = pairs["repo"].unique()
    print(f"Scoring {len(all_repos)} repos …")

    for i, repo in enumerate(all_repos, 1):
        if i % 20 == 0 or i == len(all_repos):
            print(f"  {i}/{len(all_repos)}")

        repo_url = _to_url(repo)
        repo_deps = pairs[pairs["repo"] == repo]["dependency"].tolist()

        l2_repo = l2_weights.get(repo_url, {})
        direct_repo = set(_to_short(d) for d in direct_sets.get(repo_url, []))

        # Run PersonalizedPageRank for this repo
        pr = _pagerank_for_repo(G, repo)

        # ----- compute raw scores
        raw: Dict[str, float] = {}
        direct_l2_min: Optional[float] = None  # track min direct weight

        for dep in repo_deps:
            dep_url = _to_url(dep)
            is_direct = dep in direct_repo
            l2_w = l2_repo.get(dep_url, 0.0)
            pr_w = pr.get(dep, MIN_WEIGHT)

            if is_direct and l2_w > 0:
                # L2 weight is highly reliable for direct deps
                raw[dep] = l2_w
                if direct_l2_min is None or l2_w < direct_l2_min:
                    direct_l2_min = l2_w
            elif is_direct:
                # Direct dep with no L2 weight: use PageRank
                raw[dep] = max(pr_w, MIN_WEIGHT)
            else:
                # Transitive dep: use PageRank, will be scaled down below
                raw[dep] = max(pr_w, MIN_WEIGHT)

        # Scale transitive deps relative to the smallest direct dep weight.
        # This ensures they stay small but non-zero.
        floor_direct = direct_l2_min if direct_l2_min is not None else MIN_WEIGHT
        transitive_cap = floor_direct * TRANSITIVE_SCALE

        for dep in repo_deps:
            is_direct = dep in direct_repo
            if not is_direct:
                # Normalise transitive PR scores within [MIN_WEIGHT, transitive_cap]
                raw[dep] = min(raw[dep], transitive_cap)

        # ----- normalise per repo
        total = sum(raw.values()) or 1.0
        for dep in repo_deps:
            rows.append(
                {
                    "dependency": _to_url(dep),
                    "repo": _to_url(repo),
                    "weight": raw[dep] / total,
                }
            )

    submission = pd.DataFrame(rows, columns=["dependency", "repo", "weight"])
    submission.to_csv(submission_path, index=False)
    print(f"Wrote {len(submission)} rows to {submission_path}")
    return submission


if __name__ == "__main__":
    score_advanced()
