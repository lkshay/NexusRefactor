# NexusRefactor webhook service — the deployable image.
FROM python:3.12-slim

# System deps the agent shells out to: git (branch/commit), gh (clone + open PR),
# oasdiff (the OpenAPI structural differ used by `parse`).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && curl -fsSL https://raw.githubusercontent.com/oasdiff/oasdiff/main/install.sh | sh -s -- -b /usr/local/bin \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"

# Install the package + the verify toolchain. mypy/pytest are dev deps, but the agent's `verify`
# node shells out to them at RUNTIME — without them in the image the heal dies with FileNotFoundError
# (caught in a LangSmith trace: parse→search→refactor ✓, verify ✗). They are runtime deps here.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install . mypy pytest

# QDRANT_URL comes from the runtime env — compose sets `qdrant:6333`, Fly sets the cloud URL as a
# secret. Left unset here so it isn't baked to a compose-only hostname (config default: localhost).
EXPOSE 8000
# Embedding models (fastembed) download on first job, not at build time.
CMD ["uvicorn", "nexus_refactor.server:app", "--host", "0.0.0.0", "--port", "8000"]
