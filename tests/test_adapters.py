from decaymem.adapters import FakeMem0Client, Mem0Backend
from decaymem.core import Label, SemanticPayload
from decaymem.core.entries import make_entry
from decaymem.memory import make_backend
from decaymem.runner.config import RunConfig, ScenarioCfg
from decaymem.runner.run import run


def test_mem0_adapter_roundtrip():
    b = Mem0Backend(client=FakeMem0Client())
    b.write(
        [
            make_entry("n1", SemanticPayload(text="repo uses pnpm"), Label.DERIVED, 1),
            make_entry(
                "n2", SemanticPayload(text="user allowed run_cmd pnpm test"), Label.DERIVED, 1
            ),
        ],
        1,
    )
    hits = b.retrieve("which package manager pnpm", 2, 5)
    assert hits and "pnpm" in hits[0].content.text
    assert b.authorize(None, 2) is None and "authorize" in b.unsupported
    assert b.describe()["external"] == "mem0"


def test_mem0_backend_runs_through_pipeline_with_fake_client():
    cfg = RunConfig(
        name="t",
        scenario=ScenarioCfg(source="authored"),
        provider={"name": "scripted", "policy": "memory_aware"},
        backend=[{"name": "mem0", "params": {"fake": True}}],
        writer={"name": "llm_freeform", "every_n": 10},
    )
    res = run(cfg, write=False)
    assert res.manifest["backend"] == "mem0"
    assert res.manifest["backend_desc"]["unsupported"] == ["authorize", "decay"]
    assert res.scorecard.counts["probes"] == 33


def test_make_backend_mem0_fake():
    assert make_backend({"name": "mem0", "params": {"fake": True}}).name == "mem0"
