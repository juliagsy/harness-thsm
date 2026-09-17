"""Integrity label lattice (docs/01-state-model.md §3).

Biba-style: information may flow down (a derived entry is at most as trusted as its
least trusted source and its writer), never up.
"""

from collections.abc import Iterable
from enum import IntEnum


class Label(IntEnum):
    UNTRUSTED = 0  # tool results, web content, file contents, other agents
    DERIVED = 1  # any LLM output: summaries, extracted facts, skills, proposals
    HARNESS = 2  # deterministic harness code: timestamps, expiry, rule-based narrowing
    PRINCIPAL = 3  # the user/operator via an authenticated channel

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name


def meet(labels: Iterable[Label]) -> Label:
    """Greatest lower bound. Empty input is the top element (no sources = no taint)."""
    labels = list(labels)
    if not labels:
        return Label.PRINCIPAL
    return Label(min(int(x) for x in labels))


def derive_label(writer: Label, sources: Iterable[Label]) -> Label:
    """Rule L1: label of a written entry = min(writer, min over sources)."""
    return meet([writer, *sources])
