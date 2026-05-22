"""Generate synthetic pairwise dependency comparisons using Claude via Bedrock.

Uses Claude 3.5 Haiku to generate pairwise comparisons of dependencies for each
repo, then aggregates using the Huber-log method (Bradley-Terry model) from
Level I to derive final weights.

The generated comparisons are validated against L2PublicEval.csv before submission.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore


def _load_bedrock_credentials() -> Tuple[str, str]:
    """Load and decode Bedrock API credentials from ~/.bedrock_key."""
    key_file = os.path.expanduser("~/.bedrock_key")
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"Bedrock key file not found: {key_file}")

    with open(key_file, "r") as f:
        encoded_key = f.read().strip()

    # Decode base64
    decoded = base64.b64decode(encoded_key)
    # Skip binary prefix (\x00\x14) and parse key:secret
    key_str = decoded[2:].decode("utf-8", errors="ignore")

    if ":" not in key_str:
        raise ValueError("Invalid key format: expected 'key:secret'")

    key_id, secret = key_str.split(":", 1)
    return key_id, secret


def _get_bedrock_client():
    """Create a Bedrock runtime client."""
    if boto3 is None:
        raise ImportError("boto3 required for Bedrock access. Install with: pip install boto3")

    key_id, secret = _load_bedrock_credentials()

    return boto3.client(
        "bedrock-runtime",
        region_name="us-east-1",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
    )


def _generate_comparisons_for_repo(
    repo_url: str,
    dependencies: List[str],
    client=None,
) -> List[Tuple[str, str, int, float]]:
    """Generate pairwise comparisons for a repo's dependencies using Claude.

    Args:
        repo_url: Full GitHub URL of the repo.
        dependencies: List of dependency GitHub URLs.
        client: Bedrock runtime client. If None, will create one.

    Returns:
        List of (dep_a_url, dep_b_url, choice, multiplier) tuples.
        choice=1 means dep_a is more important, choice=0 means dep_b is more important.
    """
    if not dependencies:
        return []

    if client is None:
        client = _get_bedrock_client()

    # Build a manageable subset of comparisons (up to 10 deps to reduce API calls)
    deps_sample = dependencies[: min(10, len(dependencies))]
    repo_short = repo_url.replace("https://github.com/", "")

    # Craft a prompt for pairwise comparisons
    prompt = f"""You are a technical evaluator assessing the importance of dependencies to an open-source project.

Repository: {repo_short}
Dependencies to evaluate: {', '.join(d.replace('https://github.com/', '') for d in deps_sample)}

For each pair of dependencies listed below, determine which one is more critical to the repository's functionality. Consider:
- How directly does this dependency support core functionality?
- How difficult would it be to replace this dependency?
- How critical is this to the repo's core mission?

Respond in JSON format with an array of comparisons, where each comparison has:
- "a": first dependency (just owner/repo, not URL)
- "b": second dependency (just owner/repo, not URL)
- "choice": 1 if "a" is more important, 0 if "b" is more important
- "confidence": how confident you are (0.5 to 2.0, where 1.0 is neutral)

Example format:
{{"comparisons": [{{"a": "ethereum/go-ethereum", "b": "libp2p/go-libp2p", "choice": 1, "confidence": 1.5}}]}}

Generate 5-10 diverse comparisons that cover different pairs:"""

    try:
        response = client.invoke_model(
            modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
            body=json.dumps({
                "prompt": prompt,
                "max_tokens": 1024,
                "temperature": 0.7,
            }).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read().decode("utf-8"))
        comparisons = []

        if "comparisons" in result:
            for comp in result["comparisons"]:
                a_url = f"https://github.com/{comp['a']}"
                b_url = f"https://github.com/{comp['b']}"
                choice = int(comp["choice"])
                confidence = float(comp.get("confidence", 1.0))

                comparisons.append((a_url, b_url, choice, confidence))

        return comparisons

    except Exception as e:
        print(f"Warning: Failed to generate comparisons for {repo_url}: {e}")
        return []


def derive_weights_from_comparisons(
    comparisons: List[Tuple[str, str, int, float]],
) -> Dict[str, float]:
    """Derive dependency weights from pairwise comparisons using Huber-log method.

    Solves for log-weights minimizing a Huber loss over signed log-ratios.
    This is the same Bradley-Terry aggregation used in Level I.

    Args:
        comparisons: List of (dep_a, dep_b, choice, multiplier) tuples.

    Returns:
        Dict mapping dependency URL to normalized weight.
    """
    if not comparisons:
        return {}

    # Extract unique repos
    deps = set()
    for a, b, _, _ in comparisons:
        deps.add(a)
        deps.add(b)

    repos = sorted(deps)
    idx = {r: i for i, r in enumerate(repos)}
    n = len(repos)

    if n == 0:
        return {}

    # Build observations (signed log-ratios)
    obs = []
    for a, b, choice, multiplier in comparisons:
        lr = np.log(max(multiplier, 1.0))
        sign = 1.0 if choice == 1 else -1.0
        obs.append((idx[a], idx[b], sign * lr))

    # Solve for log-weights with Huber weighting (robust to outliers)
    x = np.zeros(n)
    for _ in range(300):
        A = np.zeros((n, n))
        b_vec = np.zeros(n)

        for ai, bi, r in obs:
            res = (x[ai] - x[bi]) - r
            w = 1.0 if abs(res) <= 1.0 else 1.0 / abs(res)  # Huber weight
            A[ai, ai] += w
            A[bi, bi] += w
            A[ai, bi] -= w
            A[bi, ai] -= w
            b_vec[ai] += w * r
            b_vec[bi] -= w * r

        A += 1e-6 * np.eye(n)
        A[0, :] += 1.0  # Anchor to make system identifiable
        xn = np.linalg.solve(A, b_vec)
        xn -= xn.mean()

        if np.abs(xn - x).max() < 1e-10:
            x = xn
            break
        x = xn

    w = np.exp(x)
    w /= w.sum()
    return dict(zip(repos, w))


def generate_and_validate(
    l2_path: str = "data/seedReposWithDependenciesAndWeights.json",
    eval_path: str = "data/L2PublicEval.csv",
) -> Dict[str, Dict[str, float]]:
    """Generate AI-juror comparisons for L2PublicEval repos and validate.

    Args:
        l2_path: Path to L2 weights JSON.
        eval_path: Path to L2PublicEval.csv.

    Returns:
        Dict mapping repo URL to Dict[dependency URL -> weight].
    """
    # Load validation data
    eval_df = pd.read_csv(eval_path)
    eval_repos = eval_df["repo_url"].unique()

    # Load L2 data for reference
    with open(l2_path) as f:
        l2_weights = json.load(f)

    client = _get_bedrock_client()
    results = {}

    print(f"Generating AI-juror comparisons for {len(eval_repos)} evaluation repos...")

    for repo_url in eval_repos:
        # Get dependencies for this repo
        l2_deps = l2_weights.get(repo_url, {})
        if not l2_deps:
            print(f"  No dependencies found for {repo_url}")
            continue

        repo_short = repo_url.replace("https://github.com/", "")
        print(f"  Generating for {repo_short}...")

        # Generate comparisons
        comparisons = _generate_comparisons_for_repo(repo_url, list(l2_deps.keys()), client)

        if comparisons:
            # Derive weights from comparisons
            weights = derive_weights_from_comparisons(comparisons)

            if weights:
                results[repo_url] = weights
                print(f"    Generated {len(comparisons)} comparisons -> {len(weights)} unique deps")

    # Validate against L2PublicEval
    if results:
        print(f"\nValidating {len(results)} repos against L2PublicEval...")
        validate_against_eval(results, eval_df)

    return results


def validate_against_eval(
    generated_weights: Dict[str, Dict[str, float]],
    eval_df: pd.DataFrame,
) -> float:
    """Compute MAE between generated weights and real evaluations.

    Args:
        generated_weights: Dict[repo_url -> Dict[dep_url -> weight]].
        eval_df: Evaluation DataFrame with columns repo_url, dep_url, user_weight.

    Returns:
        Mean absolute error.
    """
    predictions = []
    ground_truth = []

    for _, row in eval_df.iterrows():
        repo = row["repo_url"]
        dep = row["dep_url"]
        true_weight = row["user_weight"]

        if repo in generated_weights and dep in generated_weights[repo]:
            pred_weight = generated_weights[repo][dep]
        else:
            pred_weight = 0.0  # Default for missing deps

        predictions.append(pred_weight)
        ground_truth.append(true_weight)

    predictions = np.array(predictions)
    ground_truth = np.array(ground_truth)

    mae = np.mean(np.abs(predictions - ground_truth))
    print(f"Mean Absolute Error: {mae:.6f}")

    # Also compute per-repo MAE
    eval_df_copy = eval_df.copy()
    eval_df_copy["pred"] = predictions
    eval_df_copy["true"] = ground_truth
    eval_df_copy["error"] = np.abs(eval_df_copy["pred"] - eval_df_copy["true"])

    per_repo_mae = eval_df_copy.groupby("repo_url")["error"].mean()
    print("\nPer-repo MAE:")
    for repo, mae in per_repo_mae.items():
        repo_short = repo.replace("https://github.com/", "")
        print(f"  {repo_short}: {mae:.6f}")

    return mae


if __name__ == "__main__":
    generate_and_validate()
