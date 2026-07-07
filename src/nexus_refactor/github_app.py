"""GitHub App identity — mint short-lived installation tokens (JWT → installation access token).

Instead of acting with a personal `GH_TOKEN`, the webhook path acts as the **App** (a scoped bot):
sign a JWT with the App's private key, exchange it for a per-installation access token scoped to the
installed repos, and use that for clone / push / PR. PRs then come from `nexusrefactor[bot]`, and the
token is least-privilege + expires in an hour.

Config: `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` (the .pem contents), set as Fly secrets in prod.
The App is created once and installed per account/repo — see the onboarding docs.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import jwt

from nexus_refactor.config import get_settings

_API = "https://api.github.com"
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _private_key() -> str:
    """The App's PEM private key — from GITHUB_APP_PRIVATE_KEY (contents, e.g. a Fly secret) or,
    for local dev, GITHUB_APP_PRIVATE_KEY_PATH (a path to the .pem)."""
    s = get_settings()
    if s.github_app_private_key:
        return s.github_app_private_key
    if s.github_app_private_key_path:
        return Path(s.github_app_private_key_path).read_text()
    raise RuntimeError("GitHub App private key not configured (GITHUB_APP_PRIVATE_KEY or _PATH)")


def _app_jwt() -> str:
    """A short-lived (<=10 min) JWT proving we are the App, signed with its private key (RS256).

    `iat` is backdated 60s to tolerate clock skew between us and GitHub (GitHub's own guidance).
    """
    s = get_settings()
    now = int(time.time())
    payload = {"iss": s.github_app_id, "iat": now - 60, "exp": now + 9 * 60}
    return jwt.encode(payload, _private_key(), algorithm="RS256")


def installation_token(installation_id: int) -> str:
    """Exchange the App JWT for a 1-hour access token scoped to that installation's repos."""
    resp = httpx.post(
        f"{_API}/app/installations/{installation_id}/access_tokens",
        headers={"Authorization": f"Bearer {_app_jwt()}", **_HEADERS},
        timeout=15,
    )
    resp.raise_for_status()
    return str(resp.json()["token"])


def installation_id_for_repo(full_name: str) -> int:
    """The installation id covering a repo (`owner/name`) — for paths without a webhook payload
    (the push webhook already carries `installation.id`; the CLI/resolve path can look it up here)."""
    owner, repo = full_name.split("/", 1)
    resp = httpx.get(
        f"{_API}/repos/{owner}/{repo}/installation",
        headers={"Authorization": f"Bearer {_app_jwt()}", **_HEADERS},
        timeout=15,
    )
    resp.raise_for_status()
    return int(resp.json()["id"])
