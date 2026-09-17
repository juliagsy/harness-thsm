"""MemoryBackend base: wraps a core Store and exposes the operator table (docs/01 §2)
so every backend, including baselines, is checked by the same invariant checker."""

from __future__ import annotations

from abc import ABC, abstractmethod

from decaymem.core import Action, Decision, Entry, EntryType, Event, Operator, Store, event_to_entry
from decaymem.policies.decay import DecayPolicy, make_decay


class MemoryBackend(ABC):
    name: str = "base"

    def __init__(
        self,
        provider=None,
        decay: str | DecayPolicy = "none",
        aggressiveness: float = 0.5,
        **decay_params,
    ) -> None:
        self.provider = provider
        self.store = Store()
        self.unsupported: set[str] = set()
        self.policy: DecayPolicy = (
            decay
            if isinstance(decay, DecayPolicy)
            else make_decay(decay, aggressiveness=aggressiveness, **decay_params)
        )

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "decay": self.policy.name,
            "aggressiveness": self.policy.aggressiveness,
            "evict_below": round(self.policy.evict_below, 3),
        }

    # --- operators ---------------------------------------------------------------------
    def admit_event(self, event: Event) -> Entry:
        entry = event_to_entry(event)
        self.store.apply(
            Operator.ADMIT, lambda s: self._admit_event(s, entry, event), t=event.t, events=[event]
        )
        return entry

    def _admit_event(self, store: Store, epi: Entry, event: Event) -> None:
        store.add(epi)

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

    def _decay(self, store: Store, t: int) -> None:
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

    def consume(self, action: Action, t: int) -> None:
        """Operator `authorize` side effect: an executed action uses up a `max_uses` grant."""
        return None

    def feedback(self, entry_ids: list[str], success: bool) -> None:
        """Outcome signal for the entries retrieved during a probe (Memory Worth etc.)."""
        for eid in entry_ids:
            if eid in self.store:
                e = self.store.get(eid)
                if e.type in (EntryType.SEM, EntryType.PROC):
                    self.policy.on_outcome(e, success)

    # --- rendering ------------------------------------------------------------------------
    def render(self, entries: list[Entry]) -> str:
        lines = [f"- {self.entry_text(e)}" for e in entries]
        return "\n".join(lines) if lines else "(no notes)"

    @staticmethod
    def entry_text(e: Entry) -> str:
        from decaymem.scenarios.templates import scope_str

        c = e.content
        if e.type == EntryType.SEM:
            return c.text
        if e.type == EntryType.PROC:
            return f"skill '{c.name}': run " + "; then ".join(f"`{s}`" for s in c.steps)
        if e.type == EntryType.DEON:
            what = scope_str(c.scope) if c.scope is not None else f"grant {c.target}"
            return f"{c.kind} {what}"
        return f"{c.event_kind}: {c.content}"

    def recent_epi(self, since_t: int) -> list[Entry]:
        return [e for e in self.store.by_type(EntryType.EPI) if e.temporal.t_created >= since_t]

    def stats(self) -> dict:
        return {
            "entries": len(self.store),
            "by_type": {t.value: len(self.store.by_type(t)) for t in EntryType},
            "active_by_type": {
                t.value: sum(1 for e in self.store.by_type(t) if e.active_at(self.store.clock))
                for t in EntryType
            },
        }
