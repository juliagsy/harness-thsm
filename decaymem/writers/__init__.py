from decaymem.writers.freeform import FreeformWriter
from decaymem.writers.typed import TypedWriter


def make_writer(cfg: dict):
    name = cfg.get("name", "llm_freeform")
    if name == "llm_freeform":
        return FreeformWriter(every_n=cfg.get("every_n", 10), max_notes=cfg.get("max_notes", 8))
    if name == "llm_typed":
        return TypedWriter(every_n=cfg.get("every_n", 10), max_entries=cfg.get("max_entries", 10))
    raise ValueError(f"unknown writer {name}")


__all__ = ["FreeformWriter", "TypedWriter", "make_writer"]
