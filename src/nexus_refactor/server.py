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

from nexus_refactor.resolve import resolve_drift

app = FastAPI(title="NexusRefactor webhook")

_SECRET = os.environ.get("NEXUS_WEBHOOK_SECRET", "")
_SPEC = os.environ.get("NEXUS_SPEC", "openapi.yaml")
_CODE_DIR = os.environ.get("NEXUS_CODE_DIR", "service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
    background.add_task(_run_job, repo)  # respond now; the agent runs after (becomes a queue in prod)
    return {"accepted": repo, "spec": _SPEC}


def _verify(body: bytes, signature: str) -> None:
    if not _SECRET:
        return  # dev mode: accept unsigned
    expected = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")


def _run_job(repo: str) -> None:
    """Clone the repo and run the agent. Runs in the background; a real deploy uses a queue+worker."""
    work = Path(tempfile.mkdtemp(prefix="nexus-job-"))
    try:
        subprocess.run(
            ["gh", "repo", "clone", repo, str(work / "repo")],
            check=True, capture_output=True, text=True,
        )
        result = resolve_drift(str(work / "repo"), spec=_SPEC, code_dir=_CODE_DIR)
        print(f"[nexus] {repo}: healed={result['healed']} pr={result['pr_url']}", flush=True)
    except Exception as exc:  # log and move on — a queue would retry / dead-letter
        print(f"[nexus] {repo}: job failed: {exc}", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
