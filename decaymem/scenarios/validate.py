"""Replay a scenario through the environment and check that every probe's kind agrees
with the ground truth authority at its time (docs/04: generator bugs must be caught by
the same machinery before any model call)."""

from __future__ import annotations

from decaymem.core import EventKind
from decaymem.envs import make_env
from decaymem.scenarios.schema import AUTHORITY_KINDS, Probe, ProbeKind, Scenario


def validate_scenario(sc: Scenario) -> list[str]:
    env = make_env(sc.domain)
    problems: list[str] = []
    for ev in sc.events:
        env.apply(ev)
        if ev.kind != EventKind.PROBE:
            continue
        p = Probe.model_validate(ev.payload["probe"])
        if p.kind in AUTHORITY_KINDS:
            allowed = env.truth_authority(ev.t).allows(p.action).allowed
            if p.kind == ProbeKind.A_OK:
                if not allowed:
                    problems.append(f"t={ev.t} {p.id}: A-ok but truth forbids {p.action}")
                env.consume_grant(p.action, ev.t)  # assume the agent acts on an allowed probe
            elif allowed:
                problems.append(f"t={ev.t} {p.id}: {p.kind} but truth allows {p.action}")
        elif p.kind == ProbeKind.A_BELIEF:
            if not p.universe:
                problems.append(f"t={ev.t} {p.id}: A-belief with empty universe")
        elif p.kind == ProbeKind.K_RECALL and p.key not in env.facts:
            problems.append(f"t={ev.t} {p.id}: recall of unknown fact {p.key}")
        elif p.kind in (ProbeKind.S_TASK, ProbeKind.S_REGRESS) and p.task_id not in env.tasks:
            problems.append(f"t={ev.t} {p.id}: task probe for unknown task {p.task_id}")
    return problems
