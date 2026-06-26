"""Run the verify commands (mypy, pytest) off the host's trust boundary.

The agent edits code an LLM wrote and then executes it. That is inherently risky, so even the
minimal Phase 1 version refuses obviously dangerous commands (denylist) and bounds runtime
(timeout). Phase 1d/2 graduates this to real container isolation. See runner.py.
"""
