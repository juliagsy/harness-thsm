"""Ground-truth events and their admission as episodic entries."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from decaymem.core.entries import Entry, EpisodicPayload, Provenance, Temporal, Tick
from decaymem.core.labels import Label
from decaymem.core.types import EntryType


class EventKind(StrEnum):
    # conversation / trajectory
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    # deontic (principal channel)
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_DENY = "permission_deny"
    PERMISSION_REVOKE = "permission_revoke"
    PERMISSION_NARROW = "permission_narrow"
    PERMISSION_CONFIRM = "permission_confirm"  # confirms a model proposal (rule L3)
    OBLIGATION = "obligation"
    # world / scenario ground truth
    FACT_SET = "fact_set"
    FACT_UPDATE = "fact_update"
    TASK = "task"
    ENV_DRIFT = "env_drift"
    # harness
    COMPACTION_TRIGGER = "compaction_trigger"
    SESSION_BOUNDARY = "session_boundary"
    MODE_CHANGE = "mode_change"
    PROBE = "probe"


DEFAULT_EVENT_LABELS: dict[EventKind, Label] = {
    EventKind.USER_MESSAGE: Label.PRINCIPAL,
    EventKind.ASSISTANT_MESSAGE: Label.DERIVED,
    EventKind.TOOL_CALL: Label.DERIVED,
    EventKind.TOOL_RESULT: Label.UNTRUSTED,
    EventKind.PERMISSION_GRANT: Label.PRINCIPAL,
    EventKind.PERMISSION_DENY: Label.PRINCIPAL,
    EventKind.PERMISSION_REVOKE: Label.PRINCIPAL,
    EventKind.PERMISSION_NARROW: Label.PRINCIPAL,
    EventKind.PERMISSION_CONFIRM: Label.PRINCIPAL,
    EventKind.OBLIGATION: Label.PRINCIPAL,
    EventKind.FACT_SET: Label.PRINCIPAL,
    EventKind.FACT_UPDATE: Label.PRINCIPAL,
    EventKind.TASK: Label.PRINCIPAL,
    EventKind.ENV_DRIFT: Label.UNTRUSTED,
    EventKind.COMPACTION_TRIGGER: Label.HARNESS,
    EventKind.SESSION_BOUNDARY: Label.HARNESS,
    EventKind.MODE_CHANGE: Label.HARNESS,
    EventKind.PROBE: Label.PRINCIPAL,
}

WIDENING_EVENT_KINDS = frozenset({EventKind.PERMISSION_GRANT, EventKind.PERMISSION_CONFIRM})


class Event(BaseModel):
    id: str
    t: Tick
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    principal: str | None = None
    label: Label | None = None  # None = default for the kind; generator may override

    @property
    def effective_label(self) -> Label:
        return self.label if self.label is not None else DEFAULT_EVENT_LABELS[self.kind]


def event_to_entry(event: Event) -> Entry:
    """Admit an event as an immutable EPI entry (operator `admit`, EPI column)."""
    return Entry(
        id=f"epi:{event.id}",
        type=EntryType.EPI,
        content=EpisodicPayload(event_kind=event.kind.value, content=dict(event.payload)),
        provenance=Provenance(writer="harness", writer_label=Label.HARNESS),
        label=event.effective_label,
        temporal=Temporal(t_created=event.t, t_valid_from=event.t),
    )
