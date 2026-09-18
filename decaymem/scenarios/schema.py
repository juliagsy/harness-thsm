"""Scenario = seeded, event-sourced ground truth plus probe schedule (docs/02 §1-2)."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from decaymem.core import Action, Event, EventKind


class ProbeKind(StrEnum):
    K_RECALL = "K-recall"
    S_TASK = "S-task"
    S_REGRESS = "S-regress"
    A_OK = "A-ok"
    A_REVOKED = "A-revoked"
    A_ADJACENT = "A-adjacent"
    A_DENIED = "A-denied"
    A_NEVER = "A-never"
    S_REVOKED = "S-revoked"  # H6: a task whose standing grant was revoked; acting = skill creep
    A_BELIEF = "A-belief"  # authority-surface elicitation, graded against the truth universe


UTILITY_KINDS = frozenset({ProbeKind.K_RECALL, ProbeKind.S_TASK, ProbeKind.S_REGRESS})
AUTHORITY_KINDS = frozenset(
    {
        ProbeKind.A_OK,
        ProbeKind.A_REVOKED,
        ProbeKind.A_ADJACENT,
        ProbeKind.A_DENIED,
        ProbeKind.A_NEVER,
        ProbeKind.S_REVOKED,
    }
)


class Probe(BaseModel):
    id: str
    kind: ProbeKind
    query: str
    key: str | None = None  # K-recall
    task_id: str | None = None  # S-task / S-regress
    action: Action | None = None  # A-*
    related_grant: str | None = None  # A-revoked / A-adjacent: the grant this relates to
    related_deny: str | None = None  # A-denied: the deny entry id
    universe: list[Action] = Field(default_factory=list)  # A-belief: actions to grade over
    after_compaction: bool = False
    before_compaction: bool = False
    after_session_boundary: bool = False


class Scenario(BaseModel):
    name: str
    domain: str = "coding_harness"
    seed: int = 0
    events: list[Event] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def horizon(self) -> int:
        return len(self.events)

    def probes(self) -> list[tuple[Event, Probe]]:
        return [
            (e, Probe.model_validate(e.payload["probe"]))
            for e in self.events
            if e.kind == EventKind.PROBE
        ]

    def probe_actions(self) -> list[Action]:
        return [p.action for _, p in self.probes() if p.action is not None]

    def to_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "_scenario": {
                            "name": self.name,
                            "domain": self.domain,
                            "seed": self.seed,
                            "meta": self.meta,
                        }
                    }
                )
                + "\n"
            )
            for e in self.events:
                f.write(e.model_dump_json() + "\n")

    @classmethod
    def from_jsonl(cls, path: str | Path) -> Scenario:
        lines = Path(path).read_text().splitlines()
        head = json.loads(lines[0])["_scenario"]
        return cls(events=[Event.model_validate_json(x) for x in lines[1:]], **head)
