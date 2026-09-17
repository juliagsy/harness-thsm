from decaymem.core import Label, SemanticPayload
from decaymem.core.entries import make_entry
from decaymem.policies.decay import make_decay


def note(t=0):
    return make_entry(f"n{t}", SemanticPayload(text="x"), Label.DERIVED, t)


def test_ebbinghaus_fades_and_reinforces():
    pol = make_decay("ebbinghaus", aggressiveness=0.5)
    a, b = note(0), note(0)
    pol.on_admit(a, 0)
    pol.on_admit(b, 0)
    pol.on_access(b, 50)  # b was retrieved once
    va, vb = pol.update(a, 100), pol.update(b, 100)
    assert 0 < va < vb <= 1.0
    assert pol.update(a, 200) < va


def test_actr_recency_and_frequency():
    pol = make_decay("actr", aggressiveness=0.5)
    fresh, old, frequent = note(90), note(0), note(0)
    for e in (fresh, old, frequent):
        pol.on_admit(e, e.temporal.t_created)
    for t in (10, 20, 30, 40, 50):
        pol.on_access(frequent, t)
    v_fresh, v_old, v_freq = (pol.update(e, 100) for e in (fresh, old, frequent))
    assert v_old < v_fresh and v_old < v_freq


def test_memory_worth_is_outcome_driven_not_time_driven():
    pol = make_decay("memory_worth", aggressiveness=0.5)
    good, bad, unused = note(0), note(0), note(0)
    for e in (good, bad, unused):
        pol.on_admit(e, 0)
    for _ in range(5):
        pol.on_outcome(good, True)
        pol.on_outcome(bad, False)
    assert pol.update(good, 1000) > pol.update(unused, 1000) > pol.update(bad, 1000)
    # a prohibition that blocks tasks co-occurs with failure and sinks below the threshold
    assert pol.update(bad, 0) < pol.evict_below


def test_aggressiveness_knob():
    assert make_decay("ebbinghaus", aggressiveness=0.0).evict_below == 0.0
    assert (
        make_decay("ebbinghaus", aggressiveness=1.0).evict_below
        > make_decay("ebbinghaus", aggressiveness=0.5).evict_below
    )
    assert (
        make_decay("ebbinghaus", aggressiveness=1.0).tau
        < make_decay("ebbinghaus", aggressiveness=0.0).tau
    )
