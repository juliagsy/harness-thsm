"""Entry schema: e = <id, type, content, provenance, label, temporal, activation>."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from decaymem.core.labels import Label
from decaymem.core.scope import Scope
from decaymem.core.types import DECAYABLE_TYPES, DeonKind, EntryType

Tick = int  # logical time: event index


class Provenance(BaseModel):
    """Where an entry came from.

    `sources` are integrity-bearing parents (entry ids): rule L1 and invariant I4 apply
    over them. `related` are informational references that do not carry integrity, e.g.
    a PRINCIPAL grant pointing at the DERIVED proposal it confirms (rule L3).
    """

    sources: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    writer: str = "harness"
    writer_label: Label = Label.HARNESS


class Temporal(BaseModel):
    """Bi-temporal record: supersede and invalidate, never silently delete."""

    t_created: Tick
    t_valid_from: Tick
    t_valid_to: Tick | None = None  # set on supersession (exclusive)
    t_expired: Tick | None = None  # set when the harness invalidates the entry (exclusive)

    def active_at(self, t: Tick) -> bool:
        if t < self.t_valid_from:
            return False
        if self.t_valid_to is not None and t >= self.t_valid_to:
            return False
        if self.t_expired is not None and t >= self.t_expired:
            return False
        return True


class Activation(BaseModel):
    """Decay state; defined only for SEM and PROC."""

    value: float = 1.0
    last_access: Tick | None = None
    access_count: int = 0
    successes: int = 0
    failures: int = 0
    access_times: list[Tick] = Field(default_factory=list)  # for ACT-R base-level activation


class EpisodicPayload(BaseModel):
    type: Literal["EPI"] = "EPI"
    event_kind: str
    content: dict[str, Any] = Field(default_factory=dict)


class DeonticPayload(BaseModel):
    type: Literal["DEON"] = "DEON"
    kind: DeonKind
    scope: Scope | None = None  # required for GRANT, DENY, OBLIGE
    principal: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    expiry: Tick | None = None  # principal-set; exclusive
    target: str | None = None  # REVOKE: id of the GRANT being revoked
    uses_remaining: int | None = None  # mirrors scope.max_uses; decremented by authorize()

    @model_validator(mode="after")
    def _check_shape(self) -> DeonticPayload:
        if self.kind == DeonKind.REVOKE:
            if not self.target:
                raise ValueError("REVOKE requires target grant id")
        elif self.scope is None:
            raise ValueError(f"{self.kind} requires a scope")
        if self.uses_remaining is None and self.scope is not None:
            self.uses_remaining = self.scope.max_uses
        return self


class SemanticPayload(BaseModel):
    type: Literal["SEM"] = "SEM"
    text: str
    key: str | None = None
    value: str | None = None
    # Rule L2: a deontic-looking entry written below the required label is stored as a
    # claim with no effect on authority. Rule L3: proposals are claims flagged as such.
    deontic_claim: DeonticPayload | None = None
    proposal: bool = False


class ProceduralPayload(BaseModel):
    type: Literal["PROC"] = "PROC"
    name: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    gates: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    version: int = 1


Payload = EpisodicPayload | SemanticPayload | ProceduralPayload | DeonticPayload


class Entry(BaseModel):
    id: str
    type: EntryType
    content: Payload = Field(discriminator="type")
    provenance: Provenance = Field(default_factory=Provenance)
    label: Label
    temporal: Temporal
    activation: Activation | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Entry:
        if self.content.type != self.type.value:
            raise ValueError(f"entry type {self.type} does not match payload {self.content.type}")
        if self.type in DECAYABLE_TYPES:
            if self.activation is None:
                self.activation = Activation()
        elif self.activation is not None:
            raise ValueError(f"{self.type} entries carry no activation")
        return self

    def active_at(self, t: Tick) -> bool:
        return self.temporal.active_at(t)

    @property
    def deon(self) -> DeonticPayload:
        assert isinstance(self.content, DeonticPayload)
        return self.content


def make_entry(
    id: str,
    content: Payload,
    label: Label,
    t: Tick,
    *,
    sources: list[str] | None = None,
    related: list[str] | None = None,
    writer: str = "harness",
    writer_label: Label = Label.HARNESS,
    valid_from: Tick | None = None,
) -> Entry:
    """Convenience constructor used by tests and the harness code."""
    return Entry(
        id=id,
        type=EntryType(content.type),
        content=content,
        provenance=Provenance(
            sources=sources or [], related=related or [], writer=writer, writer_label=writer_label
        ),
        label=label,
        temporal=Temporal(t_created=t, t_valid_from=t if valid_from is None else valid_from),
    )
