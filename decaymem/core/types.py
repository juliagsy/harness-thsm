"""Enumerations shared across the state model."""

from enum import StrEnum


class EntryType(StrEnum):
    """The four harness state types (docs/01-state-model.md §1)."""

    EPI = "EPI"  # episodic: raw trajectory events, append-only
    SEM = "SEM"  # semantic: derived facts, decayable
    PROC = "PROC"  # procedural: skills, decayable, capability-stripped
    DEON = "DEON"  # deontic: grants, denies, revocations, obligations


DECAYABLE_TYPES = frozenset({EntryType.SEM, EntryType.PROC})


class DeonKind(StrEnum):
    GRANT = "GRANT"  # widening: requires PRINCIPAL (or HARNESS if it narrows an existing grant)
    DENY = "DENY"  # narrowing: requires >= HARNESS; dominates GRANT on overlap
    REVOKE = "REVOKE"  # narrowing: references a GRANT entry id
    OBLIGE = "OBLIGE"  # must-do; requires PRINCIPAL


NARROWING_KINDS = frozenset({DeonKind.DENY, DeonKind.REVOKE})


class Operator(StrEnum):
    """Operators from the type-rule table (docs/01-state-model.md §2)."""

    ADMIT = "admit"
    DECAY = "decay"
    CONSOLIDATE = "consolidate"
    COMPACT = "compact"
    RETRIEVE = "retrieve"
    SUPERSEDE = "supersede"
    AUTHORIZE = "authorize"


# Operators that must never change deontic state (invariant I3).
LOSSY_OPERATORS = frozenset({Operator.DECAY, Operator.CONSOLIDATE, Operator.COMPACT})
