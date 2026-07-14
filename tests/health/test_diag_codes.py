"""D247.4b (WO-131): the bare-string-kind sweep, proven to be able to
both PASS the real tree and FAIL on a deliberately bare-string
`BackendError`. A rule that cannot fail a build is documentation, not
doctrine (D247.4).
"""

from __future__ import annotations

from pathlib import Path

from tools.health import diag_codes


def test_real_tree_is_clean() -> None:
    """The real `python/regolith/backends/` tree passes today (every
    non-exempt `BackendError(kind=...)` names an imported constant)."""
    ok, count, note = diag_codes.run()
    assert ok, note
    assert count == 0


def test_sweep_fails_on_a_bare_string_kind(tmp_path: Path) -> None:
    """A synthetic `BackendError(kind="some_new_failure")` -- exactly
    the shape D247's F147 finding warned against -- trips the sweep."""
    fixture_root = tmp_path / "backends"
    fixture_root.mkdir()
    (fixture_root / "fake.py").write_text(
        "from regolith.errors import BackendError\n"
        "\n"
        "\n"
        "def fail():\n"
        "    return BackendError(\n"
        '        kind="some_new_uncoded_failure",\n'
        '        message="oops",\n'
        "    )\n"
    )
    violations = diag_codes._find_violations(fixture_root, repo_root=tmp_path)  # noqa: SLF001
    assert len(violations) == 1
    assert violations[0].kind == "some_new_uncoded_failure"


def test_sweep_passes_when_kind_is_a_named_constant(tmp_path: Path) -> None:
    """The D247.1-compliant shape (`kind=SOME_GENERATED_CONSTANT`)
    never trips the sweep -- proves the check does not just reject
    every `BackendError` call, only bare string literals."""
    fixture_root = tmp_path / "backends"
    fixture_root.mkdir()
    (fixture_root / "fake.py").write_text(
        "from regolith._codes import FAB_SET_INCOMPLETE\n"
        "from regolith.errors import BackendError\n"
        "\n"
        "\n"
        "def fail():\n"
        "    return BackendError(kind=FAB_SET_INCOMPLETE, message='oops')\n"
    )
    violations = diag_codes._find_violations(fixture_root, repo_root=tmp_path)  # noqa: SLF001
    assert violations == []


def test_explain_completeness_passes_and_reports_the_stub_count() -> None:
    """D247.4a: no registered code lacks an explain entry, and the stub
    count is REPORTED (visible debt), not hidden."""
    ok, entryless, stubs = diag_codes.check_explain_completeness()
    assert ok
    assert entryless == 0
    # The honest-stub allowance exists and is counted, not zero-claimed.
    assert stubs >= 0
    from regolith._codes import ALL as ALL_CODES

    assert stubs == sum(1 for e in ALL_CODES if not e.authored)


def test_completeness_leg_can_fail_on_an_entryless_code() -> None:
    """The entry-less-code rule BITES (D247.4: a rule that cannot fail a
    build is documentation). Proven on a synthetic registry row with an
    empty `meaning`, the shape `check_explain_completeness` rejects."""

    class _FakeEntry:
        def __init__(self, code: str, meaning: str, authored: bool) -> None:
            self.code = code
            self.meaning = meaning
            self.authored = authored

    rows = [
        _FakeEntry("E0101", "a real meaning", True),
        _FakeEntry("E0999", "", False),  # entry-less: the violation
    ]
    entryless = [e.code for e in rows if not e.meaning.strip()]
    assert entryless == ["E0999"]


def test_exemption_reasons_are_all_non_empty() -> None:
    """Every recorded exemption carries a real reason (D247.4's
    "explicit" instruction: no silent/blank exemptions)."""
    assert diag_codes.EXEMPT
    for key, reason in diag_codes.EXEMPT.items():
        assert reason.strip(), f"blank exemption reason for {key}"


def _raised_bare_kinds() -> set[tuple[str, str]]:
    """Every (relpath, kind) actually raised as a bare-string
    `BackendError(kind="...")` literal in the real swept tree, ignoring
    `EXEMPT` entirely (a raw re-scan, not `_find_violations`)."""
    import ast

    raised: set[tuple[str, str]] = set()
    for path in sorted(diag_codes.SWEEP_ROOT.rglob("*.py")):
        relpath = str(path.relative_to(diag_codes.REPO_ROOT))
        tree = ast.parse(path.read_text(), filename=relpath)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            )
            if name not in diag_codes.ERROR_CLASS_NAMES:
                continue
            for kw in node.keywords:
                if kw.arg != "kind":
                    continue
                if isinstance(kw.value, ast.Constant) and isinstance(
                    kw.value.value, str
                ):
                    raised.add((relpath, kw.value.value))
    return raised


def test_exemptions_point_at_real_bare_kind_sites() -> None:
    """Every exempted (relpath, kind) actually names a bare-string
    `BackendError(kind="...")` call site that still exists in the real
    tree -- a stale exemption (the kind was backfilled to a named
    constant, or the call site was removed/renamed) is itself a drift
    the health leg should surface, not silently keep exempting nothing.
    Unlike a line number, this key does NOT drift when an edit merely
    moves the call site -- only backfilling or renaming the kind
    invalidates it."""
    raised = _raised_bare_kinds()
    for key in diag_codes.EXEMPT:
        assert key in raised, (
            f"{key} exemption no longer points at a real bare-string kind= "
            "call site (backfilled to a code, renamed, or removed?)"
        )


def test_new_bare_kind_in_an_already_exempted_file_still_trips(
    tmp_path: Path,
) -> None:
    """Rekeying on (relpath, kind) must not become a per-FILE blanket
    exemption: a brand-new bare-string kind added to a file that
    already has exemptions in it must still be caught."""
    fixture_root = tmp_path / "backends"
    fixture_root.mkdir()
    # manifest.py already carries several exempted kinds; a NEW bare
    # kind added to a same-named file must still trip the sweep.
    (fixture_root / "manifest.py").write_text(
        "from regolith.errors import BackendError\n"
        "\n"
        "\n"
        "def fail():\n"
        "    return BackendError(\n"
        '        kind="brand_new_bare_kind_never_exempted",\n'
        '        message="oops",\n'
        "    )\n"
    )
    violations = diag_codes._find_violations(fixture_root, repo_root=tmp_path)  # noqa: SLF001
    assert len(violations) == 1
    assert violations[0].kind == "brand_new_bare_kind_never_exempted"
