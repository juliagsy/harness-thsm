"""Effective authority A(t), computed deterministically from DEON entries.

    A(t) = actions matched by an active GRANT at t
           minus actions matched by an active DENY at t
           minus actions matched by a GRANT that has been REVOKEd or has expired

Labels are ignored here on purpose: baselines that let an LLM write DEON entries get
the authority those entries imply, and invariant I2 is what reports the laundering.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from decaymem.core.entries import Entry, Tick
from decaymem.core.scope import Action
from decaymem.core.store import Store
from decaymem.core.types import DeonKind, EntryType


class Decision(BaseModel):
    allowed: bool
    reason: str
    matched_grant: str | None = None
    matched_deny: str | None = None


class Authority(BaseModel):
    """A(t) as the sets of grants and denies that are in force at t."""

    t: Tick
    grants: list[Entry]
    denies: list[Entry]
    obligations: list[Entry]

    def allows(self, action: Action) -> Decision:
        for d in self.denies:
            if d.deon.scope is not None and d.deon.scope.matches(action):
                return Decision(allowed=False, reason="denied", matched_deny=d.id)
        for g in self.grants:
            if g.deon.scope is not None and g.deon.scope.matches(action):
                return Decision(allowed=True, reason="granted", matched_grant=g.id)
        return Decision(allowed=False, reason="no grant")

    def grant_ids(self) -> set[str]:
        return {g.id for g in self.grants}

    def deny_ids(self) -> set[str]:
        return {d.id for d in self.denies}


def _deon_entries(entries: Iterable[Entry]) -> list[Entry]:
    return [e for e in entries if e.type == EntryType.DEON]


def _in_force(e: Entry, t: Tick) -> bool:
    if not e.active_at(t):
        return False
    p = e.deon
    if p.expiry is not None and t >= p.expiry:
        return False
    return True


def effective_authority(store_or_entries: Store | Iterable[Entry], t: Tick) -> Authority:
    entries = (
        list(store_or_entries)
        if not isinstance(store_or_entries, Store)
        else list(store_or_entries)
    )
    deon = _deon_entries(entries)
    revoked: set[str] = {
        e.deon.target
        for e in deon
        if e.deon.kind == DeonKind.REVOKE and _in_force(e, t) and e.deon.target is not None
    }
    grants = [
        e
        for e in deon
        if e.deon.kind == DeonKind.GRANT
        and _in_force(e, t)
        and e.id not in revoked
        and (e.deon.uses_remaining is None or e.deon.uses_remaining > 0)
    ]
    denies = [e for e in deon if e.deon.kind == DeonKind.DENY and _in_force(e, t)]
    obligations = [e for e in deon if e.deon.kind == DeonKind.OBLIGE and _in_force(e, t)]
    return Authority(t=t, grants=grants, denies=denies, obligations=obligations)


def authority_subset(
    narrower: Authority, broader: Authority, universe: Iterable[Action] | None = None
) -> bool:
    """Is A_narrower a subset of A_broader?

    With a finite `universe` of actions the check is exact over that universe. Without
    one it is symbolic and conservative: every grant in force in `narrower` must be the
    same entry as, or scope-subsumed by, a grant in force in `broader`, and every deny in
    force in `broader` must still be in force (or be subsumed by a deny) in `narrower`.
    """
    if universe is not None:
        return all(broader.allows(a).allowed for a in universe if narrower.allows(a).allowed)
    broad_grants = broader.grants
    for g in narrower.grants:
        if not any(
            b.id == g.id
            or (
                b.deon.scope is not None
                and g.deon.scope is not None
                and b.deon.scope.subsumes(g.deon.scope)
            )
            for b in broad_grants
        ):
            return False
    for d in broader.denies:
        if not any(
            n.id == d.id
            or (
                n.deon.scope is not None
                and d.deon.scope is not None
                and n.deon.scope.subsumes(d.deon.scope)
            )
            for n in narrower.denies
        ):
            return False
    return True
