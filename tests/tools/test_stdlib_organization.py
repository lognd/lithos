"""WO118b regression: the organization sweeps' repo-wide walks must
skip nested agent worktrees, venvs, and build output. The original
`check_prefix_reservation` walked `REPO_ROOT.rglob` unfiltered, so on
a checkout carrying live `.claude/worktrees/` (the normal coordinator
state) every std. package inside every nested worktree false-positived
as "misplaced" -- 42+ phantom failures on a green tree. These tests
build that exact layout in tmp and prove the sweep sees through it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.stdlib import organization


def _write_package(root: Path, rel_dir: str, name: str) -> None:
    """Drop a minimal magnetite.toml declaring `name` at `rel_dir`."""
    pkg = root / rel_dir
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "magnetite.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "1.0.0"\n'
    )


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repo: one legit std. package + the excluded-dir zoo.

    Layout mirrors the coordinator's main checkout: real content at the
    root, plus a nested agent worktree, a venv (root and apps/*), build
    output, and caches -- each carrying a std. package that would be a
    false positive if walked.
    """
    _write_package(tmp_path, "stdlib/std.good", "std.good")
    # The false-positive sources, each with a std. package inside:
    _write_package(tmp_path, ".claude/worktrees/wo999/stdlib/std.nested", "std.nested")
    _write_package(tmp_path, ".venv/lib/std.venv", "std.venv")
    _write_package(tmp_path, "apps/graphite/.venv/std.appvenv", "std.appvenv")
    _write_package(tmp_path, "target/debug/std.target", "std.target")
    _write_package(tmp_path, "node_modules/pkg/std.node", "std.node")
    _write_package(tmp_path, ".git/junk/std.git", "std.git")
    monkeypatch.setattr(organization, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(organization, "STDLIB_DIR", tmp_path / "stdlib")
    return tmp_path


def test_prefix_sweep_ignores_nested_worktrees_and_venvs(fake_repo: Path) -> None:
    check = organization.check_prefix_reservation()
    assert check.ok, check.note
    # Exactly the one legit package was seen -- none of the six
    # excluded-dir copies were even counted.
    assert check.count == 1


def test_prefix_sweep_still_flags_a_real_misplacement(fake_repo: Path) -> None:
    """The exclusion must not swallow real violations: a std. package
    in an ordinary (non-excluded) wrong location still fails."""
    _write_package(fake_repo, "examples/std.rogue", "std.rogue")
    check = organization.check_prefix_reservation()
    assert not check.ok
    assert "1 misplaced" in check.note


def test_prefix_sweep_flags_dir_name_mismatch(fake_repo: Path) -> None:
    """A std. package under stdlib/ whose directory name differs from
    its declared package name is still a violation."""
    _write_package(fake_repo, "stdlib/std.wrongdir", "std.mismatch")
    check = organization.check_prefix_reservation()
    assert not check.ok


def test_is_excluded_is_relative_path_semantics() -> None:
    """The predicate is applied to REPO_ROOT-relative paths: a nested
    worktree is excluded, but the pair must appear IN the relative
    path -- so a sweep running INSIDE a worktree (whose absolute path
    carries `.claude/worktrees`) does not exclude its own content."""
    assert organization.is_excluded(
        Path(".claude/worktrees/wo1/stdlib/std.x/magnetite.toml")
    )
    assert organization.is_excluded(Path(".venv/x/magnetite.toml"))
    assert organization.is_excluded(Path("apps/g/.venv/x/magnetite.toml"))
    assert organization.is_excluded(Path("target/x/magnetite.toml"))
    assert organization.is_excluded(Path("node_modules/x/magnetite.toml"))
    assert organization.is_excluded(Path(".git/x/magnetite.toml"))
    assert not organization.is_excluded(Path("stdlib/std.good/magnetite.toml"))
    assert not organization.is_excluded(Path("examples/demo/magnetite.toml"))


# --- WO-145/D257 ruling 2: structured citation strengthening --------------


def test_structured_citation_offenses_ignores_prose_only_rows() -> None:
    """A row with no `document` key never opted into the structured
    shape -- the existing prose-`reference` corpus (std.power/ti.logic/
    st.mcu) must see zero new offenses from this strengthening."""
    block = (
        '[[component]]\nkey = "x"\n'
        'evidence = { method = "catalog", trust_tier = "community", '
        'reference = "some prose citation" }\n'
    )
    assert organization._structured_citation_offenses(block) == []


def test_structured_citation_offenses_flags_incomplete_structured_row() -> None:
    """A row that DOES opt in (a `document` field present) but omits
    `page`/`table` is a real gap, not baseline debt -- it gates."""
    block = (
        '[[processor_abs_max]]\nkey = "x"\n'
        'evidence = { method = "catalog", trust_tier = "community", '
        'reference = "r", document = "SLASE54D", revision = "D" }\n'
    )
    offenses = organization._structured_citation_offenses(block)
    assert any("page" in o for o in offenses)
    assert any("table" in o for o in offenses)


def test_structured_citation_offenses_flags_empty_field() -> None:
    """An empty structured field (present but blank) is also an offense,
    not just an absent key."""
    block = (
        '[[processor_abs_max]]\nkey = "x"\n'
        'evidence = { method = "catalog", trust_tier = "community", '
        'reference = "r", document = "SLASE54D", revision = "D", '
        'page = 29, table = "" }\n'
    )
    offenses = organization._structured_citation_offenses(block)
    assert any("table" in o for o in offenses)


def test_structured_citation_offenses_passes_a_complete_row() -> None:
    """A fully-populated structured row (the ti.mcu shape) offends
    nothing."""
    block = (
        '[[processor_abs_max]]\nkey = "x"\n'
        'evidence = { method = "catalog", trust_tier = "community", '
        'reference = "r", manufacturer = "Texas Instruments", '
        'document = "SLASE54D", revision = "D", date = "2021-01", '
        'page = 29, table = "8.1 Absolute Maximum Ratings", '
        'url = "https://www.ti.com/lit/gpn/msp430fr5994" }\n'
    )
    assert organization._structured_citation_offenses(block) == []


def test_ti_mcu_shaped_records_pass_the_full_citations_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real `stdlib/ti.mcu` corpus (WO-145) was withdrawn 2026-07-16
    pending counsel review (owner rollback directive, D266) -- this
    exercises the same structured-citation strengthening against a
    SYNTHETIC ti.mcu-shaped record (invented values, not transcribed
    from any manufacturer datasheet) so the check_citations() code
    path stays covered end to end, not just via the in-process block
    helper above."""
    _write_package(tmp_path, "stdlib/std.synthetic_mcu", "std.synthetic_mcu")
    records_dir = tmp_path / "stdlib" / "std.synthetic_mcu" / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / "synthetic_mcu.toml").write_text(
        "# SYNTHETIC TEST DATA -- not transcribed from any source.\n"
        "[[processor_abs_max]]\n"
        'key = "synthetic_pin_voltage"\n'
        'evidence = { method = "catalog", trust_tier = "community", '
        'reference = "SYNTHETIC TEST DATA", '
        'manufacturer = "Synthetic Semiconductor Co.", '
        'document = "SYNTH-0001", revision = "A", date = "2026-07-16", '
        'page = 1, table = "1.1 Synthetic Ratings", '
        'url = "https://example.invalid/synthetic" }\n'
    )
    monkeypatch.setattr(organization, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(organization, "STDLIB_DIR", tmp_path / "stdlib")
    check = organization.check_citations()
    assert check.ok, check.note
    assert "0 uncited" in check.note
    # `.claude` alone (config, settings) is not the worktree pair.
    assert not organization.is_excluded(Path(".claude/settings.json"))
