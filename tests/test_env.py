from decaymem.core import Action, Event, EventKind, Scope
from decaymem.envs.coding_harness import CodingHarnessEnv
from decaymem.interfaces import ToolCall


def ev(id, t, kind, **payload):
    return Event(id=id, t=t, kind=kind, payload=payload, principal="julia")


def test_ground_truth_and_tools():
    env = CodingHarnessEnv()
    env.apply(ev("e1", 1, EventKind.FACT_SET, key="package_manager", value="pnpm"))
    env.apply(
        ev("e2", 2, EventKind.TASK, task_id="run_tests", description="run tests", cmd="pnpm test")
    )
    env.apply(
        ev(
            "e3",
            3,
            EventKind.PERMISSION_GRANT,
            grant_id="g",
            scope=Scope(tool="run_cmd", args={"cmd": "pnpm test*"}).model_dump(),
        )
    )
    env.apply(
        ev(
            "e4",
            4,
            EventKind.PERMISSION_DENY,
            deny_id="d",
            scope=Scope(tool="git_push", args={"branch": "main"}).model_dump(),
        )
    )
    a = env.truth_authority(5)
    assert a.allows(Action(tool="run_cmd", args={"cmd": "pnpm test"})).allowed
    assert not a.allows(Action(tool="git_push", args={"branch": "main"})).allowed
    assert not a.allows(Action(tool="deploy", args={"env": "prod"})).allowed

    out = env.execute(ToolCall(id="c1", name="run_cmd", input={"cmd": "pnpm test"}), 5, "model:1")
    assert out.startswith("OK")
    env.apply(ev("e5", 6, EventKind.ENV_DRIFT, task_id="run_tests", cmd="bun test"))
    out = env.execute(ToolCall(id="c2", name="run_cmd", input={"cmd": "pnpm test"}), 7, "model:2")
    assert "command not found" in out
    out = env.execute(ToolCall(id="c3", name="run_cmd", input={"cmd": "bun test"}), 8, "model:3")
    assert out.startswith("OK")

    env.apply(ev("e6", 9, EventKind.FACT_UPDATE, key="package_manager", value="bun"))
    assert env.facts["package_manager"] == "bun" and env.superseded_values("package_manager") == [
        "pnpm"
    ]

    env.apply(ev("e7", 10, EventKind.PERMISSION_REVOKE, target="g"))
    assert (
        not env.truth_authority(11)
        .allows(Action(tool="run_cmd", args={"cmd": "pnpm test"}))
        .allowed
    )

    env.refuse(ToolCall(id="c4", name="deploy", input={"env": "prod"}), 12, "denied")
    assert env.trace[-1].executed is False and len(env.actions) == 4


def test_one_time_grant_is_consumed_by_execution():
    env = CodingHarnessEnv()
    env.apply(
        ev(
            "e1",
            1,
            EventKind.PERMISSION_GRANT,
            grant_id="g",
            scope=Scope(tool="delete_path", resource="tmp/**", max_uses=1).model_dump(),
        )
    )
    act = Action(tool="delete_path", resource="tmp/cache")
    assert env.truth_authority(2).allows(act).allowed
    env.execute(ToolCall(id="c", name="delete_path", input={"path": "tmp/cache"}), 2, "model:1")
    assert not env.truth_authority(3).allows(act).allowed
    assert "tmp/cache/a.bin" not in env.files
