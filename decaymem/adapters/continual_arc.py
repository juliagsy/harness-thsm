"""A memory-augmented LLM learner for Continual-ARC, built on decaymem's PROC store.

The learner keeps one PROC entry per ARC task holding the rule the model inferred and
the demo pairs it saw. Each instance: retrieve the task's active PROC entry; if present,
ask the model to apply the rule to the fresh input and Submit; if absent (never learned,
or decayed away), RequestDemos, ask the model to infer the rule and produce the output,
store the rule as a new PROC entry, and Submit. Wrong submissions request demos (until
the cap) and re-infer. Decay is the decaymem policy plugin applied after every instance:
an evicted rule must be re-derived at demo cost, which is exactly the utility cost the
dual benchmark measures on our own scenarios. Authority is out of scope here: there is
nothing to revoke in Continual-ARC, so this learner validates the utility axis only.

Run with Continual-ARC's own CLI:
    uv run continual-arc run --learner decaymem.adapters.continual_arc:MemoryLearner \
        --learner-kwargs '{"decay": "actr", "aggressiveness": 0.5, "model": "openai/gpt-4o-mini"}' \
        --schedule ws.json --out runs/mem-actr-ws
"""

from __future__ import annotations

import json
import re
from typing import Any

from continual_arc.env import (  # type: ignore[import-not-found]
    DemosFeedback,
    GiveUp,
    Observation,
    RequestDemos,
    Submit,
    SubmitFeedback,
)
from continual_arc.learner import BaseLearner  # type: ignore[import-not-found]

from decaymem.core import EntryType, Label, Store
from decaymem.core.entries import ProceduralPayload, make_entry
from decaymem.interfaces import ModelReply
from decaymem.policies.decay import make_decay

Grid = list[list[int]]

SYSTEM = (
    "You solve ARC grid puzzles. Grids are JSON lists of lists of integers 0-9. "
    "When asked for a rule, describe the transformation from input to output in two or three "
    "precise sentences. When asked for an output, reply with the output grid as JSON only."
)


def _grid_str(g: Grid) -> str:
    return json.dumps(g, separators=(",", ":"))


def _parse_grid(text: str) -> Grid | None:
    m = re.search(r"\[\s*\[.*?\]\s*\]", text, re.S)
    if not m:
        return None
    try:
        g = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)):
        return None
    try:
        return [[int(v) for v in row] for row in g]
    except (TypeError, ValueError):
        return None


class MemoryLearner(BaseLearner):
    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",
        decay: str = "none",
        aggressiveness: float = 0.5,
        remember: bool = True,
        max_tokens: int = 1500,
        cache_dir: str = "data/cache",
        provider: Any | None = None,
    ) -> None:
        from decaymem.dotenv import load_dotenv
        from decaymem.providers import make_provider

        load_dotenv()
        self.provider = provider or make_provider(
            {
                "name": "openrouter",
                "model": model,
                "max_tokens": max_tokens,
                "temperature": None if model.startswith("anthropic/") else 0.0,
                "cache": True,
                "cache_dir": cache_dir,
            }
        )
        self.remember = remember
        self.policy = make_decay(decay, aggressiveness=aggressiveness)
        self.store = Store()
        self.t = 0
        self._calls = 0
        self._tokens_in = 0
        self._tokens_out = 0
        self._demos: dict[str, list[tuple[Grid, Grid]]] = {}  # per-task demos for this run
        self._pending_rule: dict[str, str] = {}
        self._tried_without_demos: set[str] = set()
        self._evicted = 0
        self._rederived = 0
        self._hits = 0

    # --- protocol -----------------------------------------------------------------------
    def reset(self) -> None:
        self.store = Store()
        self._demos.clear()
        self._pending_rule.clear()
        self._tried_without_demos.clear()

    def act(self, obs: Observation):
        self.t += 1
        rule = self._rule_for(obs.task_id)
        demos = self._demos.get(obs.task_id, [])
        if rule is None and not demos and obs.demo_requests_used < obs.demo_cap:
            return RequestDemos()
        if (
            obs.attempts_used > 0
            and obs.demo_requests_used < obs.demo_cap
            and obs.attempts_used > obs.demo_requests_used
        ):
            # a wrong attempt on this instance: buy more evidence before trying again
            return RequestDemos()
        if rule is None:
            if demos:
                rule = self._infer_rule(obs.task_id, demos)
                self._rederived += 1
            else:
                rule = "(no rule available; infer from the input alone)"
        else:
            self._hits += 1
        grid = self._apply_rule(rule, demos, obs.input)
        if grid is None:
            if obs.attempts_used >= obs.attempt_cap - 1:
                return GiveUp()
            grid = obs.input  # a valid but almost surely wrong grid; costs one attempt
        return Submit(grid)

    def observe(self, obs: Observation, action, feedback) -> None:
        tid = obs.task_id
        if isinstance(feedback, DemosFeedback) and not feedback.refused:
            self._demos.setdefault(tid, []).extend((p.input, p.output) for p in feedback.pairs)
            self._demos[tid] = self._demos[tid][-9:]
        elif isinstance(feedback, SubmitFeedback):
            entry = self._entry_for(tid)
            if feedback.correct:
                if entry is None and self.remember and tid in self._pending_rule:
                    entry = self._store_rule(tid, self._pending_rule[tid])
                if entry is not None:
                    self.policy.on_outcome(entry, True)
                    self.policy.on_access(entry, self.t)
                self._demos.pop(tid, None)  # rule confirmed: demos no longer needed
            else:
                if entry is not None:
                    self.policy.on_outcome(entry, False)
                    if feedback.failed:
                        entry.temporal.t_expired = self.t  # the rule is wrong: retire it
        # decay after every step; evicted rules cost a re-derivation later
        thr = self.policy.evict_below
        for e in list(self.store.by_type(EntryType.PROC)):
            if not e.active_at(self.t):
                continue
            v = self.policy.update(e, self.t)
            if thr > 0 and v < thr:
                e.temporal.t_expired = self.t
                self._evicted += 1

    def resources(self) -> dict[str, float]:
        active = sum(1 for e in self.store.by_type(EntryType.PROC) if e.active_at(self.t))
        return {
            "calls": float(self._calls),
            "tokens_in": float(self._tokens_in),
            "tokens_out": float(self._tokens_out),
            "rules_active": float(active),
            "rules_evicted": float(self._evicted),
            "rules_rederived": float(self._rederived),
            "rule_hits": float(self._hits),
        }

    # --- memory ---------------------------------------------------------------------------
    def _entry_for(self, tid: str):
        for e in self.store.by_type(EntryType.PROC):
            if e.content.name == tid and e.active_at(self.t):
                return e
        return None

    def _rule_for(self, tid: str) -> str | None:
        e = self._entry_for(tid)
        return e.content.steps[0] if e is not None and e.content.steps else None

    def _store_rule(self, tid: str, rule: str):
        e = make_entry(
            f"rule:{tid}:{self.t}",
            ProceduralPayload(name=tid, steps=[rule]),
            Label.DERIVED,
            self.t,
            writer="memory_learner",
            writer_label=Label.DERIVED,
        )
        self.store.add(e)
        self.policy.on_admit(e, self.t)
        return e

    # --- model calls -------------------------------------------------------------------------
    def _complete(self, user: str) -> ModelReply:
        r = self.provider.complete(
            system=SYSTEM, messages=[{"role": "user", "content": user}], tools=[]
        )
        self._calls += 1
        self._tokens_in += r.usage.get("input_tokens", 0)
        self._tokens_out += r.usage.get("output_tokens", 0)
        return r

    def _infer_rule(self, tid: str, demos: list[tuple[Grid, Grid]]) -> str:
        pairs = "\n".join(f"Input: {_grid_str(i)}\nOutput: {_grid_str(o)}" for i, o in demos)
        r = self._complete(f"Demonstrations for task {tid}:\n{pairs}\n\nState the rule.")
        rule = r.text.strip() or "(rule unclear)"
        self._pending_rule[tid] = rule
        return rule

    def _apply_rule(self, rule: str, demos: list[tuple[Grid, Grid]], inp: Grid) -> Grid | None:
        pairs = "\n".join(f"Input: {_grid_str(i)}\nOutput: {_grid_str(o)}" for i, o in demos[:3])
        ctx = f"Rule: {rule}\n" + (f"Examples:\n{pairs}\n" if pairs else "")
        r = self._complete(
            f"{ctx}\nNow apply the rule to this input and reply with the output "
            f"grid as JSON only.\nInput: {_grid_str(inp)}"
        )
        return _parse_grid(r.text)


__all__ = ["MemoryLearner"]
