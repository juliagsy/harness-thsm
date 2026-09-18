"""Shared environment machinery: event-sourced ground truth (facts, tasks, deontic truth),
tool-call recording and one-time grant consumption. Domains subclass and provide the
tool surface, the action mapping and the scripted tool behaviour."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from decaymem.core import (
    Action,
    Authority,
    DeonKind,
    DeonticPayload,
    Event,
    EventKind,
    Label,
    Scope,
    Store,
    ToolCallRecord,
    effective_authority,
    event_to_entry,
)
from decaymem.core.entries import make_entry
from decaymem.interfaces import ToolCall, ToolSpec


@dataclass
class TaskState:
    task_id: str
    description: str
    cmd: str  # the current "right way" (a command, a report name, ...)
    history: list[str] = field(default_factory=list)


@dataclass
class ExecutedAction:
    t: int
    action: Action
    tool: str
    executed: bool
    probe_id: str | None
    output: str


class BaseEnv(ABC):
    name = "base"
    task_tool = "run_cmd"  # tool that performs tasks
    task_arg = "cmd"  # its argument carrying the task's "command"

    def __init__(self) -> None:
        self.facts: dict[str, str] = {}
        self.fact_history: dict[str, list[tuple[int, str]]] = {}
        self.tasks: dict[str, TaskState] = {}
        self.truth = Store()  # PRINCIPAL-labelled deontic ground truth
        self.trace: list[ToolCallRecord] = []
        self.actions: list[ExecutedAction] = []
        self.current_probe: str | None = None

    # --- ground truth -----------------------------------------------------------------
    def apply(self, ev: Event) -> None:
        p = ev.payload
        if ev.kind in (EventKind.FACT_SET, EventKind.FACT_UPDATE):
            self.facts[p["key"]] = p["value"]
            self.fact_history.setdefault(p["key"], []).append((ev.t, p["value"]))
        elif ev.kind == EventKind.TASK:
            self.tasks[p["task_id"]] = TaskState(
                p["task_id"], p["description"], p["cmd"], [p["cmd"]]
            )
        elif ev.kind == EventKind.ENV_DRIFT:
            ts = self.tasks[p["task_id"]]
            ts.cmd = p["cmd"]
            ts.history.append(p["cmd"])
        elif ev.kind in (
            EventKind.PERMISSION_GRANT,
            EventKind.PERMISSION_DENY,
            EventKind.PERMISSION_REVOKE,
        ):
            epi = event_to_entry(ev)
            self.truth.add(epi)
            principal = ev.principal or "user"
            if ev.kind == EventKind.PERMISSION_GRANT:
                payload = DeonticPayload(
                    kind=DeonKind.GRANT,
                    scope=Scope.model_validate(p["scope"]),
                    principal=principal,
                    expiry=p.get("expiry"),
                )
                eid = p["grant_id"]
            elif ev.kind == EventKind.PERMISSION_DENY:
                payload = DeonticPayload(
                    kind=DeonKind.DENY, scope=Scope.model_validate(p["scope"]), principal=principal
                )
                eid = p["deny_id"]
            else:
                payload = DeonticPayload(
                    kind=DeonKind.REVOKE, target=p["target"], principal=principal
                )
                eid = f"r_{p['target']}_{ev.t}"
            self.truth.add(
                make_entry(
                    eid,
                    payload,
                    Label.PRINCIPAL,
                    ev.t,
                    sources=[epi.id],
                    writer="principal",
                    writer_label=Label.PRINCIPAL,
                )
            )
        self._apply_domain(ev)

    def _apply_domain(self, ev: Event) -> None:  # hook for domain-specific state
        return None

    def truth_authority(self, t: int) -> Authority:
        return effective_authority(self.truth, t)

    def consume_grant(self, action: Action, t: int) -> None:
        """Ground truth for `max_uses`: an executed action uses up the grant that allowed it."""
        dec = self.truth_authority(t).allows(action)
        if dec.allowed and dec.matched_grant:
            g = self.truth.get(dec.matched_grant).deon
            if g.uses_remaining is not None and g.uses_remaining > 0:
                g.uses_remaining -= 1

    def superseded_values(self, key: str) -> list[str]:
        hist = [v for _, v in self.fact_history.get(key, [])]
        return hist[:-1]

    # --- tools ------------------------------------------------------------------------------
    @abstractmethod
    def tools(self) -> list[ToolSpec]: ...

    @abstractmethod
    def to_action(self, call: ToolCall) -> Action: ...

    @abstractmethod
    def _run(self, call: ToolCall, action: Action) -> str: ...

    def task_output(self, value: str, unit: str = "command") -> str:
        """Shared scripted behaviour for the task tool: success on the current value,
        a 'retired' error on a stale one, unknown otherwise."""
        for ts in self.tasks.values():
            if value == ts.cmd:
                return f"OK: {ts.description} done"
            if value in ts.history:
                return f"error: {unit} `{value}` is no longer available"
        return f"error: unknown {unit} `{value}`"

    def execute(
        self,
        call: ToolCall,
        t: int,
        authorization_id: str | None,
        origin_proc_id: str | None = None,
    ) -> str:
        action = self.to_action(call)
        out = self._run(call, action)
        self.consume_grant(action, t)
        self.trace.append(
            ToolCallRecord(
                call_id=call.id,
                tool=call.name,
                args={k: str(v) for k, v in call.input.items()},
                resource=action.resource,
                origin_proc_id=origin_proc_id,
                authorization_id=authorization_id,
                executed=True,
            )
        )
        self.actions.append(ExecutedAction(t, action, call.name, True, self.current_probe, out))
        return out

    def refuse(self, call: ToolCall, t: int, reason: str) -> str:
        action = self.to_action(call)
        out = f"refused: {reason}"
        self.trace.append(
            ToolCallRecord(
                call_id=call.id,
                tool=call.name,
                args={k: str(v) for k, v in call.input.items()},
                resource=action.resource,
                authorization_id=None,
                executed=False,
            )
        )
        self.actions.append(ExecutedAction(t, action, call.name, False, self.current_probe, out))
        return out

    def actions_for_probe(self, probe_id: str) -> list[ExecutedAction]:
        return [a for a in self.actions if a.probe_id == probe_id]


def spec(name: str, desc: str, props: dict, req: list[str]) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=desc,
        input_schema={"type": "object", "properties": props, "required": req},
    )
