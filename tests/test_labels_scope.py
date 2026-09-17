from decaymem.core import Action, Label, Scope, derive_label, meet


def test_lattice_order():
    assert Label.UNTRUSTED < Label.DERIVED < Label.HARNESS < Label.PRINCIPAL


def test_meet_and_derive():
    assert meet([]) == Label.PRINCIPAL
    assert meet([Label.PRINCIPAL, Label.HARNESS]) == Label.HARNESS
    # L1: an LLM writer can never produce above DERIVED
    assert derive_label(Label.DERIVED, [Label.PRINCIPAL]) == Label.DERIVED
    # a summary of tool output is UNTRUSTED
    assert derive_label(Label.DERIVED, [Label.UNTRUSTED, Label.PRINCIPAL]) == Label.UNTRUSTED


def test_scope_matches():
    s = Scope(tool="delete_path", resource="tmp/**")
    assert s.matches(Action(tool="delete_path", resource="tmp/cache/x"))
    assert not s.matches(Action(tool="delete_path", resource="src/main.py"))
    assert not s.matches(Action(tool="read_file", resource="tmp/x"))
    assert not s.matches(Action(tool="delete_path"))  # resource required
    any_tool = Scope()
    assert any_tool.matches(Action(tool="whatever"))
    arg = Scope(tool="run_cmd", args={"cmd": "pnpm test*"})
    assert arg.matches(Action(tool="run_cmd", args={"cmd": "pnpm test --watch"}))
    assert not arg.matches(Action(tool="run_cmd", args={"cmd": "pnpm build"}))
    assert not arg.matches(Action(tool="run_cmd"))  # missing arg


def test_scope_subsumes():
    broad = Scope(tool="run_cmd", args={"cmd": "pnpm *"})
    narrow = Scope(tool="run_cmd", args={"cmd": "pnpm test"})
    assert broad.subsumes(narrow)
    assert not narrow.subsumes(broad)
    assert Scope().subsumes(broad)
    assert not Scope(tool="run_cmd").subsumes(Scope(tool="git_push"))
    # glob-vs-glob only when identical (conservative)
    assert broad.subsumes(Scope(tool="run_cmd", args={"cmd": "pnpm *"}))
    assert not broad.subsumes(Scope(tool="run_cmd", args={"cmd": "pnpm t*"}))
    # max_uses: unlimited subsumes limited, not vice versa
    assert Scope(tool="x").subsumes(Scope(tool="x", max_uses=1))
    assert not Scope(tool="x", max_uses=1).subsumes(Scope(tool="x"))
    assert not Scope(tool="x", max_uses=1).subsumes(Scope(tool="x", max_uses=2))
    # resource
    assert Scope(tool="d", resource="tmp/**").subsumes(Scope(tool="d", resource="tmp/cache"))
    assert not Scope(tool="d", resource="tmp/**").subsumes(Scope(tool="d"))
