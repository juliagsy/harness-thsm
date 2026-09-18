"""Response cache keyed by (provider, model, system, messages, tools)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from decaymem.interfaces import ModelProvider, ModelReply, ToolSpec


class CachedProvider:
    def __init__(self, inner: ModelProvider, cache_dir: str | Path) -> None:
        self.inner = inner
        self.name = f"cached({inner.name})"
        self.model = inner.model
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _key(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> str:
        blob = json.dumps(
            {
                "p": self.inner.name,
                "m": self.inner.model,
                "s": system,
                "msgs": messages,
                "tools": [t.model_dump() for t in tools],
                # routing/extra options change which upstream answers, so they are part
                # of the identity of a reply (e.g. OpenRouter provider routing)
                "extra": getattr(self.inner, "extra_body", None),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> ModelReply:
        path = self.dir / f"{self._key(system, messages, tools)}.json"
        if path.exists():
            self.hits += 1
            reply = ModelReply.model_validate_json(path.read_text())
            reply.cached = True
            return reply
        self.misses += 1
        reply = self.inner.complete(system=system, messages=messages, tools=tools)
        path.write_text(reply.model_dump_json())
        return reply
