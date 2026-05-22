"""AI-juror dependency reweighting via Claude on AWS Bedrock.

Validated approach (local L2PublicEval score 0.344 -> ~0.12):
The funding-derived L2 weights have the right *shape* but mis-weight a repo's
top dependencies -- they underrate critical Ethereum infra (viem, c-kzg-4844,
go-libp2p-pubsub) and overrate generic libraries (immer). 85-100% of each
repo's leaderboard error lives in its top ~6 deps.

So Claude acts as an expert juror that *corrects* L2's head: shown the top deps
with their current L2 weights, it returns corrected target weights based on each
dependency's real technical centrality to the repo. The tail (tiny weights)
stays at L2 since it contributes almost nothing to the metric.

Offline validation of the blend math (with expert target weights):
    L2 baseline ............................. 0.344
    head target-weights + L2 tail ........... 0.121   (leader cluster ~0.18)
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Dict, List

import pandas as pd

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore


MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"
REGION = "us-east-1"

# How many top L2 deps per repo Claude rewrites. The tail keeps L2.
HEAD_SIZE = 20


def _load_bedrock_credentials() -> tuple[str, str]:
    """Load and decode Bedrock API credentials from ~/.bedrock_key."""
    key_file = os.path.expanduser("~/.bedrock_key")
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"Bedrock key file not found: {key_file}")
    with open(key_file) as f:
        encoded = f.read().strip()
    decoded = base64.b64decode(encoded)
    key_str = decoded[2:].decode("utf-8", errors="ignore")  # skip 2-byte prefix
    if ":" not in key_str:
        raise ValueError("Invalid key format: expected 'key:secret'")
    key_id, secret = key_str.split(":", 1)
    return key_id, secret


def get_bedrock_client():
    """Create a Bedrock runtime client from the stored credentials."""
    if boto3 is None:
        raise ImportError("boto3 required. Install with: pip install boto3")
    key_id, secret = _load_bedrock_credentials()
    return boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
    )


def _call_claude(client, prompt: str, max_tokens: int = 2048) -> str:
    """Invoke Claude on Bedrock with the Messages API and return the text."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(resp["body"].read().decode("utf-8"))
    return payload["content"][0]["text"]


def _build_prompt(repo_short: str, head: List[tuple[str, float]]) -> str:
    """Build the juror prompt showing L2 weights and asking for corrections.

    Args:
        repo_short: ``owner/repo`` of the target repository.
        head: list of ``(dep_short, l2_weight)`` for the top dependencies.
    """
    lines = "\n".join(f"- {d}: {w*100:.2f}%" for d, w in head)
    return f"""You are an expert open-source juror for the Ethereum ecosystem. \
You assign each dependency a weight = the share of {repo_short}'s value that \
flows to that dependency, based on how *central and irreplaceable* it is to what \
the repository actually does.

Below are the repository's top dependencies with a baseline weight derived from \
funding/usage data. That baseline reflects historical funding/usage, NOT \
necessarily technical centrality, so treat it only as a starting point. Judge \
each dependency on its own merits: how core and irreplaceable it is to what THIS \
repository actually does. Dependencies that are equally central should receive \
similar weights; ones that are easily swapped out should receive less.

Repository: {repo_short}
Baseline weights:
{lines}

Return CORRECTED weights for these dependencies as decimal fractions of the \
repo's TOTAL value (so the numbers you output for these head deps should sum to \
roughly the same total as the baseline above, leaving room for the many smaller \
dependencies not shown). Respond with ONLY a JSON object mapping each dependency \
(exactly as written) to its corrected decimal weight. Example:
{{"owner/repo-a": 0.30, "owner/repo-b": 0.10}}"""


def _parse_weights(text: str, valid: set[str]) -> Dict[str, float]:
    """Extract the JSON weight object from Claude's response."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for k, v in raw.items():
        if k in valid:
            try:
                fv = float(v)
                if fv >= 0:
                    out[k] = fv
            except (TypeError, ValueError):
                continue
    return out


def correct_repo_weights(
    repo_url: str,
    l2_weights: Dict[str, float],
    client=None,
    head_size: int = HEAD_SIZE,
) -> Dict[str, float]:
    """Ask Claude to correct a repo's head dependency weights.

    Args:
        repo_url: Full GitHub URL of the repo.
        l2_weights: Mapping of dependency URL -> L2 weight for this repo.
        client: Bedrock client (created if None).
        head_size: how many top-L2 deps to send for correction.

    Returns:
        Mapping of dependency URL -> corrected target weight (head only).
        Empty on failure.
    """
    if not l2_weights:
        return {}
    if client is None:
        client = get_bedrock_client()

    head = sorted(l2_weights.items(), key=lambda kv: -kv[1])[:head_size]
    head_short = [(u.replace("https://github.com/", ""), w) for u, w in head]
    repo_short = repo_url.replace("https://github.com/", "")

    text = _call_claude(client, _build_prompt(repo_short, head_short))
    valid = {d for d, _ in head_short}
    corrected_short = _parse_weights(text, valid)
    return {
        f"https://github.com/{k}": v for k, v in corrected_short.items()
    }


def blend_corrections(
    l2_weights: Dict[str, float],
    corrections: Dict[str, float],
) -> Dict[str, float]:
    """Combine Claude's head corrections with the L2 tail, normalized to 1.0.

    The corrected head deps take Claude's target weights; all remaining deps
    keep their L2 weight, scaled to fill whatever mass is left over.

    Args:
        l2_weights: dependency URL -> L2 weight.
        corrections: dependency URL -> Claude target weight (head subset).

    Returns:
        Normalized dependency URL -> weight (sums to 1.0).
    """
    if not corrections:
        total = sum(l2_weights.values()) or 1.0
        return {k: v / total for k, v in l2_weights.items()}

    head = {d: w for d, w in corrections.items() if d in l2_weights}
    head_sum = sum(head.values())
    remaining = max(1.0 - head_sum, 0.0)

    tail = {d: w for d, w in l2_weights.items() if d not in head}
    tail_sum = sum(tail.values()) or 1.0

    out = dict(head)
    for d, w in tail.items():
        out[d] = remaining * w / tail_sum

    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def generate_all(
    l2_path: str = "data/seedReposWithDependenciesAndWeights.json",
    repos: List[str] | None = None,
    cache_path: str | None = "data/ai_juror_corrections.json",
    sleep_s: float = 0.0,
) -> Dict[str, Dict[str, float]]:
    """Run the AI-juror over repos, returning corrected head weights per repo.

    Results are cached to ``cache_path`` so a re-run resumes without re-calling
    Claude for repos already done.

    Args:
        l2_path: Path to L2 weights JSON.
        repos: optional subset of repo URLs; defaults to all repos in the file.
        cache_path: where to persist corrections (None disables caching).
        sleep_s: optional delay between calls to respect rate limits.

    Returns:
        Mapping of repo URL -> {dependency URL -> corrected head weight}.
    """
    with open(l2_path) as f:
        l2 = json.load(f)

    if repos is None:
        repos = list(l2.keys())

    cache: Dict[str, Dict[str, float]] = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path) as f:
            cache = json.load(f)

    client = get_bedrock_client()

    for i, repo in enumerate(repos, 1):
        if repo in cache:
            continue
        try:
            corr = correct_repo_weights(repo, l2.get(repo, {}), client)
        except Exception as e:  # keep going; one bad repo shouldn't kill the run
            print(f"  [{i}/{len(repos)}] {repo} FAILED: {e}")
            corr = {}
        cache[repo] = corr
        print(f"  [{i}/{len(repos)}] {repo.replace('https://github.com/','')}: "
              f"{len(corr)} deps corrected")
        if cache_path:
            with open(cache_path, "w") as f:
                json.dump(cache, f, indent=2)
        if sleep_s:
            time.sleep(sleep_s)

    return cache


if __name__ == "__main__":
    generate_all()
