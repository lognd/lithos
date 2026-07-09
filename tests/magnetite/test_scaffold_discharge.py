"""WO-53 template audit: every scaffolded template's example claim, run
through the real orchestrator ``build()`` (not just ``regolith check``).

`test_scaffold.py`'s `test_every_template_checks_green` only pins the
STATIC L0-L3 pass; it says nothing about whether the example claim can
ever discharge. This module closes that gap: for each template, scaffold
into ``tmp_path``, run a real ``build(..., BuildTier.RELEASE)``, and
assert what this engine honestly supports today (recorded in the WO-53
template audit report):

- ``mech``/``elec``: discharge >= 1 obligation and reach the release
  gate (``feldspar``'s ``mech.stiffness``/``elec.rail.lo``/``.hi``
  models) -- gated on ``feldspar`` being installed (mirrors
  ``tests/packs/test_feldspar_conformance.py``'s ``importorskip``
  posture: skip-if-absent, never fail-if-absent).
- ``system``: the mech/elec tracks discharge (feldspar-gated); the
  fluid track never does (see below), so ``release_ok`` stays False.
- ``fluid``: NEVER discharges in this engine -- `orchestrator/
  translate.py` has no fluid-claim lowering path at all (every fluorite
  `require` clause defers `unsupported_op`), independent of whether any
  `fluids.*` model is registered. Not feldspar-gated: this is a
  structural translate.py gap, reproduced with built-ins alone.
- ``four_bar``/``level_shifter``: instantiating the pattern generic
  always emits an unresolved `conforms` obligation (the WO-12
  conformance-window cut), so `release_ok` stays False regardless of
  the template's other claims; the added feldspar-backed claim still
  discharges on its own (feldspar-gated).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith.harness import default_registry
from regolith.harness.models import register_all
from regolith.harness.registry import ModelRegistry
from regolith.magnetite.scaffold import scaffold_project
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

pytest.importorskip("feldspar")


def _feldspar_installed() -> bool:
    """True when the real `feldspar` pack is discoverable in this env."""
    return "feldspar" in [p.name for p in default_registry().packs]


requires_feldspar = pytest.mark.skipif(
    not _feldspar_installed(), reason="feldspar pack not installed"
)


def _scaffold(tmp_path: Path, template: str) -> Path:
    result = scaffold_project("demo", template, parent=tmp_path)
    assert result.is_ok, f"scaffold({template}) returned Err: {result}"
    return result.danger_ok


@requires_feldspar
def test_mech_template_discharges_and_releases(tmp_path: Path) -> None:
    project = _scaffold(tmp_path, "mech")
    report = build((str(project),), BuildTier.RELEASE)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 1
    assert report_ok.release_ok is True


@requires_feldspar
def test_elec_template_discharges_and_releases(tmp_path: Path) -> None:
    project = _scaffold(tmp_path, "elec")
    report = build((str(project),), BuildTier.RELEASE)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 2
    assert report_ok.release_ok is True


def test_fluid_template_never_discharges(tmp_path: Path) -> None:
    """The structural translate.py gap: built-ins alone are enough to
    reproduce it -- no feldspar involvement, so not gated."""
    project = _scaffold(tmp_path, "fluid")
    registry = ModelRegistry()
    register_all(registry)
    report = build((str(project),), BuildTier.RELEASE, registry=registry)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged == 0
    assert report_ok.release_ok is False


@requires_feldspar
def test_system_template_mech_and_elec_tracks_discharge(tmp_path: Path) -> None:
    """The system template emits three files; the mech/elec tracks
    discharge, the fluid track never does (its own gap), so overall
    `release_ok` stays honestly False."""
    project = _scaffold(tmp_path, "system")
    report = build((str(project),), BuildTier.RELEASE)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 3
    assert report_ok.release_ok is False


@requires_feldspar
def test_four_bar_pattern_claim_discharges_but_release_blocked(
    tmp_path: Path,
) -> None:
    project = _scaffold(tmp_path, "four_bar")
    report = build((str(project),), BuildTier.RELEASE)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 1
    # The WO-12 conformance-window cut on the pattern generic itself
    # blocks the release gate regardless of the other claim.
    assert report_ok.release_ok is False


@requires_feldspar
def test_level_shifter_pattern_claim_discharges_but_release_blocked(
    tmp_path: Path,
) -> None:
    project = _scaffold(tmp_path, "level_shifter")
    report = build((str(project),), BuildTier.RELEASE)
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 1
    assert report_ok.release_ok is False
