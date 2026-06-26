"""verify: run the build gate and capture the objective signal.

This is the ground truth the whole agent is steered by.

In Python there is no separate "compile" step, so our build gate is:
  1. mypy  on target_repo  -> the static analog of compiler errors. Schema drift shows up
                              here as attribute/type errors (e.g. `resp.user_name` after the
                              field was renamed to `username`).
  2. pytest on target_repo -> behavioral verification of the localized tests.

"build_clean" is True ONLY if BOTH exit 0. Capture stdout/stderr for each — on failure the
logs get fed back into `refactor` on the next loop. That feedback is the self-heal.

Runs via src/nexus_refactor/sandbox/runner.py (don't exec untrusted/LLM-touched code on the
host). Dev mode uses a host subprocess; graduate to container isolation (run_in_sandbox with
isolated=True) before trusting it on code you didn't write.
"""

from __future__ import annotations

from nexus_refactor.sandbox.runner import run_in_sandbox
from nexus_refactor.state import RefactorState


def verify_node(state: RefactorState) -> dict:
    # In an ISOLATED copy (the container) plain `mypy .` works. In-place (dev mode), mypy maps a
    # file to two module names ("Source file found twice") because the dir is nested in this
    # project — hence --explicit-package-bases. pytest is fine in-place (the scenario's
    # conftest.py anchors its rootdir).
    mypy = run_in_sandbox(["mypy", "--explicit-package-bases", "."], cwd=state["target_repo"])
    test = run_in_sandbox(["pytest", "-q"], cwd=state["target_repo"])
    clean = mypy.exit_code == 0 and test.exit_code == 0
    return {
        "build_clean": clean,
        "compiler_log": mypy.output,
        "test_log": test.output,
        "history": [f"verify: build_clean={clean} (mypy={mypy.exit_code}, pytest={test.exit_code})"],
    }
