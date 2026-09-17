"""Type-blind baselines: one note type, labels ignored, lossy eviction and consolidation,
the model decides authority. The decay policy is pluggable (none, ebbinghaus, actr,
memory_worth) so the same store yields the H1 sweep."""

from __future__ import annotations

from decaymem.core import Action, Entry, EntryType, Label, SemanticPayload, Store
from decaymem.core.entries import make_entry
from decaymem.embed import HashBowEmbedder
from decaymem.interfaces import ModelProvider
from decaymem.memory.base import MemoryBackend
from decaymem.scenarios import templates as T


class FlatVectorBackend(MemoryBackend):
    name = "flat_vector"

    def __init__(
        self,
        provider: ModelProvider | None = None,
        decay: str = "none",
        aggressiveness: float = 0.5,
        cap: int = 60,
        consolidation: str = "on_cap",
        summarise_batch: int = 10,
        **decay_params,
    ) -> None:
        super().__init__(provider, decay=decay, aggressiveness=aggressiveness, **decay_params)
        self.cap = cap
        self.consolidation = consolidation
        self.batch = summarise_batch
        self.embedder = HashBowEmbedder()
        self._vecs: dict[str, list[float]] = {}
        self.unsupported = {"authorize"}
        self._n = 0
        if decay != "none":
            self.name = f"flat_{self.policy.name}"

    def describe(self) -> dict:
        return {**super().describe(), "cap": self.cap, "consolidation": self.consolidation}

    def _admit_candidate(self, store: Store, entry: Entry, t: int) -> Entry:
        # type-blind: everything becomes a SEM note; labels are kept but never consulted
        if entry.type != EntryType.SEM:
            self._n += 1
            entry = make_entry(
                f"note:{t}:{self._n}",
                SemanticPayload(text=self.entry_text(entry)),
                entry.label,
                t,
                sources=entry.provenance.sources,
                writer=entry.provenance.writer,
                writer_label=entry.provenance.writer_label,
            )
        store.add(entry)
        self.policy.on_admit(entry, t)
        self._vecs[entry.id] = self.embedder.embed(entry.content.text)
        return entry

    def _notes(self) -> list[Entry]:
        return [e for e in self.store.by_type(EntryType.SEM) if e.active_at(self.store.clock)]

    def _decay(self, store: Store, t: int) -> None:
        thr = self.policy.evict_below
        for e in self._notes():
            v = self.policy.update(e, t)
            if thr > 0 and v < thr:
                store.remove(e.id)  # lossy: the baseline forgets outright
                self._vecs.pop(e.id, None)

    def _score(self, e: Entry, qv: list[float], t: int) -> float:
        return self.embedder.cosine(qv, self._vecs[e.id]) * (0.5 + 0.5 * e.activation.value)

    def retrieve(self, query: str, t: int, k: int, action: Action | None = None) -> list[Entry]:
        qv = self.embedder.embed(query)
        ranked = sorted(self._notes(), key=lambda e: self._score(e, qv, t), reverse=True)[:k]
        for e in ranked:
            self.policy.on_access(e, t)
        return ranked

    def _consolidate(self, store: Store, t: int) -> None:
        if self.consolidation == "never":
            return
        notes = self._notes()
        if len(notes) <= self.cap:
            return
        victims = sorted(notes, key=lambda e: e.activation.value)[: self.batch]
        text = "\n".join(self.entry_text(v) for v in victims)
        summary = self._summarise(text)
        label = Label(min(int(v.label) for v in victims))
        self._n += 1
        merged = make_entry(
            f"sum:{t}:{self._n}",
            SemanticPayload(text=summary),
            label,
            t,
            sources=[v.id for v in victims],
            writer="llm_summariser",
            writer_label=Label.DERIVED,
        )
        for v in victims:
            store.remove(v.id)
            self._vecs.pop(v.id, None)
        store.add(merged)
        self.policy.on_admit(merged, t)
        self._vecs[merged.id] = self.embedder.embed(summary)

    def _summarise(self, text: str) -> str:
        if self.provider is None:
            return "Summary: " + " | ".join(text.splitlines()[:6])
        reply = self.provider.complete(
            system=f"{T.SUMMARY_MARKER}\nCondense these memory notes into one short paragraph, "
            "keeping anything the user allowed, forbade, or changed.",
            messages=[{"role": "user", "content": text}],
            tools=[],
        )
        return reply.text.strip() or "Summary: (empty)"


class FlatEbbinghausBackend(FlatVectorBackend):
    """Kept for config compatibility: flat_vector with the ebbinghaus policy."""

    def __init__(
        self,
        provider: ModelProvider | None = None,
        cap: int = 60,
        aggressiveness: float = 0.5,
        tau: float | None = None,
        **kw,
    ) -> None:
        params = {"tau": tau} if tau is not None else {}
        super().__init__(
            provider, decay="ebbinghaus", aggressiveness=aggressiveness, cap=cap, **params, **kw
        )
        self.name = "flat_ebbinghaus"
