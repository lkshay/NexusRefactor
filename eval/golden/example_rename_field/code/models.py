"""GENERATED from the OpenAPI spec — do not hand-edit (regenerated on each spec change).

This file already reflects openapi_after.yaml (field is `username`). The hand-written code that
uses it has NOT caught up — that's the drift the agent must heal.

A dataclass (not a pydantic model) is used here deliberately: mypy reliably flags access to an
undeclared attribute on a dataclass instance, so the rename surfaces as a *static* error. (A
pydantic BaseModel defines __getattr__ -> Any, which makes mypy permit `user.user_name` and
silently weakens the verify signal — see docs/DECISIONS.md.)
"""

from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str
