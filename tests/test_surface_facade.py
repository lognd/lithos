"""Tests for the WO-159 `regolith.surface` UI read facade (AD-44).

The facade's whole contract is: (1) `__all__` names exactly the
charter-sanctioned set, no extras; (2) every name in `__all__` actually
resolves to a live symbol re-exported by value; (3) the module's own
source never reaches into `regolith.orchestrator`/`harness`/
`realizer`/`backends`/`compiler` except through the controlled import
lines at the top (the grep the WO close-out records).
"""

from __future__ import annotations

import re
from pathlib import Path

import regolith.surface as surface
from regolith.backends.artifact_index import ArtifactIndex, ArtifactRow, build_index
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.lockfile import parse as parse_lockfile
from regolith.orchestrator.orchestrate import BuildReport, StagedBuildReport

_EXPECTED_ALL = {
    "ArtifactIndex",
    "ArtifactRow",
    "build_index",
    "AuditIndex",
    "AuditRow",
    "AuditSummary",
    "CalcBook",
    "CalcSheet",
    "BuildReport",
    "StagedBuildReport",
    "Lockfile",
    "parse_lockfile",
}


# frob:tests python/regolith/surface.py kind="unit"
def test_all_names_exactly_the_charter_set():
    """`regolith.surface.__all__` lists exactly the charter's named
    types/functions -- no extras, nothing missing (WO-159 acceptance 1)."""
    assert set(surface.__all__) == _EXPECTED_ALL
    assert len(surface.__all__) == len(_EXPECTED_ALL)


# frob:tests python/regolith/surface.py kind="unit"
def test_every_all_name_resolves_on_the_module():
    """Every name in `__all__` is actually a live attribute of the
    module (a name could be listed but not bound if a re-export line
    were dropped by mistake)."""
    for name in surface.__all__:
        assert hasattr(surface, name), f"{name} listed in __all__ but not bound"


# frob:tests python/regolith/surface.py kind="unit"
def test_reexports_are_by_value_identity():
    """Each re-export is the SAME object as the underlying module's
    symbol (by value, never a reach-through proxy/wrapper)."""
    assert surface.ArtifactIndex is ArtifactIndex
    assert surface.ArtifactRow is ArtifactRow
    assert surface.build_index is build_index
    assert surface.BuildReport is BuildReport
    assert surface.StagedBuildReport is StagedBuildReport
    assert surface.Lockfile is Lockfile
    assert surface.parse_lockfile is parse_lockfile


# frob:tests python/regolith/surface.py kind="unit"
def test_facade_source_has_no_uncontrolled_reach_in():
    """`grep`-equivalent: `python/regolith/surface.py`'s own import
    lines are the only place it names
    `regolith.orchestrator`/`harness`/`realizer`/`backends`/`compiler`
    (WO-159 acceptance 2 / the close-out grep, re-checked here so a
    future edit that widens the reach fails a test, not just a
    close-out note)."""
    source = Path(surface.__file__).read_text()
    banned = re.compile(
        r"from regolith\.(orchestrator|harness|realizer|backends|compiler)"
    )
    hits = banned.findall(source)
    # Exactly the two controlled reach-in prefixes this facade is
    # allowed: regolith.orchestrator (lockfile + orchestrate) and
    # regolith.backends (artifact_index + calc read models).
    assert set(hits) == {"orchestrator", "backends"}


# frob:tests python/regolith/surface.py kind="unit"
def test_import_regolith_surface_succeeds():
    """`python -c "import regolith.surface"` succeeds (WO-159 acceptance
    1, the bare-import half)."""
    import importlib

    importlib.reload(surface)
