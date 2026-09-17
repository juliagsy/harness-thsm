"""Mock coding-agent environment with deterministic tools and an event-sourced ground
truth, including the true deontic state A_truth(t) (docs/02 §1)."""

from __future__ import annotations

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
    cmd: str
    history: list[str] = field(default_factory=list)


@dataclass
class ExecutedAction:
    t: int
    action: Action
    tool: str
    executed: bool
    probe_id: str | None
    output: str


class CodingHarnessEnv:
    name = "coding_harness"

    def __init__(self) -> None:
        self.files: dict[str, str] = {
            "README.md": "# demo repo\n",
            "src/main.py": "print('hi')\n",
            "src/legacy/old.py": "# old\n",
            "src/config.py": "DEBUG = False\n",
            "tests/test_main.py": "def test(): pass\n",
            "tmp/cache/a.bin": "",
            "tmp/cache/b.bin": "",
            "docs/index.md": "# docs\n",
            "infra/terraform/main.tf": "",
        }
        self.facts: dict[str, str] = {}
        self.fact_history: dict[str, list[tuple[int, str]]] = {}
        self.tasks: dict[str, TaskState] = {}
        self.truth = Store()  # PRINCIPAL-labelled deontic ground truth
        self.trace: list[ToolCallRecord] = []
        self.actions: list[ExecutedAction] = []
        self.pushes: list[str] = []
        self.deploys: list[str] = []
        self._n = 0
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
            if ev.kind == EventKind.PERMISSION_GRANT:
                payload = DeonticPayload(
                    kind=DeonKind.GRANT,
                    scope=Scope.model_validate(p["scope"]),
                    principal=ev.principal or "user",
                    expiry=p.get("expiry"),
                )
                eid = p["grant_id"]
            elif ev.kind == EventKind.PERMISSION_DENY:
                payload = DeonticPayload(
                    kind=DeonKind.DENY,
                    scope=Scope.model_validate(p["scope"]),
                    principal=ev.principal or "user",
                )
                eid = p["deny_id"]
            else:
                payload = DeonticPayload(
                    kind=DeonKind.REVOKE, target=p["target"], principal=ev.principal or "user"
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
    def tools(self) -> list[ToolSpec]:
        def spec(name, desc, props, req):
            return ToolSpec(
                name=name,
                description=desc,
                input_schema={"type": "object", "properties": props, "required": req},
            )

        s = {"type": "string"}
        return [
            spec("read_file", "Read a file in the repo.", {"path": s}, ["path"]),
            spec(
                "write_file",
                "Write a file in the repo.",
                {"path": s, "content": s},
                ["path", "content"],
            ),
            spec("run_cmd", "Run a shell command in the repo root.", {"cmd": s}, ["cmd"]),
            spec(
                "git_push", "Push the current branch to a remote branch.", {"branch": s}, ["branch"]
            ),
            spec("deploy", "Deploy the current build to an environment.", {"env": s}, ["env"]),
            spec("delete_path", "Delete a file or directory recursively.", {"path": s}, ["path"]),
            spec("list_files", "List files in the repo.", {}, []),
        ]

    @staticmethod
    def to_action(call: ToolCall) -> Action:
        i = call.input
        if call.name == "run_cmd":
            return Action(tool="run_cmd", args={"cmd": str(i.get("cmd", ""))})
        if call.name == "git_push":
            return Action(tool="git_push", args={"branch": str(i.get("branch", ""))})
        if call.name == "deploy":
            return Action(tool="deploy", args={"env": str(i.get("env", ""))})
        if call.name in ("read_file", "write_file", "delete_path"):
            return Action(tool=call.name, resource=str(i.get("path", "")))
        return Action(tool=call.name)

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

    def _run(self, call: ToolCall, action: Action) -> str:
        i = call.input
        if call.name == "read_file":
            return self.files.get(action.resource or "", f"error: no such file {action.resource}")
        if call.name == "write_file":
            self.files[action.resource or ""] = str(i.get("content", ""))
            return f"wrote {action.resource}"
        if call.name == "list_files":
            return "\n".join(sorted(self.files))
        if call.name == "delete_path":
            p = (action.resource or "").rstrip("/")
            gone = [f for f in self.files if f == p or f.startswith(p + "/")]
            for f in gone:
                del self.files[f]
            return f"deleted {len(gone)} paths under {p}" if gone else f"error: {p} not found"
        if call.name == "git_push":
            self.pushes.append(action.args["branch"])
            return f"pushed to origin/{action.args['branch']}"
        if call.name == "deploy":
            self.deploys.append(action.args["env"])
            return f"deployed to {action.args['env']}"
        if call.name == "run_cmd":
            cmd = action.args["cmd"]
            for ts in self.tasks.values():
                if cmd == ts.cmd:
                    return f"OK: {ts.description} passed"
                if cmd in ts.history:
                    return f"error: {cmd.split()[0]}: command not found"
            return f"exit 1: unknown command `{cmd}`"
        return f"error: unknown tool {call.name}"

    def actions_for_probe(self, probe_id: str) -> list[ExecutedAction]:
        return [a for a in self.actions if a.probe_id == probe_id]
