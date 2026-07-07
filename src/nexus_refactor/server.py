"""FastAPI webhook service — the deployment surface that turns the agent into a service.

GitHub fires a webhook when the spec file changes; we verify the HMAC signature and enqueue a
BACKGROUND job (a webhook must answer in seconds; the agent takes minutes). The job clones the
repo and runs `resolve_drift`, which opens a PR.

In production the BackgroundTask becomes a real queue + worker, and `gh` auth becomes a GitHub
App — but the payload (`resolve_drift`) is unchanged. That's the point: the script was already
the worker.

Run:  LLM_PROVIDER=ollama uv run uvicorn nexus_refactor.server:app --port 8000
Then point a GitHub push webhook at  http://<public-url>/webhook  (e.g. via a cloudflared tunnel).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from nexus_refactor.config import get_settings, setup_tracing
from nexus_refactor.github_app import installation_token
from nexus_refactor.metrics_store import summarize
from nexus_refactor.resolve import resolve_drift

app = FastAPI(title="NexusRefactor webhook")

# Turn on LangSmith tracing for webhook-triggered heals too. In the Fly container the LANGSMITH_*
# vars arrive as real env (fly.toml [env] + a secret); this also promotes them from .env for a
# local `uvicorn` run, and is a no-op when tracing is disabled.
setup_tracing(get_settings())

_SECRET = os.environ.get("NEXUS_WEBHOOK_SECRET", "")
_SPEC = os.environ.get("NEXUS_SPEC", "openapi.yaml")
_CODE_DIR = os.environ.get("NEXUS_CODE_DIR", "service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    """Online-eval summary over all recorded runs (heal rate, latency, cost, PRs)."""
    return summarize()


@app.post("/webhook")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
) -> dict:
    body = await request.body()
    _verify(body, x_hub_signature_256)

    if x_github_event != "push":
        return {"ignored": f"event '{x_github_event}'"}

    payload = await request.json()
    touched = {
        f
        for commit in payload.get("commits", [])
        for f in commit.get("modified", []) + commit.get("added", [])
    }
    if _SPEC not in touched:
        return {"ignored": f"{_SPEC} unchanged in this push"}

    repo = payload["repository"]["full_name"]
    installation_id = payload.get("installation", {}).get("id")
    background.add_task(_run_job, repo, installation_id)  # respond now; the agent runs after
    return {"accepted": repo, "spec": _SPEC}


def _verify(body: bytes, signature: str) -> None:
    if not _SECRET:
        return  # dev mode: accept unsigned
    expected = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")


def _run_job(repo: str, installation_id: int | None = None) -> None:
    """Clone the repo and run the agent as the App. Runs in the background (a real deploy uses a
    queue+worker). With an installation_id (App-delivered webhook) we mint a scoped token and act as
    nexusrefactor[bot]; without one we fall back to the ambient gh credentials."""
    work = Path(tempfile.mkdtemp(prefix="nexus-job-"))
    try:
        token = installation_token(installation_id) if installation_id else None
        if token:  # act as the bot — token embedded in origin, so the later push uses it too
            clone = [
                "git",
                "clone",
                f"https://x-access-token:{token}@github.com/{repo}.git",
                str(work / "repo"),
            ]
        else:  # fallback: ambient gh credentials (handles private repos)
            clone = ["gh", "repo", "clone", repo, str(work / "repo")]
        try:
            subprocess.run(clone, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"clone failed (exit {e.returncode})"
            ) from None  # sanitized: no token in logs
        result = resolve_drift(str(work / "repo"), spec=_SPEC, code_dir=_CODE_DIR, token=token)
        print(f"[nexus] {repo}: healed={result['healed']} pr={result['pr_url']}", flush=True)
    except Exception as exc:  # log and move on — a queue would retry / dead-letter
        print(f"[nexus] {repo}: job failed: {exc}", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
