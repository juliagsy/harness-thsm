from decaymem.writers.freeform import FreeformWriter


def make_writer(cfg: dict):
    name = cfg.get("name", "llm_freeform")
    if name == "llm_freeform":
        return FreeformWriter(every_n=cfg.get("every_n", 10), max_notes=cfg.get("max_notes", 8))
    raise ValueError(f"unknown writer {name}")


__all__ = ["FreeformWriter", "make_writer"]
