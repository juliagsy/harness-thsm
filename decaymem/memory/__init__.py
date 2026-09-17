from decaymem.memory.base import MemoryBackend
from decaymem.memory.flat import FlatEbbinghausBackend, FlatVectorBackend
from decaymem.memory.thsm import ThsmBackend, make_thsm_variant

FLAT_PRESETS = {
    "flat_vector": {"decay": "none"},
    "flat_ebbinghaus": {"decay": "ebbinghaus"},
    "flat_actr": {"decay": "actr"},
    "flat_memworth": {"decay": "memory_worth"},
}
THSM_VARIANTS = {"thsm", "thsm_nopin", "thsm_nogate", "typed_nolabels", "labels_notypes"}


def make_backend(cfg: dict, provider=None) -> MemoryBackend:
    name = cfg.get("name", "flat_vector")
    params = dict(cfg.get("params", {}))
    if name in FLAT_PRESETS:
        params = {**FLAT_PRESETS[name], **params}
        b = FlatVectorBackend(provider=provider, **params)
        b.name = name
        return b
    if name in THSM_VARIANTS:
        return make_thsm_variant(name, provider, **params)
    raise ValueError(f"unknown backend {name}; known: {sorted(FLAT_PRESETS | THSM_VARIANTS)}")


__all__ = [
    "FlatEbbinghausBackend",
    "FlatVectorBackend",
    "MemoryBackend",
    "ThsmBackend",
    "make_backend",
]
