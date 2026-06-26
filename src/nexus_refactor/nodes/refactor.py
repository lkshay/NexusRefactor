"""refactor: turn the candidate sites + schema delta (+ the verify error log on retries) into an
applied patch, using the LLM.

Output format: the model returns SEARCH/REPLACE blocks — reliable and minimal, unlike unified
diffs which LLMs reliably get wrong. We parse them, apply by exact string replacement on the
working copy, and compute the unified diff ourselves (difflib) for state/eval.

Self-heal: on retries we feed back the previous mypy/pytest failure, so the model sees the
current (partially-patched) code AND what's still broken. Always increments `iteration`.
"""

from __future__ import annotations

import difflib
import re
import textwrap
from collections.abc import Iterable
from pathlib import Path

from nexus_refactor.llm.router import choose_provider
from nexus_refactor.schema.delta import SchemaDelta
from nexus_refactor.state import RefactorState

_SYSTEM = """You are a precise refactoring agent. An upstream API schema changed and downstream \
code still references the OLD interface, breaking the build. Make the SMALLEST change that fixes \
it — do not touch unrelated code.

Reply ONLY with SEARCH/REPLACE blocks, one per file you change, formatted EXACTLY like this:

client.py
<<<<<<< SEARCH
    return user.user_name
=======
    return user.username
>>>>>>> REPLACE

The first line is the file's REAL path (the name shown after `---` in the files above), never a \
placeholder. The SEARCH text must match the file's current code. No prose, no markdown fences."""

# One SEARCH/REPLACE block; the path is the line just above the SEARCH marker.
_BLOCK = re.compile(
    r"(?P<path>\S[^\n]*)\n<<<<<<< SEARCH\n(?P<find>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


def refactor_node(state: RefactorState) -> dict:
    iteration = state.get("iteration", 0) + 1
    repo = Path(state["target_repo"])

    files = _read_candidate_files(state, repo)
    if not files:
        return {
            "current_patch": "",
            "iteration": iteration,
            "history": [f"refactor: iteration {iteration}, no candidate files to edit"],
        }

    prompt = _build_prompt(
        state.get("schema_diff"), files, state.get("compiler_log"), state.get("test_log")
    )
    completion = choose_provider("refactor").complete(_SYSTEM, prompt, max_tokens=2048).text
    edits = _parse_blocks(completion)
    applied = _apply_edits(edits, repo)
    patch = _compute_patch(state, repo, files.keys())

    return {
        "current_patch": patch,
        "iteration": iteration,
        "history": [
            f"refactor: iteration {iteration}, parsed {len(edits)} edit(s), applied {applied}"
        ],
    }


def _read_candidate_files(state: RefactorState, repo: Path) -> dict[str, str]:
    """Current content of each unique candidate file, read from the working copy."""
    files: dict[str, str] = {}
    for site in state.get("candidate_sites", []):
        rel = site["path"]
        if rel not in files and (repo / rel).exists():
            files[rel] = (repo / rel).read_text()
    return files


def _build_prompt(
    delta: SchemaDelta | None,
    files: dict[str, str],
    compiler_log: str | None,
    test_log: str | None,
) -> str:
    lines = ["The upstream API schema changed:"]
    for change in delta.changes if delta else []:
        extra = f" (was {change.before!r} -> {change.after!r})" if change.before or change.after else ""
        lines.append(f"  - {change.kind.value} at {change.location}{extra}")

    lines.append("\nDownstream files that may still use the OLD interface:")
    for path, content in files.items():
        lines.append(f"\n--- {path} ---\n{content}")

    if compiler_log or test_log:
        lines.append("\nYour previous patch did NOT fix the build. Fix these errors:")
        if compiler_log:
            lines.append(f"\n[mypy]\n{compiler_log}")
        if test_log:
            lines.append(f"\n[pytest]\n{test_log}")

    lines.append("\nReturn SEARCH/REPLACE blocks for the minimal fix.")
    return "\n".join(lines)


def _parse_blocks(text: str) -> list[tuple[str, str, str]]:
    """Extract (path, find, replace) from SEARCH/REPLACE blocks in the model output."""
    edits: list[tuple[str, str, str]] = []
    for m in _BLOCK.finditer(text):
        path = m.group("path").strip().strip("`").strip()
        edits.append((path, m.group("find"), m.group("replace")))
    return edits


def _apply_edits(edits: list[tuple[str, str, str]], repo: Path) -> int:
    """Apply each edit. Tries the named file first, then falls back to any repo file whose code
    the SEARCH text matches — the model sometimes emits a wrong or placeholder path."""
    applied = 0
    repo_files = sorted(repo.rglob("*.py"))
    for rel, find, replace in edits:
        if not find:
            continue
        named = repo / rel
        for f in [named, *(p for p in repo_files if p != named)]:
            if not f.exists():
                continue
            new_content = _apply_one(f.read_text(), find, replace)
            if new_content is not None and new_content != f.read_text():
                f.write_text(new_content)
                applied += 1
                break
    return applied


def _apply_one(content: str, find: str, replace: str) -> str | None:
    """Replace `find` with `replace`. Exact match first, then a whitespace-tolerant line match —
    LLMs reproduce indentation/trailing whitespace imperfectly, so exact-only silently no-ops.
    Returns the new content, or None if `find` can't be located.
    """
    if find in content:
        return content.replace(find, replace, 1)

    # Tolerant: match find's lines against content's lines, comparing each line stripped.
    key = [ln.strip() for ln in find.strip("\n").splitlines()]
    if not key:
        return None
    c_lines = content.splitlines()
    for i in range(len(c_lines) - len(key) + 1):
        if [c_lines[i + j].strip() for j in range(len(key))] == key:
            # re-indent the replace block to the matched region's base indentation
            base = c_lines[i][: len(c_lines[i]) - len(c_lines[i].lstrip())]
            dedented = textwrap.dedent(replace.strip("\n")).splitlines()
            new_lines = [base + ln if ln.strip() else "" for ln in dedented]
            out = c_lines[:i] + new_lines + c_lines[i + len(key) :]
            return "\n".join(out) + ("\n" if content.endswith("\n") else "")
    return None


def _compute_patch(state: RefactorState, working: Path, paths: Iterable[str]) -> str:
    """Unified diff of the working copy vs the original fixture — the cumulative patch so far."""
    scenario_dir = state.get("scenario_dir")
    if not scenario_dir:
        return ""
    original = Path(scenario_dir) / "code"
    chunks: list[str] = []
    for rel in sorted(paths):
        old = _read_or_empty(original / rel)
        new = _read_or_empty(working / rel)
        if old != new:
            chunks.append(
                "".join(
                    difflib.unified_diff(
                        old.splitlines(keepends=True),
                        new.splitlines(keepends=True),
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                    )
                )
            )
    return "".join(chunks)


def _read_or_empty(p: Path) -> str:
    return p.read_text() if p.exists() else ""
