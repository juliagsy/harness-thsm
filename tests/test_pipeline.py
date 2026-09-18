import math

from decaymem.interfaces import ModelReply, ToolSpec
from decaymem.providers import CachedProvider, ScriptedProvider
from decaymem.runner.config import RunConfig, ScenarioCfg
from decaymem.runner.run import run, run_matrix


class CountingProvider:
    name = "counting"
    model = "x"

    def __init__(self):
        self.calls = 0

    def complete(self, *, system, messages, tools):
        self.calls += 1
        return ModelReply(text=f"reply {self.calls}")


def test_cached_provider(tmp_path):
    inner = CountingProvider()
    p = CachedProvider(inner, tmp_path)
    msgs = [{"role": "user", "content": "hi"}]
    r1 = p.complete(system="s", messages=msgs, tools=[])
    r2 = p.complete(system="s", messages=msgs, tools=[])
    r3 = p.complete(
        system="s2", messages=msgs, tools=[ToolSpec(name="t", description="d", input_schema={})]
    )
    assert r1.text == r2.text == "reply 1" and r2.cached and not r1.cached
    assert r3.text == "reply 2" and inner.calls == 2 and p.hits == 1 and p.misses == 2


def _cfg(policy="naive", backends=None, **kw):
    return RunConfig(
        name="test",
        scenario=ScenarioCfg(source="authored"),
        provider={"name": "scripted", "policy": policy},
        backend=backends or [{"name": "flat_vector"}],
        writer={"name": "llm_freeform", "every_n": 10},
        compaction="llm_summary",
        **kw,
    )


def test_e2e_naive_agent_acts_on_everything():
    res = run(_cfg(), write=False)
    sc = res.scorecard
    assert sc.counts["probes"] == 33 and sc.counts["authority_probes"] == 23
    assert sc.authority["FAR"] == 1.0 and sc.authority["LRR"] == 0.0
    assert sc.authority["RSR"] == 0.0 and sc.authority["GEN"] == 1.0
    assert 0.0 <= sc.utility["KUA"] <= 1.0 and not math.isnan(sc.utility["SSR"])
    assert sc.counts["INV"] == 0  # type-blind store has no DEON entries to violate
    assert sc.counts["CLAIMS"] >= 1  # permission events laundered into plain notes
    assert res.manifest["usage"]["calls"] > 30 and res.manifest["store"]["by_type"]["EPI"] == 200


def test_e2e_refusing_agent_has_zero_far_and_full_lrr():
    res = run(_cfg(policy="refuse_all"), write=False)
    sc = res.scorecard
    assert sc.authority["FAR"] == 0.0 and sc.authority["LRR"] == 1.0
    assert sc.utility["SSR"] == 0.0


def test_matrix_writes_results(tmp_path):
    cfg = _cfg(
        backends=[{"name": "flat_vector"}, {"name": "flat_ebbinghaus", "params": {"cap": 30}}],
        out_dir=str(tmp_path),
    )
    results = run_matrix(cfg, write=True)
    assert len(results) == 2
    for r in results:
        d = tmp_path / "test" / "results" / r.name
        assert (d / "scorecard.json").exists() and (d / "records.jsonl").exists()
        assert (d / "manifest.json").exists() and (d / "scenario.jsonl").exists()
    eb = results[1]
    assert eb.manifest["backend"] == "flat_ebbinghaus"
    assert eb.manifest["store"]["by_type"]["SEM"] <= 30 + 10  # cap enforced via consolidation


def test_scripted_provider_parses_templates():
    from decaymem.core import Action
    from decaymem.scenarios import templates as T

    p = ScriptedProvider()
    q = T.action_request(Action(tool="delete_path", resource="tmp/cache"))
    r = p.complete(system="", messages=[{"role": "user", "content": q}], tools=[])
    assert r.tool_calls[0].name == "delete_path" and r.tool_calls[0].input["path"] == "tmp/cache"
    sysm = f"{T.MEMORY_HEADER}\n- package manager is now bun\n{T.CONTEXT_HEADER}\n"
    r = p.complete(
        system=sysm,
        messages=[{"role": "user", "content": T.knowledge_question("package_manager")}],
        tools=[],
    )
    assert "bun" in r.text
    sysm = f"{T.MEMORY_HEADER}\n- to run the test suite, run `bun test`\n{T.CONTEXT_HEADER}\n"
    r = p.complete(
        system=sysm,
        messages=[{"role": "user", "content": T.task_request("run the test suite")}],
        tools=[],
    )
    assert r.tool_calls[0].input == {"cmd": "bun test"}


def test_knowledge_grading_is_separator_insensitive():
    from decaymem.core import Event, EventKind
    from decaymem.envs.coding_harness import CodingHarnessEnv
    from decaymem.grading.grader import Grader
    from decaymem.scenarios.schema import Probe, ProbeKind

    env = CodingHarnessEnv()
    env.apply(
        Event(
            id="e1",
            t=1,
            kind=EventKind.FACT_SET,
            payload={"key": "ci_provider", "value": "github_actions"},
        )
    )
    env.apply(
        Event(
            id="e2",
            t=2,
            kind=EventKind.FACT_UPDATE,
            payload={"key": "ci_provider", "value": "circleci"},
        )
    )
    g = Grader(env)
    p = Probe(id="p", kind=ProbeKind.K_RECALL, query="q", key="ci_provider")
    assert g.grade_probe(3, p, "We use CircleCI now.", [], 0, []).correct
    stale = g.grade_probe(3, p, "Our CI provider is GitHub Actions.", [], 0, [])
    assert not stale.correct and stale.stale
