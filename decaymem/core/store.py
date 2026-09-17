"""In-memory entry store with snapshots and an operator log.

Snapshots are deliberately lean: they hold full dumps only for EPI and DEON entries (the
types the transition invariants I1, I3 and I6 reason about) plus the id set. EPI dumps are
cached because EPI entries are immutable by invariant; pass `strict_epi=True` to re-dump
them on every snapshot so that in-place tampering is caught (used by the test suite).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

from pydantic import BaseModel, Field

from decaymem.core.entries import Entry, Tick
from decaymem.core.events import Event
from decaymem.core.types import EntryType, Operator

SNAPSHOT_TYPES = (EntryType.EPI, EntryType.DEON)


class Snapshot(BaseModel):
    """Frozen view of a store: EPI and DEON dumps by id, plus all entry ids."""

    t: Tick
    entries: dict[str, dict[str, Any]]
    all_ids: set[str] = Field(default_factory=set)

    def ids(self) -> set[str]:
        return set(self.all_ids or self.entries)

    def of_type(self, type_: EntryType) -> dict[str, dict[str, Any]]:
        return {k: v for k, v in self.entries.items() if v["type"] == type_.value}

    def entry(self, id: str) -> Entry:
        return Entry.model_validate(self.entries[id])

    def to_store(self) -> Store:
        s = Store()
        for d in self.entries.values():
            s.add(Entry.model_validate(d))
        s.clock = self.t
        return s


class ToolCallRecord(BaseModel):
    """One proposed tool call, for the I5 trace check."""

    call_id: str
    tool: str
    args: dict[str, str] = Field(default_factory=dict)
    resource: str | None = None
    origin_proc_id: str | None = None  # PROC entry whose step produced this call, if any
    authorization_id: str | None = None  # id of the authorize() decision; None = bypassed
    executed: bool = False


class OperatorRecord(BaseModel):
    operator: Operator
    t: Tick
    before: Snapshot
    after: Snapshot
    events: list[Event] = Field(default_factory=list)


class Store:
    def __init__(self, strict_epi: bool = False) -> None:
        self._entries: dict[str, Entry] = {}
        self._epi_dumps: dict[str, dict[str, Any]] = {}
        self.strict_epi = strict_epi
        self.clock: Tick = 0
        self.log: list[OperatorRecord] = []

    # --- basic access -------------------------------------------------------------
    def add(self, entry: Entry) -> Entry:
        if entry.id in self._entries:
            raise KeyError(f"duplicate entry id {entry.id}")
        self._entries[entry.id] = entry
        if entry.type == EntryType.EPI:
            self._epi_dumps[entry.id] = entry.model_dump(mode="json")
        return entry

    def get(self, id: str) -> Entry:
        return self._entries[id]

    def __contains__(self, id: str) -> bool:
        return id in self._entries

    def __iter__(self) -> Iterator[Entry]:
        return iter(list(self._entries.values()))

    def __len__(self) -> int:
        return len(self._entries)

    def by_type(self, type_: EntryType) -> list[Entry]:
        return [e for e in self._entries.values() if e.type == type_]

    def active(self, t: Tick | None = None) -> list[Entry]:
        t = self.clock if t is None else t
        return [e for e in self._entries.values() if e.active_at(t)]

    def remove(self, id: str) -> Entry:
        """Physically drop an entry. Baselines use this for eviction; THSM never calls it
        on DEON or EPI entries (the invariant checker will report if it does)."""
        self._epi_dumps.pop(id, None)
        return self._entries.pop(id)

    def snapshot(self) -> Snapshot:
        dumps: dict[str, dict[str, Any]] = {}
        for k, v in self._entries.items():
            if v.type == EntryType.DEON:
                dumps[k] = v.model_dump(mode="json")
            elif v.type == EntryType.EPI:
                dumps[k] = v.model_dump(mode="json") if self.strict_epi else self._epi_dumps[k]
        return Snapshot(t=self.clock, entries=dumps, all_ids=set(self._entries))

    # --- operators -----------------------------------------------------------------
    def supersede(self, old_id: str, new: Entry, t: Tick) -> Entry:
        """Bi-temporal supersession: close the old entry's validity, add the new one."""
        old = self._entries[old_id]
        if old.type == EntryType.EPI:
            raise ValueError("EPI entries are immutable (I6)")
        old.temporal.t_valid_to = t
        if old_id not in new.provenance.sources and old_id not in new.provenance.related:
            new.provenance.sources.append(old_id)
        return self.add(new)

    def apply(
        self,
        operator: Operator,
        fn: Callable[[Store], Any],
        *,
        t: Tick | None = None,
        events: Iterable[Event] = (),
    ) -> Any:
        """Run `fn(store)` as a named operator, recording before/after snapshots."""
        if t is not None:
            self.clock = t
        before = self.snapshot()
        result = fn(self)
        after = self.snapshot()
        self.log.append(
            OperatorRecord(
                operator=operator, t=self.clock, before=before, after=after, events=list(events)
            )
        )
        return result
