"""Decay policies (docs/01 §2). Each maps an entry's access/outcome history to an
activation value in (0, 1]. Policies never see DEON entries: backends apply them to
SEM/PROC only, which is what the invariant checker verifies.

`aggressiveness` in [0, 1] is the single sweep knob used by the H1 experiment: it scales
the time constant (faster fading) and raises the eviction threshold. 0 = never evict.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from decaymem.core import Entry
from decaymem.core.entries import Activation


def _act(e: Entry) -> Activation:
    if e.activation is None:
        e.activation = Activation()
    return e.activation


class DecayPolicy(ABC):
    name = "base"

    def __init__(self, aggressiveness: float = 0.5) -> None:
        self.aggressiveness = max(0.0, min(1.0, aggressiveness))

    @property
    def evict_below(self) -> float:
        """Activation threshold below which a backend may evict/expire an entry."""
        return 0.0 if self.aggressiveness == 0 else 0.05 + 0.6 * self.aggressiveness

    def on_admit(self, e: Entry, t: int) -> None:
        a = _act(e)
        a.last_access = t
        a.access_times = [t]
        a.value = 1.0

    def on_access(self, e: Entry, t: int) -> None:
        a = _act(e)
        a.access_count += 1
        a.last_access = t
        a.access_times.append(t)

    def on_outcome(self, e: Entry, success: bool) -> None:
        a = _act(e)
        if success:
            a.successes += 1
        else:
            a.failures += 1

    @abstractmethod
    def update(self, e: Entry, t: int) -> float:
        """Recompute and store activation.value at time t; return it."""


class NoDecay(DecayPolicy):
    name = "none"

    def update(self, e: Entry, t: int) -> float:
        _act(e).value = 1.0
        return 1.0


class Ebbinghaus(DecayPolicy):
    """MemoryBank-style: value = exp(-(t - last_access) / (tau * strength)); each access
    multiplies strength by `reinforce` (spaced repetition)."""

    name = "ebbinghaus"

    def __init__(
        self, aggressiveness: float = 0.5, tau: float | None = None, reinforce: float = 1.5
    ) -> None:
        super().__init__(aggressiveness)
        # aggressiveness 0 -> very slow fade, 1 -> tau of ~15 ticks
        self.tau = tau if tau is not None else 15.0 + 185.0 * (1.0 - self.aggressiveness)
        self.reinforce = reinforce

    def update(self, e: Entry, t: int) -> float:
        a = _act(e)
        last = a.last_access if a.last_access is not None else e.temporal.t_created
        strength = self.reinforce**a.access_count
        a.value = math.exp(-max(0, t - last) / (self.tau * strength))
        return a.value


class ACTR(DecayPolicy):
    """ACT-R base-level activation: B = ln(sum_j (t - t_j)^-d) over access times, mapped
    to (0, 1] with a logistic. d = 0.5 canonical (Anderson & Schooler 1991)."""

    name = "actr"

    def __init__(
        self, aggressiveness: float = 0.5, d: float = 0.5, threshold: float | None = None
    ) -> None:
        super().__init__(aggressiveness)
        self.d = d
        # higher threshold = more forgetting; aggressiveness shifts it
        self.threshold = threshold if threshold is not None else -3.0 + 4.0 * self.aggressiveness

    def base_level(self, e: Entry, t: int) -> float:
        a = _act(e)
        times = a.access_times or [e.temporal.t_created]
        s = sum((max(t - tj, 0) + 1.0) ** (-self.d) for tj in times)
        return math.log(s) if s > 0 else -math.inf

    def update(self, e: Entry, t: int) -> float:
        b = self.base_level(e, t)
        a = _act(e)
        a.value = 1.0 / (1.0 + math.exp(-(b - self.threshold)))
        return a.value


class MemoryWorth(DecayPolicy):
    """Two-counter outcome co-occurrence (When to Forget, arXiv:2604.12007): value is the
    Laplace-smoothed success rate of probes in which the entry was retrieved. Time plays
    no role, so a never-retrieved prohibition sits at the prior forever, and one that
    blocks tasks gets pushed down — exactly the failure mode H1 predicts."""

    name = "memory_worth"

    def __init__(self, aggressiveness: float = 0.5, prior: float = 0.5) -> None:
        super().__init__(aggressiveness)
        self.prior = prior

    @property
    def evict_below(self) -> float:
        return 0.0 if self.aggressiveness == 0 else 0.15 + 0.45 * self.aggressiveness

    def update(self, e: Entry, t: int) -> float:
        a = _act(e)
        n = a.successes + a.failures
        a.value = (a.successes + self.prior) / (n + 1.0)
        return a.value


REGISTRY = {c.name: c for c in (NoDecay, Ebbinghaus, ACTR, MemoryWorth)}


def make_decay(name: str = "none", **params) -> DecayPolicy:
    if name not in REGISTRY:
        raise ValueError(f"unknown decay policy {name}; known: {sorted(REGISTRY)}")
    return REGISTRY[name](**params)
