"""Empty-project release guard: a source-less directory must never
pass `check`/`compile` (and therefore `build`/`ship`/`preview`, which
route through them) vacuously. Before this guard, `regolith build
--release` on a directory with no design source exited rc=0 with
`release_ok=True` -- a vacuous pass, verified live against a litter
directory this cycle. The fix lives at the ONE seam every caller
funnels through: `regolith.compiler._run` (`check`/`compile` share it).
"""

from __future__ import annotations

from pathlib import Path

from regolith import compiler


def test_empty_directory_refuses(tmp_path: Path) -> None:
    empty = tmp_path / "litter"
    empty.mkdir()
    result = compiler.check((str(empty),))
    assert result.is_err
    failure = result.danger_err
    assert failure.kind == "no_sources"
    assert str(empty) in failure.message


def test_directory_with_only_test_files_refuses(tmp_path: Path) -> None:
    project = tmp_path / "only_tests"
    project.mkdir()
    (project / "sample.test.cupr").write_text("# a test fixture, not source\n")
    result = compiler.check((str(project),))
    assert result.is_err
    assert result.danger_err.kind == "no_sources"


def test_directory_with_real_source_is_unaffected(tmp_path: Path) -> None:
    project = tmp_path / "real"
    project.mkdir()
    (project / "part.hema").write_text("part Widget:\n    param mass: mass = 1kg\n")
    result = compiler.check((str(project),))
    assert result.is_ok


def test_compile_also_refuses_on_empty(tmp_path: Path) -> None:
    empty = tmp_path / "litter2"
    empty.mkdir()
    result = compiler.compile((str(empty),))
    assert result.is_err
    assert result.danger_err.kind == "no_sources"


def test_no_paths_at_all_refuses() -> None:
    result = compiler.check(())
    assert result.is_err
    assert result.danger_err.kind == "no_sources"
