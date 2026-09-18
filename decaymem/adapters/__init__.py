"""Adapters that expose third-party memory systems as MemoryBackend plugins (docs/03 §7).
Operators a system does not support are recorded in `backend.unsupported` and the grader
carries that through the manifest."""

from decaymem.adapters.mem0_backend import FakeMem0Client, Mem0Backend

__all__ = ["FakeMem0Client", "Mem0Backend"]
