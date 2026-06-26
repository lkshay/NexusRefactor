"""Execute verify commands and capture exit code + output.

Two modes:
  - isolated=False (DEFAULT, DEV ONLY): runs as a subprocess on the host. This is NOT isolation
    — it just lets you build the verify node today. The denylist + timeout are the only guards.
  - isolated=True (Phase 1d/2): run inside an ephemeral container. STUB for now; sketch below.

`RunResult.exit_code` is the objective signal the whole agent is steered by.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from nexus_refactor.sandbox.denylist import check_command


@dataclass
class RunResult:
    exit_code: int
    output: str  # merged stdout + stderr


def _text(stream: str | bytes | None) -> str:
    """subprocess streams are str under text=True, but TimeoutExpired types them loosely."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode(errors="replace")
    return stream


def run_in_sandbox(
    argv: list[str],
    cwd: str | Path,
    *,
    timeout: int = 120,
    isolated: bool = False,
) -> RunResult:
    """Run `argv` in `cwd`, returning exit code + combined output.

    Raises SandboxViolation (from the denylist) before anything executes.
    """
    check_command(argv)

    if isolated:
        # TODO(you, Phase 1d): real isolation. Sketch:
        #   - mount `cwd` read-write into a minimal python image (or read-only + a tmp overlay)
        #   - --network none, drop capabilities, non-root user, memory/CPU limits, --rm
        #   - `docker run --rm --network none -v {cwd}:/work -w /work <img> {argv}`
        #   - capture exit code + logs the same way. Keep the same RunResult contract.
        # Bonus beyond safety: a fresh isolated dir also makes tools behave predictably — mypy
        # stops mapping a file to two module names, pytest rootdir is unambiguous, no config bleed.
        raise NotImplementedError("Container isolation is Phase 1d. Use isolated=False for now.")

    # DEV fallback: host subprocess. Replace with the container path before trusting this on
    # anything you didn't write yourself.
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return RunResult(proc.returncode, _text(proc.stdout) + _text(proc.stderr))
    except subprocess.TimeoutExpired as exc:
        out = _text(exc.stdout) + _text(exc.stderr)
        return RunResult(124, f"TIMEOUT after {timeout}s\n{out}")
