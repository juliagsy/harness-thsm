"""Core schemas and rules of the Typed Harness State Model (docs/01-state-model.md)."""

from decaymem.core.admission import AdmissionResult, admit
from decaymem.core.authority import Authority, Decision, authority_subset, effective_authority
from decaymem.core.entries import (
    Activation,
    DeonticPayload,
    Entry,
    EpisodicPayload,
    ProceduralPayload,
    Provenance,
    SemanticPayload,
    Temporal,
)
from decaymem.core.events import Event, EventKind, event_to_entry
from decaymem.core.invariants import (
    Violation,
    check_all,
    check_state,
    check_trace,
    check_transition,
)
from decaymem.core.labels import Label, derive_label, meet
from decaymem.core.scope import Action, Scope
from decaymem.core.store import Snapshot, Store, ToolCallRecord
from decaymem.core.types import DeonKind, EntryType, Operator

__all__ = [
    "Action",
    "Activation",
    "AdmissionResult",
    "Authority",
    "Decision",
    "DeonKind",
    "DeonticPayload",
    "Entry",
    "EntryType",
    "EpisodicPayload",
    "Event",
    "EventKind",
    "Label",
    "Operator",
    "ProceduralPayload",
    "Provenance",
    "Scope",
    "SemanticPayload",
    "Snapshot",
    "Store",
    "Temporal",
    "ToolCallRecord",
    "Violation",
    "admit",
    "authority_subset",
    "check_all",
    "check_state",
    "check_trace",
    "check_transition",
    "derive_label",
    "effective_authority",
    "event_to_entry",
    "meet",
]
