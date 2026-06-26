"""A command denylist — minimal safety for the code-executing path. Implemented (starter).

This is a *denylist* (block known-bad), which is weaker than an *allowlist* (permit only
known-good). For verify you actually only need a tiny allowlist — mypy, pytest, python. Once
you're comfortable, flip this to an allowlist; it's strictly safer. For now this catches the
obvious foot-guns so a hallucinated `rm -rf` or an exfiltration `curl` doesn't run.

Extend it as you learn the threat model (Phase 2 writes it up in SECURITY.md).
"""

from __future__ import annotations


class SandboxViolation(RuntimeError):
    """Raised when a command trips the denylist."""


# Binaries that enable privilege escalation, external network, or remote shells.
DENIED_BINARIES: frozenset[str] = frozenset(
    {"sudo", "su", "doas", "curl", "wget", "ssh", "scp", "sftp", "nc", "ncat", "telnet"}
)

# Substrings that indicate destructive or escalating intent, checked against the joined command.
DENIED_SUBSTRINGS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf ~",
    ":(){",  # fork bomb
    "mkfs",
    "dd if=",
    "chmod 777",
    "/etc/passwd",
    "/etc/shadow",
    "> /dev/sd",
)


def check_command(argv: list[str]) -> None:
    """Raise SandboxViolation if `argv` is disallowed. No-op if it's fine.

    Args:
        argv: the command as a list, e.g. ["pytest", "-q"].
    """
    if not argv:
        raise SandboxViolation("empty command")

    binary = argv[0].rsplit("/", 1)[-1]  # strip any path prefix
    if binary in DENIED_BINARIES:
        raise SandboxViolation(f"denied binary: {binary!r}")

    joined = " ".join(argv)
    for bad in DENIED_SUBSTRINGS:
        if bad in joined:
            raise SandboxViolation(f"denied pattern in command: {bad!r}")
