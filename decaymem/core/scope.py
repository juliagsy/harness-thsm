"""Scope predicates over actions (docs/01-state-model.md §1, DEON payload).

A Scope matches an Action by tool name, glob patterns over named arguments, and a glob
over an optional resource (typically a path). `subsumes` is a conservative test that
one scope is at least as broad as another; it is used to validate HARNESS-labelled
narrowing (rule L5) and for the symbolic monotonicity check (invariant I1).
"""

from __future__ import annotations

from fnmatch import fnmatchcase

from pydantic import BaseModel, Field

GLOB_CHARS = set("*?[")


def _is_literal(pattern: str) -> bool:
    return not (GLOB_CHARS & set(pattern))


class Action(BaseModel, frozen=True):
    tool: str
    args: dict[str, str] = Field(default_factory=dict)
    resource: str | None = None


class Scope(BaseModel, frozen=True):
    tool: str = "*"  # exact tool name, or "*" for any tool
    args: dict[str, str] = Field(default_factory=dict)  # arg name -> glob; all must match
    resource: str | None = None  # glob over Action.resource; None = any
    max_uses: int | None = None  # None = unlimited

    def matches(self, action: Action) -> bool:
        if self.tool != "*" and self.tool != action.tool:
            return False
        if action.resource is not None and not _is_literal(action.resource):
            return False  # a glob is not a concrete resource
        for key, pattern in self.args.items():
            if key not in action.args or not fnmatchcase(action.args[key], pattern):
                return False
        if self.resource is not None:
            if action.resource is None or not fnmatchcase(action.resource, self.resource):
                return False
        return True

    def subsumes(self, other: Scope) -> bool:
        """True if every action matched by `other` is matched by `self` (conservative).

        Sound but incomplete: glob-vs-glob containment is only recognised when the
        patterns are identical or the narrower one is a literal.
        """
        if self.tool != "*" and self.tool != other.tool:
            return False
        for key, pattern in self.args.items():
            if key not in other.args:
                return False
            if not _pattern_contains(pattern, other.args[key]):
                return False
        if self.resource is not None:
            if other.resource is None or not _pattern_contains(self.resource, other.resource):
                return False
        if self.max_uses is not None:
            if other.max_uses is None or other.max_uses > self.max_uses:
                return False
        return True


def _pattern_contains(broad: str, narrow: str) -> bool:
    if broad == narrow:
        return True
    if _is_literal(narrow):
        return fnmatchcase(narrow, broad)
    return False
