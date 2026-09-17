from decaymem.core import (
    DeonKind,
    DeonticPayload,
    EntryType,
    Label,
    Scope,
    Store,
    admit,
    effective_authority,
)
from decaymem.core.entries import make_entry
from decaymem.core.scope import Action


def grant(id: str, scope: Scope, label: Label, t: int, **kw):
    return make_entry(
        id, DeonticPayload(kind=DeonKind.GRANT, scope=scope, principal="julia"), label, t, **kw
    )


def test_principal_grant_accepted():
    s = Store()
    r = admit(s, grant("g", Scope(tool="x"), Label.PRINCIPAL, 0), 0)
    assert r.accepted_as_deontic and s.get("g").type == EntryType.DEON


def test_derived_grant_becomes_claim_with_no_authority():
    """The laundering vector: an LLM writer 'remembers' a permission."""
    s = Store()
    r = admit(
        s,
        grant(
            "g",
            Scope(tool="delete_path", resource="**"),
            Label.DERIVED,
            0,
            writer="llm_writer",
            writer_label=Label.DERIVED,
        ),
        0,
    )
    assert r.converted_to_claim and not r.accepted_as_deontic
    e = s.get("g")
    assert e.type == EntryType.SEM and e.content.deontic_claim is not None
    assert not e.content.proposal
    assert not effective_authority(s, 1).allows(Action(tool="delete_path", resource="a")).allowed


def test_untrusted_grant_becomes_claim():
    s = Store()
    r = admit(s, grant("g", Scope(tool="x"), Label.UNTRUSTED, 0), 0)
    assert r.converted_to_claim


def test_proposal_then_confirmation():
    s = Store()
    r = admit(
        s,
        grant(
            "prop", Scope(tool="deploy"), Label.DERIVED, 0, writer="llm", writer_label=Label.DERIVED
        ),
        0,
        proposal=True,
    )
    assert r.converted_to_claim and s.get("prop").content.proposal
    assert not effective_authority(s, 1).allows(Action(tool="deploy")).allowed
    # PRINCIPAL confirmation creates the real grant; proposal is `related`, not a source
    r2 = admit(
        s,
        grant(
            "g",
            Scope(tool="deploy"),
            Label.PRINCIPAL,
            2,
            sources=[],
            related=["prop"],
            writer="permission_prompt",
            writer_label=Label.PRINCIPAL,
        ),
        2,
    )
    assert r2.accepted_as_deontic
    assert effective_authority(s, 3).allows(Action(tool="deploy")).allowed


def test_harness_narrowing_accepted_widening_rejected():
    s = Store()
    admit(s, grant("g", Scope(tool="run_cmd", args={"cmd": "pnpm *"}), Label.PRINCIPAL, 0), 0)
    narrow = grant(
        "g2", Scope(tool="run_cmd", args={"cmd": "pnpm test"}), Label.HARNESS, 5, sources=["g"]
    )
    s.get("g").temporal.t_valid_to = 5
    assert admit(s, narrow, 5).accepted_as_deontic
    wide = grant("g3", Scope(tool="run_cmd"), Label.HARNESS, 6, sources=["g2"])
    r = admit(s, wide, 6)
    assert r.converted_to_claim and "not subsumed" in r.reason
    orphan = grant("g4", Scope(tool="run_cmd", args={"cmd": "pnpm t"}), Label.HARNESS, 7)
    assert admit(s, orphan, 7).converted_to_claim


def test_harness_narrowing_cannot_extend_expiry():
    s = Store()
    admit(
        s,
        make_entry(
            "g",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="j", expiry=10),
            Label.PRINCIPAL,
            0,
        ),
        0,
    )
    later = make_entry(
        "g2",
        DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="j", expiry=20),
        Label.HARNESS,
        1,
        sources=["g"],
    )
    assert admit(s, later, 1).converted_to_claim


def test_deny_and_revoke_need_harness_or_above():
    s = Store()
    admit(s, grant("g", Scope(tool="x"), Label.PRINCIPAL, 0), 0)
    d_llm = make_entry(
        "d1",
        DeonticPayload(kind=DeonKind.DENY, scope=Scope(tool="x"), principal="j"),
        Label.DERIVED,
        1,
        writer="llm",
        writer_label=Label.DERIVED,
    )
    assert admit(s, d_llm, 1).converted_to_claim
    d_h = make_entry(
        "d2",
        DeonticPayload(kind=DeonKind.DENY, scope=Scope(tool="x"), principal="j"),
        Label.HARNESS,
        2,
        sources=["g"],
    )
    assert admit(s, d_h, 2).accepted_as_deontic
    r_llm = make_entry(
        "r1",
        DeonticPayload(kind=DeonKind.REVOKE, target="g", principal="j"),
        Label.DERIVED,
        3,
        writer="llm",
        writer_label=Label.DERIVED,
    )
    assert admit(s, r_llm, 3).converted_to_claim


def test_non_deontic_passthrough():
    from decaymem.core import SemanticPayload

    s = Store()
    r = admit(s, make_entry("f", SemanticPayload(text="x"), Label.DERIVED, 0), 0)
    assert not r.accepted_as_deontic and not r.converted_to_claim and "f" in s
