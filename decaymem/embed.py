"""Dependency-free hashed bag-of-words embedder (the `hash_bow` plugin)."""

from __future__ import annotations

import math
import re
import zlib

_TOKEN = re.compile(r"[a-z0-9]+")


class HashBowEmbedder:
    name = "hash_bow"

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = zlib.crc32(tok.encode())
            v[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))
