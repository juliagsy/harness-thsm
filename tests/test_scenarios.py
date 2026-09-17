from collections import Counter

from decaymem.core import EventKind
from decaymem.scenarios.authored import build_authored_scenario
from decaymem.scenarios.generator import GeneratorConfig, generate
from decaymem.scenarios.schema import Scenario
from decaymem.scenarios.validate import validate_scenario

EXPECTED_KINDS = {
    EventKind.USER_MESSAGE,
    EventKind.TOOL_RESULT,
    EventKind.PROBE,
    EventKind.PERMISSION_GRANT,
    EventKind.PERMISSION_DENY,
    EventKind.PERMISSION_REVOKE,
    EventKind.FACT_SET,
    EventKind.FACT_UPDATE,
    EventKind.TASK,
    EventKind.ENV_DRIFT,
    EventKind.COMPACTION_TRIGGER,
    EventKind.SESSION_BOUNDARY,
}


def test_authored_scenario_shape_and_validity():
    sc = build_authored_scenario()
    assert sc.horizon == 200
    kinds = {e.kind for e in sc.events}
    assert EXPECTED_KINDS <= kinds
    assert [e.t for e in sc.events] == list(range(200))
    assert validate_scenario(sc) == []
    probes = Counter(p.kind.value for _, p in sc.probes())
    for k in ("K-recall", "S-task", "A-ok", "A-revoked", "A-adjacent", "A-denied", "A-never"):
        assert probes[k] >= 1, k
    flags = [p for _, p in sc.probes() if p.after_compaction or p.before_compaction]
    assert len(flags) >= 4
    injected = [e for e in sc.events if e.payload.get("injected")]
    assert injected and injected[0].effective_label.name == "UNTRUSTED"


def test_jsonl_roundtrip(tmp_path):
    sc = build_authored_scenario()
    path = tmp_path / "s.jsonl"
    sc.to_jsonl(path)
    back = Scenario.from_jsonl(path)
    assert back.model_dump() == sc.model_dump()


def test_generator_is_deterministic_and_valid():
    a = generate(GeneratorConfig(horizon=300, seed=7))
    b = generate(GeneratorConfig(horizon=300, seed=7))
    c = generate(GeneratorConfig(horizon=300, seed=8))
    assert a.model_dump() == b.model_dump()
    assert a.model_dump() != c.model_dump()
    assert a.horizon >= 300
    for sc in (a, c):
        assert validate_scenario(sc) == []
        kinds = Counter(p.kind.value for _, p in sc.probes())
        assert kinds["K-recall"] and kinds["S-task"]
        assert sum(v for k, v in kinds.items() if k.startswith("A-")) >= 3
