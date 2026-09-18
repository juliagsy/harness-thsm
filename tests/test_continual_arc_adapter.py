import pytest

continual_arc = pytest.importorskip("continual_arc")

from continual_arc.env import (  # noqa: E402
    DemosFeedback,
    Observation,
    RequestDemos,
    Submit,
    SubmitFeedback,
)

from decaymem.adapters.continual_arc import EchoProvider, MemoryLearner  # noqa: E402


def obs(task="t1", attempts=0, demos=0, step=1):
    return Observation(
        step=step,
        n_steps=10,
        task_id=task,
        phase="stream",
        input=[[1, 0], [0, 1]],
        exposure_index=0,
        attempts_used=attempts,
        demo_requests_used=demos,
        attempt_cap=8,
        demo_cap=8,
        reset_before=False,
    )


def test_memory_learner_protocol_and_decay():
    from types import SimpleNamespace

    L = MemoryLearner(model="echo", decay="actr", aggressiveness=1.0)
    assert isinstance(L.provider, EchoProvider)
    a = L.act(obs())
    assert isinstance(a, RequestDemos)  # no rule, no demos: buy evidence first
    pair = SimpleNamespace(input=[[1, 0], [0, 1]], output=[[1, 0], [0, 1]])
    L.observe(obs(), a, DemosFeedback(pairs=[pair], refused=False, demo_requests_used=1))
    a = L.act(obs(demos=1))
    assert isinstance(a, Submit) and a.grid == [[1, 0], [0, 1]]
    L.observe(
        obs(demos=1), a, SubmitFeedback(correct=True, valid=True, attempts_used=1, failed=False)
    )
    assert L._rule_for("t1") is not None and L.resources()["rules_active"] == 1
    # a later instance of the same task reuses the rule without demos
    a = L.act(obs(step=5))
    assert isinstance(a, Submit) and L.resources()["rule_hits"] == 1
    # aggressive ACT-R decay eventually expires an untouched rule
    for step in range(6, 400):
        L.observe(
            obs(task="other", step=step),
            Submit([[0]]),
            SubmitFeedback(correct=False, valid=True, attempts_used=1, failed=False),
        )
    assert L.resources()["rules_evicted"] >= 1 and L._rule_for("t1") is None
    # give up after the attempt budget
    assert L.act(obs(attempts=3)).__class__.__name__ == "GiveUp"
