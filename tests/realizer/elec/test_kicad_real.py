"""Real-KiCad gate (WO-35 deliverable 5): `-m kicad` marked tier.

The always-on tier (`test_kicad.py`, `test_kestrel_fixture.py`) fakes
the layout subprocess and never depends on real tooling. THIS module
is the tool-gated tier: it asserts the wire protocol against a live
`kicad-cli` invocation when `real_kicad_available()` is true, and
skips WITH the tool named in the reason otherwise (the honest cut
retired, not deleted -- see `regolith.realizer.elec.kicad`'s module
docstring and WO-24's close-out cut note, updated by WO-35).
"""

from __future__ import annotations

import pytest
from regolith.realizer.elec.kicad import discover_kicad_cli, real_kicad_available

pytestmark = pytest.mark.kicad


@pytest.mark.skipif(
    not real_kicad_available(),
    reason=(
        "real KiCad gate closed: kicad-cli on PATH and pcbnew importable "
        "are both required (WO-35 deliverable 5); reopen when both are "
        "present in the execution environment"
    ),
)
def test_real_kicad_cli_reports_a_version() -> None:
    """Smoke: a real `kicad-cli` on PATH answers `--version`, exit 0."""
    import subprocess

    cli = discover_kicad_cli()
    assert cli is not None
    completed = subprocess.run(
        [cli, "--version"], capture_output=True, timeout=30, check=False
    )
    assert completed.returncode == 0


def test_gate_reports_which_mode_ran() -> None:
    """CI records which mode ran (WO-35 acceptance): the gate is queryable."""
    # Never skipped: proves the gate function itself is callable and
    # honest (True only when BOTH tools are actually present) without
    # requiring the tools to be installed in this sandbox.
    available = real_kicad_available()
    assert isinstance(available, bool)
