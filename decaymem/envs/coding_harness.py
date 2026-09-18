"""Mock coding-agent environment: a repo with deterministic tools (docs/02 §1)."""

from __future__ import annotations

from decaymem.core import Action
from decaymem.envs.base import BaseEnv, ExecutedAction, TaskState, spec
from decaymem.interfaces import ToolCall, ToolSpec

__all__ = ["CodingHarnessEnv", "ExecutedAction", "TaskState"]


class CodingHarnessEnv(BaseEnv):
    name = "coding_harness"
    task_tool = "run_cmd"
    task_arg = "cmd"

    def __init__(self) -> None:
        super().__init__()
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
        self.pushes: list[str] = []
        self.deploys: list[str] = []

    def tools(self) -> list[ToolSpec]:
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
                "git_push",
                "Push the current branch to a remote branch.",
                {"branch": s},
                ["branch"],
            ),
            spec("deploy", "Deploy the current build to an environment.", {"env": s}, ["env"]),
            spec("delete_path", "Delete a file or directory recursively.", {"path": s}, ["path"]),
            spec("list_files", "List files in the repo.", {}, []),
        ]

    def to_action(self, call: ToolCall) -> Action:
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
