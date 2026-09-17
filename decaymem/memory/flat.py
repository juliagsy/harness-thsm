"""Type-blind baselines.

flat_vector      : every note is SEM text, top-k cosine retrieval, no decay.
flat_ebbinghaus  : MemoryBank-style. activation = exp(-(t - last_access) / (tau * strength)),
                   strength grows on access; lowest-activation notes are summarised into one
                   note (LLM) and evicted when the store exceeds `cap`.
"""

from __future__ import annotations

import math

from decaymem.core import Action, Entry, EntryType, Label, SemanticPayload, Store
from decaymem.core.entries import Activation, make_entry
from decaymem.embed import HashBowEmbedder
from decaymem.interfaces import ModelProvider
from decaymem.memory.base import MemoryBackend
from decaymem.scenarios import templates as T


class FlatVectorBackend(MemoryBackend):
    name = "flat_vector"

    def __init__(self, provider: ModelProvider | None = None, cap: int = 10_000, **_) -> None:
        super().__init__(provider)
        self.cap = cap
        self.embedder = HashBowEmbedder()
        self._vecs: dict[str, list[float]] = {}
        self.unsupported = {"authorize", "consolidate", "decay"}
        self._n = 0

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
        self._vecs[entry.id] = self.embedder.embed(entry.content.text)
        return entry

    def _notes(self) -> list[Entry]:
        return [e for e in self.store.by_type(EntryType.SEM) if e.active_at(self.store.clock)]

    def _score(self, e: Entry, qv: list[float], t: int) -> float:
        return self.embedder.cosine(qv, self._vecs[e.id])

    def retrieve(self, query: str, t: int, k: int, action: Action | None = None) -> list[Entry]:
        qv = self.embedder.embed(query)
        ranked = sorted(self._notes(), key=lambda e: self._score(e, qv, t), reverse=True)[:k]
        for e in ranked:
            self._on_access(e, t)
        return ranked

    def _on_access(self, e: Entry, t: int) -> None:
        a = e.activation or Activation()
        a.access_count += 1
        a.last_access = t
        a.access_times.append(t)
        e.activation = a


class FlatEbbinghausBackend(FlatVectorBackend):
    name = "flat_ebbinghaus"

    def __init__(
        self,
        provider: ModelProvider | None = None,
        cap: int = 60,
        tau: float = 40.0,
        reinforce: float = 1.5,
        summarise_batch: int = 10,
        **_,
    ) -> None:
        super().__init__(provider=provider, cap=cap)
        self.tau = tau
        self.reinforce = reinforce
        self.batch = summarise_batch
        self.unsupported = {"authorize"}
        self._strength: dict[str, float] = {}

    def _admit_candidate(self, store: Store, entry: Entry, t: int) -> Entry:
        e = super()._admit_candidate(store, entry, t)
        self._strength[e.id] = 1.0
        e.activation.last_access = t
        e.activation.value = 1.0
        return e

    def _on_access(self, e: Entry, t: int) -> None:
        super()._on_access(e, t)
        self._strength[e.id] = self._strength.get(e.id, 1.0) * self.reinforce
        e.activation.value = 1.0

    def _decay(self, store: Store, t: int) -> None:
        for e in self._notes():
            a = e.activation
            last = a.last_access if a.last_access is not None else e.temporal.t_created
            a.value = math.exp(-(t - last) / (self.tau * self._strength.get(e.id, 1.0)))

    def _score(self, e: Entry, qv: list[float], t: int) -> float:
        return self.embedder.cosine(qv, self._vecs[e.id]) * (0.5 + 0.5 * e.activation.value)

    def _consolidate(self, store: Store, t: int) -> None:
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
            store.remove(v.id)  # lossy: the baseline forgets the originals
            self._vecs.pop(v.id, None)
            self._strength.pop(v.id, None)
        store.add(merged)
        self._vecs[merged.id] = self.embedder.embed(summary)
        self._strength[merged.id] = 1.0
        merged.activation.last_access = t

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
