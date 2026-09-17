"""Deontic admission rules L2, L3, L5 (docs/01-state-model.md §3).

    GRANT / OBLIGE  : label == PRINCIPAL, or label == HARNESS when it narrows an existing
                      grant that it supersedes (rule L5)
    DENY / REVOKE   : label >= HARNESS
    anything below  : stored as a SEM claim with no effect on A(t); counted as laundering

A DERIVED GRANT marked as a proposal becomes a SEM claim with `proposal=True`; a later
PRINCIPAL confirmation creates the real GRANT citing the proposal in `related` only.
"""

from __future__ import annotations

from pydantic import BaseModel

from decaymem.core.entries import (
    Activation,
    DeonticPayload,
    Entry,
    SemanticPayload,
    Tick,
)
from decaymem.core.labels import Label
from decaymem.core.store import Store
from decaymem.core.types import NARROWING_KINDS, DeonKind, EntryType


class AdmissionResult(BaseModel):
    entry: Entry
    accepted_as_deontic: bool
    converted_to_claim: bool
    reason: str


def _narrows_existing_grant(store: Store, entry: Entry, t: Tick) -> tuple[bool, str]:
    """Rule L5: a HARNESS-labelled GRANT is admissible iff it supersedes one existing
    GRANT whose scope subsumes the new scope and whose expiry is not extended."""
    p = entry.deon
    parents = [
        store.get(sid)
        for sid in entry.provenance.sources
        if sid in store
        and store.get(sid).type == EntryType.DEON
        and store.get(sid).deon.kind == DeonKind.GRANT
    ]
    if len(parents) != 1:
        return False, "harness grant must supersede exactly one existing grant"
    old = parents[0]
    if not old.active_at(t) and old.temporal.t_valid_to != t:
        return False, "parent grant is not in force"
    if old.deon.scope is None or p.scope is None or not old.deon.scope.subsumes(p.scope):
        return False, "new scope is not subsumed by parent scope"
    if old.deon.expiry is not None and (p.expiry is None or p.expiry > old.deon.expiry):
        return False, "new grant extends expiry"
    return True, "narrowing"


def _to_claim(entry: Entry, reason: str, proposal: bool) -> Entry:
    p = entry.deon
    text = f"claim: {p.kind} {p.scope.model_dump() if p.scope else p.target} by {p.principal}"
    return Entry(
        id=entry.id,
        type=EntryType.SEM,
        content=SemanticPayload(text=text, deontic_claim=p, proposal=proposal),
        provenance=entry.provenance,
        label=entry.label,
        temporal=entry.temporal,
        activation=Activation(),
    )


def admit(store: Store, entry: Entry, t: Tick, *, proposal: bool = False) -> AdmissionResult:
    """Apply the deontic admission rule to a candidate entry and add the result to the
    store. Non-DEON entries are added unchanged."""
    if entry.type != EntryType.DEON:
        store.add(entry)
        return AdmissionResult(
            entry=entry, accepted_as_deontic=False, converted_to_claim=False, reason="not deontic"
        )

    p: DeonticPayload = entry.deon
    if proposal:
        claim = _to_claim(entry, "proposal", proposal=True)
        store.add(claim)
        return AdmissionResult(
            entry=claim,
            accepted_as_deontic=False,
            converted_to_claim=True,
            reason="proposal pending confirmation",
        )

    if p.kind in NARROWING_KINDS:
        if entry.label >= Label.HARNESS:
            store.add(entry)
            return AdmissionResult(
                entry=entry,
                accepted_as_deontic=True,
                converted_to_claim=False,
                reason="narrowing by trusted writer",
            )
        reason = f"{p.kind} requires label >= HARNESS, got {entry.label.name}"
    else:  # GRANT, OBLIGE
        if entry.label == Label.PRINCIPAL:
            store.add(entry)
            return AdmissionResult(
                entry=entry, accepted_as_deontic=True, converted_to_claim=False, reason="principal"
            )
        if entry.label == Label.HARNESS and p.kind == DeonKind.GRANT:
            ok, why = _narrows_existing_grant(store, entry, t)
            if ok:
                store.add(entry)
                return AdmissionResult(
                    entry=entry, accepted_as_deontic=True, converted_to_claim=False, reason=why
                )
            reason = f"harness grant rejected: {why}"
        else:
            reason = f"{p.kind} requires PRINCIPAL, got {entry.label.name}"

    claim = _to_claim(entry, reason, proposal=False)
    store.add(claim)
    return AdmissionResult(
        entry=claim, accepted_as_deontic=False, converted_to_claim=True, reason=reason
    )
