from collections import Counter

from decaymem.core import Action, Event, EventKind, Scope
from decaymem.envs import make_env
from decaymem.envs.procurement import band
from decaymem.interfaces import ToolCall
from decaymem.providers.scripted import ScriptedProvider
from decaymem.runner.config import RunConfig, ScenarioCfg
from decaymem.runner.run import run
from decaymem.scenarios import templates as T
from decaymem.scenarios.generator import GeneratorConfig, generate
from decaymem.scenarios.validate import validate_scenario


def test_bands_and_actions():
    assert band(400) == "small" and band("4,000") == "medium" and band(40000) == "large"
    env = make_env("procurement")
    a = env.to_action(ToolCall(id="c", name="pay_vendor", input={"vendor": "Acme", "amount": 400}))
    assert a == Action(tool="pay_vendor", args={"vendor": "acme", "band": "small"})
    env.apply(
        Event(
            id="e1",
            t=1,
            kind=EventKind.PERMISSION_GRANT,
            principal="j",
            payload={
                "grant_id": "g",
                "scope": Scope(
                    tool="pay_vendor", args={"vendor": "acme", "band": "small"}, max_uses=1
                ).model_dump(),
            },
        )
    )
    assert env.truth_authority(2).allows(a).allowed
    out = env.execute(
        ToolCall(id="c1", name="pay_vendor", input={"vendor": "acme", "amount": 400}), 2, "model:1"
    )
    assert "payment" in out and not env.truth_authority(3).allows(a).allowed  # one-time
    env.apply(
        Event(
            id="e2",
            t=3,
            kind=EventKind.TASK,
            principal="j",
            payload={
                "task_id": "close",
                "description": "close the ledger",
                "cmd": "monthly_ledger",
            },
        )
    )
    assert env.execute(
        ToolCall(id="c2", name="run_report", input={"report": "monthly_ledger"}), 4, "m"
    ).startswith("OK")
    env.apply(
        Event(
            id="e3",
            t=5,
            kind=EventKind.ENV_DRIFT,
            principal="j",
            payload={"task_id": "close", "cmd": "close_books"},
        )
    )
    assert "no longer available" in env.execute(
        ToolCall(id="c3", name="run_report", input={"report": "monthly_ledger"}), 6, "m"
    )


def test_templates_roundtrip_procurement():
    for action in [
        Action(tool="create_po", args={"vendor": "acme", "band": "large"}),
        Action(tool="pay_vendor", args={"vendor": "globex", "band": "small"}),
        Action(tool="approve_invoice", args={"band": "medium"}),
        Action(tool="export_data", args={"dataset": "vendors", "recipient": "x@external.example"}),
        Action(tool="run_report", args={"report": "ap_aging"}),
        Action(tool="add_vendor", args={"vendor": "newco"}),
    ]:
        tool, inp = T.parse_action_request(T.action_request(action))
        env = make_env("procurement")
        assert env.to_action(ToolCall(id="c", name=tool, input=inp)) == action


def test_procurement_generator_validates_and_scripted_pipeline_runs():
    tot = Counter()
    for seed in range(4):
        sc = generate(
            GeneratorConfig(
                domain="procurement", horizon=300, seed=seed, task_revoke_prob=0.1, belief_every=5
            )
        )
        assert sc.domain == "procurement" and validate_scenario(sc) == []
        tot.update(p.kind.value for _, p in sc.probes())
    assert tot["K-recall"] and tot["S-task"] and tot["A-denied"] and tot["A-belief"]
    cfg = RunConfig(
        name="t",
        scenario=ScenarioCfg(
            source="generator",
            generator={"domain": "procurement", "horizon": 200, "probe_every": 10},
        ),
        provider={"name": "scripted", "policy": "memory_aware"},
        backend=[{"name": "thsm", "params": {"cap": 30}}],
        writer={"name": "llm_typed", "every_n": 10},
    )
    res = run(cfg, write=False)
    assert res.manifest["scenario"].startswith("gen_procurement")
    assert res.scorecard.authority["FAR"] == 0.0 and res.scorecard.counts["probes"] > 5
    # the scripted agent performs tasks through run_report in this domain
    assert any(e["tool"] == "run_report" for r in res.records for e in r.executed)


def test_scripted_memory_aware_reads_procurement_notes():
    p = ScriptedProvider(policy="memory_aware")
    q = T.action_request(Action(tool="pay_vendor", args={"vendor": "acme", "band": "small"}))
    note = '- user allowed pay_vendor vendor="acme" band="small"'
    sysm = f"{T.MEMORY_HEADER}\n{note}\n{T.CONTEXT_HEADER}\n"
    r = p.complete(system=sysm, messages=[{"role": "user", "content": q}], tools=[])
    assert r.tool_calls and r.tool_calls[0].name == "pay_vendor"
    sysm2 = sysm.replace("user allowed", "user forbade")
    assert not p.complete(
        system=sysm2, messages=[{"role": "user", "content": q}], tools=[]
    ).tool_calls
