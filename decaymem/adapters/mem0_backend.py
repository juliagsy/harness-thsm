"""Mem0 as a MemoryBackend.

Mem0 (mem0ai) extracts and stores memories from conversation text with its own LLM and
vector store, deduplicates and updates them, and returns them by semantic search. Mapped
onto our operator table:

    admit_event   : EPI kept in our Store for the invariant checker; nothing sent to Mem0
    write         : the writer's candidates are rendered to text and `add`ed as user
                    memories (Mem0 runs its own extraction on top)
    decay         : unsupported (Mem0 has no decay); recorded in `unsupported`
    consolidate   : Mem0 does this itself on every add (its UPDATE/DELETE decisions);
                    we do not call anything, recorded as `builtin`
    retrieve      : `search(query, limit=k)`; results mirrored into our Store as SEM
                    entries labelled DERIVED so CLAIMS/INV are computable
    authorize     : unsupported (the model decides), like the type-blind baselines

The client is injected so tests run against `FakeMem0Client`; `RealMem0Client` lazily
imports `mem0` and needs an LLM (any OpenAI-compatible endpoint) and an embedder that
Mem0 supports. See configs/mem0_live.yaml for the shape.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from decaymem.core import Action, Entry, EntryType, Label, SemanticPayload, Store
from decaymem.core.entries import make_entry
from decaymem.memory.base import MemoryBackend


class Mem0Like(Protocol):
    def add(self, text: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> Any: ...
    def search(self, query: str, *, user_id: str, limit: int) -> list[dict[str, Any]]: ...
    def get_all(self, *, user_id: str) -> list[dict[str, Any]]: ...


class FakeMem0Client:
    """Deterministic stand-in: stores the text verbatim, ranks by token overlap. Lets the
    adapter be exercised end to end without the real dependency."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def add(self, text: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> Any:
        mid = hashlib.sha1(f"{user_id}:{text}".encode()).hexdigest()[:12]
        self.items[mid] = {
            "id": mid,
            "memory": text,
            "user_id": user_id,
            "metadata": metadata or {},
        }
        return {"results": [{"id": mid, "memory": text, "event": "ADD"}]}

    def search(self, query: str, *, user_id: str, limit: int) -> list[dict[str, Any]]:
        q = set(query.lower().split())
        scored = []
        for it in self.items.values():
            if it["user_id"] != user_id:
                continue
            toks = set(it["memory"].lower().split())
            scored.append((len(q & toks) / (len(toks) ** 0.5 + 1), it))
        scored.sort(key=lambda x: -x[0])
        return [dict(it, score=s) for s, it in scored[:limit]]

    def get_all(self, *, user_id: str) -> list[dict[str, Any]]:
        return [it for it in self.items.values() if it["user_id"] == user_id]


class RealMem0Client:
    """Thin wrapper over mem0.Memory. Config example (OpenRouter LLM, HF embedder):

    {"llm": {"provider": "openai", "config": {"model": "openai/gpt-4o-mini",
              "openai_base_url": "https://openrouter.ai/api/v1", "api_key": "<key>"}},
     "embedder": {"provider": "huggingface",
                  "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}},
     "vector_store": {"provider": "qdrant", "config": {"path": "data/mem0", "on_disk": True}}}
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        from mem0 import Memory  # optional dependency: uv sync --extra mem0

        self.mem = Memory.from_config(config) if config else Memory()

    def add(self, text: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> Any:
        return self.mem.add(text, user_id=user_id, metadata=metadata or {})

    def search(self, query: str, *, user_id: str, limit: int) -> list[dict[str, Any]]:
        res = self.mem.search(query, user_id=user_id, limit=limit)
        return res.get("results", res) if isinstance(res, dict) else res

    def get_all(self, *, user_id: str) -> list[dict[str, Any]]:
        res = self.mem.get_all(user_id=user_id)
        return res.get("results", res) if isinstance(res, dict) else res


class Mem0Backend(MemoryBackend):
    name = "mem0"

    def __init__(
        self,
        provider=None,
        client: Mem0Like | None = None,
        user_id: str = "julia",
        mem0_config: dict[str, Any] | None = None,
        **_,
    ) -> None:
        super().__init__(provider, decay="none")
        self.client: Mem0Like = client or RealMem0Client(mem0_config)
        self.user_id = user_id
        self.unsupported = {"authorize", "decay"}
        self.builtin = {"consolidate"}
        self._mirrored: dict[str, str] = {}  # mem0 id -> our entry id
        self._n = 0

    def describe(self) -> dict:
        return {
            **super().describe(),
            "external": "mem0",
            "unsupported": sorted(self.unsupported),
            "builtin": sorted(self.builtin),
        }

    def _admit_candidate(self, store: Store, entry: Entry, t: int) -> Entry:
        text = self.entry_text(entry)
        self.client.add(
            text,
            user_id=self.user_id,
            metadata={"t": t, "label": entry.label.name, "type": entry.type.value},
        )
        # keep the candidate in our store too (labelled as written) so CLAIMS is computable
        if entry.type != EntryType.SEM:
            self._n += 1
            entry = make_entry(
                f"note:{t}:{self._n}",
                SemanticPayload(text=text),
                entry.label,
                t,
                sources=entry.provenance.sources,
                writer=entry.provenance.writer,
                writer_label=entry.provenance.writer_label,
            )
        store.add(entry)
        return entry

    def _decay(self, store: Store, t: int) -> None:
        return None  # unsupported

    def _consolidate(self, store: Store, t: int) -> None:
        return None  # Mem0 consolidates internally on add

    def retrieve(self, query: str, t: int, k: int, action: Action | None = None) -> list[Entry]:
        hits = self.client.search(query, user_id=self.user_id, limit=k)
        out: list[Entry] = []
        for h in hits:
            mid = str(h.get("id"))
            text = str(h.get("memory", ""))
            if not text:
                continue
            eid = self._mirrored.get(mid)
            if eid is None or eid not in self.store:
                self._n += 1
                eid = f"mem0:{mid}:{self._n}"
                e = make_entry(
                    eid,
                    SemanticPayload(text=text),
                    Label.DERIVED,
                    t,
                    writer="mem0",
                    writer_label=Label.DERIVED,
                )
                self.store.add(e)
                self._mirrored[mid] = eid
            out.append(self.store.get(eid))
        return out
