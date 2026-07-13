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
    # `.claude` alone (config, settings) is not the worktree pair.
    assert not organization.is_excluded(Path(".claude/settings.json"))
