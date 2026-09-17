from decaymem.memory.base import MemoryBackend
from decaymem.memory.flat import FlatEbbinghausBackend, FlatVectorBackend


def make_backend(cfg: dict, provider=None):
    name = cfg.get("name", "flat_vector")
    if name == "flat_vector":
        return FlatVectorBackend(provider=provider, **cfg.get("params", {}))
    if name == "flat_ebbinghaus":
        return FlatEbbinghausBackend(provider=provider, **cfg.get("params", {}))
    raise ValueError(f"unknown backend {name}")


__all__ = ["FlatEbbinghausBackend", "FlatVectorBackend", "MemoryBackend", "make_backend"]
