#!/usr/bin/env python3
"""Check readiness for AI-juror pipeline execution.

Run this after AWS Bedrock access is approved to verify all components are working.

Usage:
    python check_readiness.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Tuple

import numpy as np


def check_files() -> Tuple[bool, str]:
    """Check that all required data files exist."""
    required_files = [
        "data/pairs_to_predict.csv",
        "data/seedReposWithDependenciesAndWeights.json",
        "data/L2PublicEval.csv",
        "data/seedReposWithDependencies.json",
        "data/unweighted_graph.csv",
    ]

    missing = [f for f in required_files if not os.path.exists(f)]
    if missing:
        return False, f"Missing files: {', '.join(missing)}"
    return True, "All data files present"


def check_imports() -> Tuple[bool, str]:
    """Check that all required Python packages are available."""
    required = ["pandas", "numpy", "networkx", "boto3"]
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, "All required packages installed"


def check_bedrock_credentials() -> Tuple[bool, str]:
    """Check that Bedrock API credentials are available and valid."""
    key_file = os.path.expanduser("~/.bedrock_key")

    if not os.path.exists(key_file):
        return False, "Bedrock key file not found (~/.bedrock_key)"

    try:
        import base64
        from src.ai_juror_generator import _load_bedrock_credentials

        key_id, secret = _load_bedrock_credentials()
        if not key_id or not secret:
            return False, "Credentials empty or invalid"
        return True, f"Credentials loaded: {key_id[:20]}..."

    except Exception as e:
        return False, f"Failed to load credentials: {e}"


def test_bedrock_connection() -> Tuple[bool, str]:
    """Test actual Bedrock API connection."""
    try:
        import boto3
        from src.ai_juror_generator import _load_bedrock_credentials

        key_id, secret = _load_bedrock_credentials()

        client = boto3.client(
            "bedrock-runtime",
            region_name="us-east-1",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
        )

        # Try a minimal invoke_model call
        response = client.invoke_model(
            modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
            body=json.dumps({
                "prompt": "Hello",
                "max_tokens": 10,
            }).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )

        result = response["body"].read()
        if result:
            return True, "✓ Bedrock API connection working"
        else:
            return False, "API returned empty response"

    except Exception as e:
        error_str = str(e)
        if "UnrecognizedClientException" in error_str or "invalid" in error_str.lower():
            return False, (
                "AWS Bedrock credentials still invalid. "
                "Has AWS approved the use case form? Check AWS console."
            )
        elif "ModelNotFoundException" in error_str:
            return False, "Model not available in region (try us-east-1)"
        else:
            return False, f"API connection failed: {e}"


def test_blend_math() -> Tuple[bool, str]:
    """Test the AI-juror blend math (Claude head corrections + L2 tail)."""
    try:
        from src.ai_juror_generator import blend_corrections

        l2 = {
            "https://github.com/x/big": 0.6,
            "https://github.com/x/mid": 0.3,
            "https://github.com/x/small": 0.1,
        }
        # Claude corrects the head: shrink "big", boost "mid".
        corrections = {
            "https://github.com/x/big": 0.4,
            "https://github.com/x/mid": 0.5,
        }
        weights = blend_corrections(l2, corrections)

        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            return False, f"Weights don't sum to 1.0 (got {total})"
        if weights["https://github.com/x/mid"] <= weights["https://github.com/x/big"]:
            return False, "Correction not applied (mid should exceed big)"

        return True, f"Blend math working ({len(weights)} deps normalized)"

    except Exception as e:
        return False, f"Blend math test failed: {e}"


def check_validation_data() -> Tuple[bool, str]:
    """Check that validation data has expected structure."""
    try:
        import pandas as pd

        eval_df = pd.read_csv("data/L2PublicEval.csv")

        required_cols = ["repo_url", "dep_url", "user_weight"]
        if not all(col in eval_df.columns for col in required_cols):
            return False, f"Missing columns in L2PublicEval: {required_cols}"

        # Check number of repos
        repos = eval_df["repo_url"].nunique()
        if repos < 2:
            return False, f"Expected multiple repos in L2PublicEval, got {repos}"

        # Check weights are reasonable
        if (eval_df["user_weight"] < 0).any() or (eval_df["user_weight"] > 1).any():
            return False, "Some weights are outside [0, 1]"

        total_rows = len(eval_df)
        return True, f"L2PublicEval: {repos} repos, {total_rows} pairs, weights in [0, 1]"

    except Exception as e:
        return False, f"Validation data check failed: {e}"


def main() -> None:
    """Run all readiness checks."""
    print("=" * 70)
    print("Level III AI-Juror Pipeline - Readiness Check")
    print("=" * 70)

    checks = [
        ("Data files", check_files),
        ("Python imports", check_imports),
        ("Bedrock credentials", check_bedrock_credentials),
        ("Validation data", check_validation_data),
        ("Blend math", test_blend_math),
        ("Bedrock API connection", test_bedrock_connection),  # This one takes longest
    ]

    results = []
    for name, check_fn in checks:
        print(f"\n[*] Checking {name}...")
        ok, msg = check_fn()
        results.append((name, ok, msg))
        status = "✓" if ok else "✗"
        print(f"  {status} {msg}")

    print("\n" + "=" * 70)

    ok_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)

    if ok_count == total:
        print(f"✓ ALL CHECKS PASSED ({ok_count}/{total})")
        print("\nReady to run: python run_ai_juror_pipeline.py")
        return

    failed = [name for name, ok, _ in results if not ok]
    print(f"✗ {total - ok_count} CHECK(S) FAILED:")
    for name in failed:
        print(f"  - {name}")

    # Special handling for Bedrock API check
    if "Bedrock API connection" in failed:
        print(
            "\nIMPORTANT: AWS Bedrock access is not yet approved."
            "\nWait for AWS email confirming use case form acceptance, then retry."
        )
        sys.exit(1)

    sys.exit(1)


if __name__ == "__main__":
    main()
