"""Phase 0 exit criterion: invariants pass on a valid store and fail on violations."""

from decaymem.core import (
    Action,
    DeonKind,
    DeonticPayload,
    Event,
    EventKind,
    Label,
    Operator,
    Scope,
    SemanticPayload,
    Store,
    ToolCallRecord,
    check_all,
    check_state,
    check_trace,
    check_transition,
    event_to_entry,
)
from decaymem.core.entries import make_entry

UNIVERSE = [
    Action(tool="run_cmd", args={"cmd": "pnpm test"}),
    Action(tool="run_cmd", args={"cmd": "pnpm test --watch"}),
    Action(tool="delete_path", resource="tmp/cache"),
    Action(tool="delete_path", resource="src/x.py"),
    Action(tool="git_push", args={"branch": "main"}),
]


def ids(violations):
    return sorted({v.invariant for v in violations})


# --- the valid store passes everything ---------------------------------------------


def test_valid_store_has_no_violations(valid_store: Store):
    assert check_state(valid_store) == []
    assert check_all(valid_store, universe=UNIVERSE) == []


def test_valid_lossy_operators_pass(valid_store: Store):
    def decay(s: Store):
        for e in s:
            if e.activation is not None:
                e.activation.value *= 0.5

    def consolidate(s: Store):
        s.add(
            make_entry(
                "f_sum",
                SemanticPayload(text="summary: pnpm"),
                Label.UNTRUSTED,
                61,
                sources=["f_pm"],
                writer="llm",
                writer_label=Label.DERIVED,
            )
        )

    def compact(s: Store):
        s.remove("f_pm")  # evicting a SEM entry is fine

    valid_store.apply(Operator.DECAY, decay, t=60)
    valid_store.apply(Operator.CONSOLIDATE, consolidate, t=61)
    valid_store.apply(Operator.COMPACT, compact, t=62)
    assert check_all(valid_store, universe=UNIVERSE) == []


def test_principal_widening_event_permits_new_grant(valid_store: Store):
    ev = Event(id="e70", t=70, kind=EventKind.PERMISSION_GRANT, payload={})

    def widen(s: Store):
        s.add(event_to_entry(ev))
        s.add(
            make_entry(
                "g_deploy",
                DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="deploy"), principal="julia"),
                Label.PRINCIPAL,
                70,
                sources=["epi:e70"],
                writer_label=Label.PRINCIPAL,
            )
        )

    valid_store.apply(Operator.ADMIT, widen, t=70, events=[ev])
    assert check_all(valid_store, universe=UNIVERSE) == []


# --- each invariant fails on a hand-written violation -----------------------------------


def test_i1_widening_without_principal_event(valid_store: Store):
    def sneak(s: Store):
        s.add(
            make_entry(
                "g_all",
                DeonticPayload(kind=DeonKind.GRANT, scope=Scope(), principal="julia"),
                Label.PRINCIPAL,
                70,
                sources=["epi:e10"],
                writer_label=Label.PRINCIPAL,
            )
        )

    valid_store.apply(Operator.CONSOLIDATE, sneak, t=70)  # no PERMISSION_GRANT event
    v = check_transition(
        valid_store.log[-1].before, valid_store.log[-1].after, Operator.CONSOLIDATE
    )
    assert "I1" in ids(v)
    assert "I3" in ids(v)  # a lossy operator also touched DEON


def test_i1_losing_a_deny(valid_store: Store):
    """Symbolic check is conservative: a lost deny is widening. The exact universe check
    knows there is no grant for git_push, so only I3 fires."""
    valid_store.apply(Operator.DECAY, lambda s: s.remove("d_push"), t=70)
    rec = valid_store.log[-1]
    assert ids(check_transition(rec.before, rec.after, Operator.DECAY)) == ["I1", "I3"]
    assert ids(check_transition(rec.before, rec.after, Operator.DECAY, universe=UNIVERSE)) == ["I3"]


def test_i1_detected_with_universe_only_for_scope_overlap(valid_store: Store):
    """Symbolic check is conservative; universe check is exact over the universe."""
    ev = Event(id="e80", t=80, kind=EventKind.MODE_CHANGE)  # HARNESS, not widening

    def widen(s: Store):
        s.add(event_to_entry(ev))
        s.add(
            make_entry(
                "g_src",
                DeonticPayload(
                    kind=DeonKind.GRANT,
                    scope=Scope(tool="delete_path", resource="src/**"),
                    principal="julia",
                ),
                Label.HARNESS,
                80,
                sources=["epi:e80"],
            )
        )

    valid_store.apply(Operator.ADMIT, widen, t=80, events=[ev])
    rec = valid_store.log[-1]
    assert "I1" in ids(check_transition(rec.before, rec.after, rec.operator, rec.events, UNIVERSE))
    assert "I1" in ids(check_transition(rec.before, rec.after, rec.operator, rec.events))
    assert "I2" in ids(check_state(valid_store))  # HARNESS grant that narrows nothing


def test_i2_derived_deon_entry(valid_store: Store):
    valid_store.add(
        make_entry(
            "g_llm",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="julia"),
            Label.DERIVED,
            70,
            sources=["epi:e55"],
            writer="llm",
            writer_label=Label.DERIVED,
        )
    )
    v = check_state(valid_store)
    assert ids(v) == ["I2"] and v[0].entry_ids == ["g_llm"]


def test_i2_principal_label_but_untrusted_provenance(valid_store: Store):
    """Laundered: label says PRINCIPAL, but the only source is a tool result."""
    valid_store.add(
        make_entry(
            "g_laund",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="julia"),
            Label.PRINCIPAL,
            70,
            sources=["epi:e12"],
            writer_label=Label.PRINCIPAL,
        )
    )
    v = check_state(valid_store)
    assert "I2" in ids(v)
    assert any("EPI ancestor" in x.message for x in v)


def test_i2_no_provenance(valid_store: Store):
    valid_store.add(
        make_entry(
            "g_orphan",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="julia"),
            Label.PRINCIPAL,
            70,
            writer_label=Label.PRINCIPAL,
        )
    )
    v = check_state(valid_store)
    assert any(x.invariant == "I2" and "no provenance" in x.message for x in v)


def test_i2_broken_chain_when_backing_epi_evicted(valid_store: Store):
    valid_store.remove("epi:e30")  # the event backing the deny
    v = check_state(valid_store)
    assert any(x.invariant == "I2" and x.entry_ids == ["d_push"] for x in v)


def test_i3_lossy_operator_removes_revoke(valid_store: Store):
    valid_store.apply(Operator.DECAY, lambda s: s.remove("r_tmp"), t=70)
    rec = valid_store.log[-1]
    v = check_transition(rec.before, rec.after, rec.operator)
    assert "I3" in ids(v) and "I1" in ids(v)  # revoked grant comes back = widening
    assert any("revocation/denial" in x.message for x in v)


def test_i3_lossy_operator_modifies_grant(valid_store: Store):
    def touch(s: Store):
        s.get("g_test_v2").deon.scope = Scope(tool="run_cmd", args={"cmd": "pnpm test"})
        s.get("g_test_v2").deon.conditions["note"] = "summarised"

    valid_store.apply(Operator.COMPACT, touch, t=70)
    rec = valid_store.log[-1]
    v = check_transition(rec.before, rec.after, rec.operator)
    assert ids(v) == ["I3"]


def test_i3_not_triggered_by_admit(valid_store: Store):
    ev = Event(id="e90", t=90, kind=EventKind.PERMISSION_DENY)

    def deny(s: Store):
        s.add(event_to_entry(ev))
        s.add(
            make_entry(
                "d_new",
                DeonticPayload(kind=DeonKind.DENY, scope=Scope(tool="deploy"), principal="julia"),
                Label.PRINCIPAL,
                90,
                sources=["epi:e90"],
                writer_label=Label.PRINCIPAL,
            )
        )

    valid_store.apply(Operator.ADMIT, deny, t=90, events=[ev])
    assert check_all(valid_store, universe=UNIVERSE) == []


def test_i4_label_above_sources(valid_store: Store):
    valid_store.add(
        make_entry(
            "f_up",
            SemanticPayload(text="trusted?"),
            Label.PRINCIPAL,
            70,
            sources=["epi:e12"],
            writer="llm",
            writer_label=Label.DERIVED,
        )
    )
    v = check_state(valid_store)
    assert ids(v) == ["I4"]


def test_i4_label_above_writer(valid_store: Store):
    valid_store.add(
        make_entry(
            "f_w",
            SemanticPayload(text="x"),
            Label.HARNESS,
            70,
            sources=["epi:e10"],
            writer="llm",
            writer_label=Label.DERIVED,
        )
    )
    assert ids(check_state(valid_store)) == ["I4"]


def test_i5_executed_without_authorization():
    trace = [
        ToolCallRecord(call_id="c1", tool="run_cmd", authorization_id="a1", executed=True),
        ToolCallRecord(call_id="c2", tool="delete_path", origin_proc_id="p_test", executed=True),
        ToolCallRecord(call_id="c3", tool="deploy", executed=False),  # refused, fine
    ]
    v = check_trace(trace)
    assert len(v) == 1 and v[0].invariant == "I5" and v[0].entry_ids == ["c2"]
    assert "p_test" in v[0].message


def test_i6_epi_rewritten_or_removed(valid_store: Store):
    def rewrite(s: Store):
        s.get("epi:e12").content.content["output"] = "package manager: bun"

    valid_store.apply(Operator.CONSOLIDATE, rewrite, t=70)
    rec = valid_store.log[-1]
    assert ids(check_transition(rec.before, rec.after, rec.operator)) == ["I6"]

    valid_store.apply(Operator.COMPACT, lambda s: s.remove("epi:e55"), t=71)
    rec = valid_store.log[-1]
    v = check_transition(rec.before, rec.after, rec.operator)
    assert ids(v) == ["I6"] and "removed" in v[0].message


def test_store_supersede_refuses_epi(valid_store: Store):
    import pytest

    with pytest.raises(ValueError):
        valid_store.supersede(
            "epi:e10", make_entry("x", SemanticPayload(text="x"), Label.DERIVED, 70), 70
        )


def test_check_all_aggregates(valid_store: Store):
    valid_store.apply(Operator.DECAY, lambda s: s.remove("r_tmp"), t=70)
    valid_store.add(
        make_entry(
            "g_llm",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="julia"),
            Label.DERIVED,
            71,
            sources=["epi:e55"],
            writer_label=Label.DERIVED,
        )
    )
    trace = [ToolCallRecord(call_id="c", tool="x", executed=True)]
    v = check_all(valid_store, trace=trace, universe=UNIVERSE)
    assert ids(v) == ["I1", "I2", "I3", "I5"]
