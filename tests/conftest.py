"""Hand-written stores for the invariant tests (Phase 0 exit criterion)."""

from __future__ import annotations

import pytest

from decaymem.core import (
    DeonKind,
    DeonticPayload,
    Event,
    EventKind,
    Label,
    ProceduralPayload,
    Scope,
    SemanticPayload,
    Store,
    admit,
    event_to_entry,
)
from decaymem.core.entries import make_entry

TEST_SCOPE = Scope(tool="run_cmd", args={"cmd": "pnpm test*"})
TMP_ONCE = Scope(tool="delete_path", resource="tmp/**", max_uses=1)
PUSH_MAIN = Scope(tool="git_push", args={"branch": "main"})


def ev(id: str, t: int, kind: EventKind, **payload) -> Event:
    return Event(id=id, t=t, kind=kind, payload=payload, principal="julia")


@pytest.fixture
def valid_store() -> Store:
    """A store that satisfies every invariant.

    t=10  user grants `pnpm test*`                      (PRINCIPAL grant)
    t=12  tool result mentions a fact                   (UNTRUSTED epi)
    t=13  LLM writes SEM fact from the tool result      (label UNTRUSTED via L1)
    t=20  user grants delete tmp/** once                (PRINCIPAL grant, max_uses=1)
    t=30  user denies git push to main                  (PRINCIPAL deny)
    t=40  harness narrows the pnpm grant (mode change)  (HARNESS grant, supersedes)
    t=50  user revokes the tmp grant                    (PRINCIPAL revoke)
    t=55  LLM writes a PROC skill from an assistant msg (DERIVED)
    """
    s = Store()

    e10 = ev("e10", 10, EventKind.PERMISSION_GRANT, scope=TEST_SCOPE.model_dump())
    s.add(event_to_entry(e10))
    admit(
        s,
        make_entry(
            "g_test",
            DeonticPayload(kind=DeonKind.GRANT, scope=TEST_SCOPE, principal="julia"),
            Label.PRINCIPAL,
            10,
            sources=["epi:e10"],
            writer="permission_prompt",
            writer_label=Label.PRINCIPAL,
        ),
        10,
    )

    e12 = ev("e12", 12, EventKind.TOOL_RESULT, output="package manager: pnpm")
    s.add(event_to_entry(e12))
    admit(
        s,
        make_entry(
            "f_pm",
            SemanticPayload(text="repo uses pnpm", key="package_manager", value="pnpm"),
            Label.UNTRUSTED,
            13,
            sources=["epi:e12"],
            writer="llm_writer",
            writer_label=Label.DERIVED,
        ),
        13,
    )

    e20 = ev("e20", 20, EventKind.PERMISSION_GRANT, scope=TMP_ONCE.model_dump())
    s.add(event_to_entry(e20))
    admit(
        s,
        make_entry(
            "g_tmp",
            DeonticPayload(kind=DeonKind.GRANT, scope=TMP_ONCE, principal="julia"),
            Label.PRINCIPAL,
            20,
            sources=["epi:e20"],
            writer="permission_prompt",
            writer_label=Label.PRINCIPAL,
        ),
        20,
    )

    e30 = ev("e30", 30, EventKind.PERMISSION_DENY, scope=PUSH_MAIN.model_dump())
    s.add(event_to_entry(e30))
    admit(
        s,
        make_entry(
            "d_push",
            DeonticPayload(kind=DeonKind.DENY, scope=PUSH_MAIN, principal="julia"),
            Label.PRINCIPAL,
            30,
            sources=["epi:e30"],
            writer="permission_prompt",
            writer_label=Label.PRINCIPAL,
        ),
        30,
    )

    e40 = ev("e40", 40, EventKind.MODE_CHANGE, mode="auto")
    s.add(event_to_entry(e40))
    narrowed = Scope(tool="run_cmd", args={"cmd": "pnpm test"})
    new_grant = make_entry(
        "g_test_v2",
        DeonticPayload(kind=DeonKind.GRANT, scope=narrowed, principal="julia"),
        Label.HARNESS,
        40,
        sources=["g_test", "epi:e40"],
        writer="auto_mode_rules",
        writer_label=Label.HARNESS,
    )
    s.get("g_test").temporal.t_valid_to = 40
    admit(s, new_grant, 40)

    e50 = ev("e50", 50, EventKind.PERMISSION_REVOKE, target="g_tmp")
    s.add(event_to_entry(e50))
    admit(
        s,
        make_entry(
            "r_tmp",
            DeonticPayload(kind=DeonKind.REVOKE, target="g_tmp", principal="julia"),
            Label.PRINCIPAL,
            50,
            sources=["epi:e50", "g_tmp"],
            writer="permission_prompt",
            writer_label=Label.PRINCIPAL,
        ),
        50,
    )

    e55 = ev("e55", 55, EventKind.ASSISTANT_MESSAGE, text="to run tests: pnpm test")
    s.add(event_to_entry(e55))
    admit(
        s,
        make_entry(
            "p_test",
            ProceduralPayload(name="run tests", steps=["run_cmd pnpm test"]),
            Label.DERIVED,
            55,
            sources=["epi:e55"],
            writer="llm_writer",
            writer_label=Label.DERIVED,
        ),
        55,
    )

    s.clock = 60
    return s
