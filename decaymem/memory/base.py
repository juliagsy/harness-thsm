"""MemoryBackend base: wraps a core Store and exposes the operator table (docs/01 §2)
so every backend, including baselines, is checked by the same invariant checker."""

from __future__ import annotations

from abc import ABC, abstractmethod

from decaymem.core import Action, Decision, Entry, EntryType, Event, Operator, Store, event_to_entry


class MemoryBackend(ABC):
    name: str = "base"

    def __init__(self, provider=None) -> None:
        self.provider = provider
        self.store = Store()
        self.unsupported: set[str] = set()

    # --- operators ---------------------------------------------------------------------
    def admit_event(self, event: Event) -> Entry:
        entry = event_to_entry(event)
        self.store.apply(Operator.ADMIT, lambda s: s.add(entry), t=event.t, events=[event])
        return entry

    def write(self, entries: list[Entry], t: int) -> list[Entry]:
        """Admit writer-produced candidates. Baselines may coerce types."""
        out: list[Entry] = []

        def _do(s: Store):
            for e in entries:
                out.append(self._admit_candidate(s, e, t))

        self.store.apply(Operator.ADMIT, _do, t=t)
        return out

    @abstractmethod
    def _admit_candidate(self, store: Store, entry: Entry, t: int) -> Entry: ...

    def decay(self, t: int) -> None:
        self.store.apply(Operator.DECAY, lambda s: self._decay(s, t), t=t)

    def _decay(self, store: Store, t: int) -> None:  # default: no decay
        return None

    def consolidate(self, t: int) -> None:
        self.store.apply(Operator.CONSOLIDATE, lambda s: self._consolidate(s, t), t=t)

    def _consolidate(self, store: Store, t: int) -> None:
        return None

    @abstractmethod
    def retrieve(self, query: str, t: int, k: int, action: Action | None = None) -> list[Entry]: ...

    def authorize(self, action: Action, t: int) -> Decision | None:
        """None means 'the model decides' (baselines)."""
        return None

    # --- rendering ------------------------------------------------------------------------
    def render(self, entries: list[Entry]) -> str:
        lines = []
        for e in entries:
            lines.append(f"- {self.entry_text(e)}")
        return "\n".join(lines) if lines else "(no notes)"

    @staticmethod
    def entry_text(e: Entry) -> str:
        c = e.content
        if e.type == EntryType.SEM:
            return c.text
        if e.type == EntryType.PROC:
            return f"skill {c.name}: " + "; ".join(c.steps)
        if e.type == EntryType.DEON:
            return f"{c.kind} {c.scope.model_dump(exclude_none=True) if c.scope else c.target}"
        return f"{c.event_kind}: {c.content}"

    def recent_epi(self, since_t: int) -> list[Entry]:
        return [e for e in self.store.by_type(EntryType.EPI) if e.temporal.t_created >= since_t]

    def stats(self) -> dict:
        return {
            "entries": len(self.store),
            "by_type": {t.value: len(self.store.by_type(t)) for t in EntryType},
        }
