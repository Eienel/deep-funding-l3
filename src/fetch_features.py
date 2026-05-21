"""Fetch GitHub features for each (dependency, repo) pair.

Reads ``data/pairs_to_predict.csv`` (columns ``dependency`` and ``repo``,
both full GitHub URLs), queries the GitHub REST API for repository metadata
and dependency-manifest information, and writes ``data/features.csv``.

The script is resilient: network errors are retried with exponential
backoff, the GitHub rate limit is respected proactively, and any pair that
fails completely is written out with all-zero features instead of aborting
the run.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Manifest files that, in a target repo's root, may declare dependencies.
MANIFEST_FILES: Tuple[str, ...] = (
    "package.json",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "setup.py",
    "pyproject.toml",
    "composer.json",
)

API_ROOT = "https://api.github.com"
DEFAULT_PAIRS_PATH = os.path.join("data", "pairs_to_predict.csv")
DEFAULT_OUTPUT_PATH = os.path.join("data", "features.csv")
LOG_PATH = os.path.join("logs", "errors.log")

OUTPUT_COLUMNS: Tuple[str, ...] = (
    "dependency",
    "repo",
    "stars",
    "forks",
    "dep_language",
    "repo_language",
    "days_since_push",
    "is_direct_dependency",
)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
RATE_LIMIT_FLOOR = 10


def _ensure_dirs() -> None:
    """Create the ``data`` and ``logs`` directories if they do not exist."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)


def _build_logger() -> logging.Logger:
    """Configure and return a logger that writes errors to ``logs/errors.log``."""
    logger = logging.getLogger("fetch_features")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Avoid duplicate handlers if the module is imported more than once.
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


def parse_owner_repo(url: str) -> Optional[Tuple[str, str]]:
    """Parse the ``owner`` and ``repo`` components from a GitHub URL.

    Handles trailing slashes, a ``.git`` suffix, ``https://`` URLs, and the
    ``git@github.com:owner/repo`` SSH form. Returns ``None`` when the URL is
    not a parseable GitHub repository reference.

    Args:
        url: A GitHub repository URL.

    Returns:
        A ``(owner, repo)`` tuple, or ``None`` if parsing fails.
    """
    if not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    cleaned = cleaned.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if "github.com" not in cleaned:
        return None
    path = cleaned.split("github.com", 1)[1]
    # Strip the protocol/host separators left over from https:// or git@...:
    path = path.lstrip(":/")
    segments = [seg for seg in path.split("/") if seg]
    if len(segments) < 2:
        return None
    return segments[0], segments[1]


def _sleep_for_rate_limit(response: requests.Response, logger: logging.Logger) -> None:
    """Sleep until the rate-limit reset if remaining requests are low.

    Args:
        response: A GitHub API response whose rate-limit headers are read.
        logger: Logger used to record the wait.
    """
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if remaining is None or reset is None:
        return
    try:
        remaining_int = int(remaining)
        reset_int = int(reset)
    except ValueError:
        return
    if remaining_int < RATE_LIMIT_FLOOR:
        wait_seconds = max(0, reset_int - int(time.time())) + 1
        logger.info(
            "Rate limit low (%s remaining); sleeping %ss until reset.",
            remaining_int,
            wait_seconds,
        )
        time.sleep(wait_seconds)


def github_get(
    session: requests.Session, url: str, logger: logging.Logger
) -> Optional[requests.Response]:
    """Perform a GET request with retries, backoff, and rate-limit handling.

    Retries up to :data:`MAX_RETRIES` times with exponential backoff on
    network errors and on ``429``/``403``/``500``/``502``/``503`` responses.
    After every response the rate-limit headers are inspected and the call
    sleeps until reset when the remaining budget is low.

    Args:
        session: A configured :class:`requests.Session`.
        url: The full URL to request.
        logger: Logger for error reporting.

    Returns:
        The successful :class:`requests.Response`, or ``None`` if all
        attempts fail.
    """
    backoff = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("Request error for %s (attempt %d): %s", url, attempt, exc)
            time.sleep(backoff)
            backoff *= 2
            continue

        # Proactively respect the rate limit before deciding what to do next.
        _sleep_for_rate_limit(response, logger)

        if response.status_code in (429, 403, 500, 502, 503):
            logger.error(
                "HTTP %d for %s (attempt %d).",
                response.status_code,
                url,
                attempt,
            )
            time.sleep(backoff)
            backoff *= 2
            continue

        return response

    logger.error("Giving up on %s after %d attempts.", url, MAX_RETRIES)
    return None


def _days_since(pushed_at: Optional[str]) -> int:
    """Return whole days between ``pushed_at`` and now (UTC).

    Args:
        pushed_at: An ISO-8601 timestamp such as ``2023-01-01T00:00:00Z``.

    Returns:
        The number of days since the push, or ``0`` if it cannot be parsed.
    """
    if not pushed_at:
        return 0
    try:
        pushed = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return 0
    delta = datetime.now(timezone.utc) - pushed
    return max(0, delta.days)


def fetch_repo_metadata(
    session: requests.Session,
    owner: str,
    repo: str,
    logger: logging.Logger,
    cache: Dict[Tuple[str, str], Optional[Dict[str, object]]],
) -> Optional[Dict[str, object]]:
    """Fetch and cache repository metadata from ``GET /repos/{owner}/{repo}``.

    Args:
        session: A configured :class:`requests.Session`.
        owner: Repository owner/organisation.
        repo: Repository name.
        logger: Logger for error reporting.
        cache: Mutable cache keyed by ``(owner, repo)``.

    Returns:
        A dict with ``stars``, ``forks``, ``language``, ``pushed_at`` and
        ``size`` keys, or ``None`` if the repository could not be fetched.
    """
    key = (owner, repo)
    if key in cache:
        return cache[key]

    url = f"{API_ROOT}/repos/{owner}/{repo}"
    response = github_get(session, url, logger)
    result: Optional[Dict[str, object]]
    if response is None or response.status_code != 200:
        status = "no response" if response is None else response.status_code
        logger.error("Metadata fetch failed for %s/%s (%s).", owner, repo, status)
        result = None
    else:
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Bad JSON for %s/%s metadata: %s", owner, repo, exc)
            data = {}
        result = {
            "stars": int(data.get("stargazers_count") or 0),
            "forks": int(data.get("forks_count") or 0),
            "language": data.get("language") or "",
            "pushed_at": data.get("pushed_at"),
            "size": int(data.get("size") or 0),
        }

    cache[key] = result
    return result


def fetch_repo_manifests(
    session: requests.Session,
    owner: str,
    repo: str,
    logger: logging.Logger,
    cache: Dict[Tuple[str, str], str],
) -> str:
    """Fetch and concatenate manifest file contents from a repo's root.

    Lists the root directory via ``GET /repos/{owner}/{repo}/contents/`` and,
    for each known manifest file present, downloads and base64-decodes its
    content. The combined, lower-cased text is cached and returned.

    Args:
        session: A configured :class:`requests.Session`.
        owner: Repository owner/organisation.
        repo: Repository name.
        logger: Logger for error reporting.
        cache: Mutable cache keyed by ``(owner, repo)``.

    Returns:
        The concatenated, lower-cased manifest text (empty string on failure).
    """
    key = (owner, repo)
    if key in cache:
        return cache[key]

    combined: List[str] = []
    listing = github_get(session, f"{API_ROOT}/repos/{owner}/{repo}/contents/", logger)
    if listing is None or listing.status_code != 200:
        status = "no response" if listing is None else listing.status_code
        logger.error("Contents listing failed for %s/%s (%s).", owner, repo, status)
        cache[key] = ""
        return ""

    try:
        items = listing.json()
    except ValueError as exc:
        logger.error("Bad JSON for %s/%s contents: %s", owner, repo, exc)
        items = []

    present = {
        item["name"]
        for item in items
        if isinstance(item, dict)
        and item.get("type") == "file"
        and "name" in item
    }

    for filename in MANIFEST_FILES:
        if filename not in present:
            continue
        file_resp = github_get(
            session, f"{API_ROOT}/repos/{owner}/{repo}/contents/{filename}", logger
        )
        if file_resp is None or file_resp.status_code != 200:
            continue
        try:
            payload = file_resp.json()
        except ValueError:
            continue
        if payload.get("encoding") == "base64":
            try:
                decoded = base64.b64decode(payload.get("content", "")).decode(
                    "utf-8", errors="ignore"
                )
                combined.append(decoded)
            except (ValueError, TypeError) as exc:
                logger.error("Decode failed for %s/%s/%s: %s", owner, repo, filename, exc)

    text = "\n".join(combined).lower()
    cache[key] = text
    return text


def _zero_row(dependency: str, repo: str) -> Dict[str, object]:
    """Return a feature row with all numeric/categorical features zeroed."""
    return {
        "dependency": dependency,
        "repo": repo,
        "stars": 0,
        "forks": 0,
        "dep_language": "",
        "repo_language": "",
        "days_since_push": 0,
        "is_direct_dependency": 0,
    }


def fetch_features(
    pairs_path: str = DEFAULT_PAIRS_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Run the full feature-fetching pipeline and write ``features.csv``.

    Args:
        pairs_path: Path to the input pairs CSV.
        output_path: Path where the feature CSV is written.

    Returns:
        The feature :class:`pandas.DataFrame` that was written to disk.
    """
    _ensure_dirs()
    logger = _build_logger()
    load_dotenv()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN not set; requests will be unauthenticated.")
        print("WARNING: GITHUB_TOKEN not set. API limits will be very low.")

    pairs = pd.read_csv(pairs_path)
    missing = {"dependency", "repo"} - set(pairs.columns)
    if missing:
        raise ValueError(f"{pairs_path} is missing required columns: {sorted(missing)}")

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "deep-funding-l3",
        }
    )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"

    meta_cache: Dict[Tuple[str, str], Optional[Dict[str, object]]] = {}
    manifest_cache: Dict[Tuple[str, str], str] = {}

    rows: List[Dict[str, object]] = []
    for record in tqdm(
        pairs.itertuples(index=False), total=len(pairs), desc="Fetching"
    ):
        dependency = str(getattr(record, "dependency"))
        repo = str(getattr(record, "repo"))
        try:
            row = _zero_row(dependency, repo)

            dep_parsed = parse_owner_repo(dependency)
            if dep_parsed is not None:
                dep_meta = fetch_repo_metadata(
                    session, dep_parsed[0], dep_parsed[1], logger, meta_cache
                )
                if dep_meta is not None:
                    row["stars"] = dep_meta["stars"]
                    row["forks"] = dep_meta["forks"]
                    row["dep_language"] = dep_meta["language"]
                    row["days_since_push"] = _days_since(dep_meta["pushed_at"])  # type: ignore[arg-type]
            else:
                logger.error("Could not parse dependency URL: %s", dependency)

            repo_parsed = parse_owner_repo(repo)
            if repo_parsed is not None:
                repo_meta = fetch_repo_metadata(
                    session, repo_parsed[0], repo_parsed[1], logger, meta_cache
                )
                if repo_meta is not None:
                    row["repo_language"] = repo_meta["language"]

                manifest_text = fetch_repo_manifests(
                    session, repo_parsed[0], repo_parsed[1], logger, manifest_cache
                )
                if dep_parsed is not None and manifest_text:
                    dep_name = dep_parsed[1].lower()
                    if dep_name and dep_name in manifest_text:
                        row["is_direct_dependency"] = 1
            else:
                logger.error("Could not parse repo URL: %s", repo)

            rows.append(row)
        except Exception as exc:  # noqa: BLE001 - want a robust per-pair fallback
            logger.error("Unhandled failure for (%s, %s): %s", dependency, repo, exc)
            rows.append(_zero_row(dependency, repo))

    features = pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS))
    features.to_csv(output_path, index=False)
    print(f"Wrote {len(features)} feature rows to {output_path}")
    return features


if __name__ == "__main__":
    fetch_features()
