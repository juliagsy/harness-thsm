from decaymem.core import (
    Action,
    DeonKind,
    DeonticPayload,
    Label,
    Scope,
    Store,
    authority_subset,
    effective_authority,
)
from decaymem.core.entries import make_entry

PNPM_TEST = Action(tool="run_cmd", args={"cmd": "pnpm test"})
PNPM_WATCH = Action(tool="run_cmd", args={"cmd": "pnpm test --watch"})
DEL_TMP = Action(tool="delete_path", resource="tmp/cache")
DEL_SRC = Action(tool="delete_path", resource="src/x.py")
PUSH_MAIN = Action(tool="git_push", args={"branch": "main"})
PUSH_DEV = Action(tool="git_push", args={"branch": "dev"})


def test_valid_store_authority_over_time(valid_store: Store):
    a15 = effective_authority(valid_store, 15)
    assert a15.allows(PNPM_WATCH).allowed
    assert not a15.allows(DEL_TMP).allowed  # not yet granted

    a25 = effective_authority(valid_store, 25)
    assert a25.allows(DEL_TMP).allowed
    assert not a25.allows(DEL_SRC).allowed  # scope-adjacent, no creep
    assert a25.allows(PUSH_MAIN).allowed is False  # no grant at all

    a35 = effective_authority(valid_store, 35)
    d = a35.allows(PUSH_MAIN)
    assert not d.allowed and d.reason == "denied" and d.matched_deny == "d_push"
    assert a35.allows(PUSH_DEV).reason == "no grant"

    a45 = effective_authority(valid_store, 45)  # after harness narrowing
    assert a45.allows(PNPM_TEST).allowed
    assert not a45.allows(PNPM_WATCH).allowed
    assert "g_test" not in a45.grant_ids() and "g_test_v2" in a45.grant_ids()

    a55 = effective_authority(valid_store, 55)  # after revoke
    assert not a55.allows(DEL_TMP).allowed
    assert "g_tmp" not in a55.grant_ids()


def test_deny_dominates_grant():
    s = Store()
    s.add(
        make_entry(
            "g",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="git_push"), principal="p"),
            Label.PRINCIPAL,
            0,
        )
    )
    s.add(
        make_entry(
            "d",
            DeonticPayload(
                kind=DeonKind.DENY,
                scope=Scope(tool="git_push", args={"branch": "main"}),
                principal="p",
            ),
            Label.PRINCIPAL,
            1,
        )
    )
    a = effective_authority(s, 5)
    assert a.allows(PUSH_DEV).allowed
    dec = a.allows(PUSH_MAIN)
    assert not dec.allowed and dec.matched_deny == "d"


def test_expiry_and_uses():
    s = Store()
    s.add(
        make_entry(
            "g",
            DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="x"), principal="p", expiry=10),
            Label.PRINCIPAL,
            0,
        )
    )
    assert effective_authority(s, 9).allows(Action(tool="x")).allowed
    assert not effective_authority(s, 10).allows(Action(tool="x")).allowed
    once = make_entry(
        "o",
        DeonticPayload(kind=DeonKind.GRANT, scope=Scope(tool="y", max_uses=1), principal="p"),
        Label.PRINCIPAL,
        0,
    )
    assert once.deon.uses_remaining == 1
    s.add(once)
    assert effective_authority(s, 1).allows(Action(tool="y")).allowed
    once.deon.uses_remaining = 0
    assert not effective_authority(s, 1).allows(Action(tool="y")).allowed


def test_authority_subset_symbolic_and_universe(valid_store: Store):
    a25 = effective_authority(valid_store, 25)
    a55 = effective_authority(valid_store, 55)
    assert authority_subset(a55, a25)  # narrowing over time
    assert not authority_subset(a25, a55)
    universe = [PNPM_TEST, PNPM_WATCH, DEL_TMP, DEL_SRC, PUSH_MAIN]
    assert authority_subset(a55, a25, universe)
    assert not authority_subset(a25, a55, universe)
