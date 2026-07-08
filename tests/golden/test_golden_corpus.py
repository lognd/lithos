"""Golden corpus: WO-15 -- the compiler's structural output over
`examples/` is committed as data and must not drift silently.

Drives the facade only (`regolith.compiler.check`, AD-4/AD-11
placement), extracts the stable slice of `BuildOutcome.payload_json`
(see `_util.stable_snapshot`), and compares it to a committed JSON
file under `tests/golden/data/`. The property under test is
DETERMINISM and STABILITY -- not that the corpus is warning-free; the
WO-19 STATUS note records the pipeline as PARTIAL (resolutions=0,
~984 over-reported diagnostics on cubesat) and this suite captures
that noisy-but-deterministic state verbatim as golden.

Regeneration: never hand-edit a golden file. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_golden_corpus.py`
to rewrite them from the current compiler output, then diff-review
the change like any other generated artifact (schema-drift style,
AD-11).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from regolith import compiler

from ._util import stable_snapshot

_DATA_DIR = Path(__file__).parent / "data"

# name -> paths passed to `compiler.check`. Kept small and cheap
# (AD-11: golden corpus runs in the default `make check` gate) --
# one multi-file session (cubesat) plus a couple of single-file
# examples across both languages.
# The sdr project's parse-clean files, shared with the deferral suite
# (tests/golden/test_deferral_corpus.py imports this tuple so the two
# corpora cannot drift apart). The negative fixture directory
# (examples/systems/sdr_transceiver/negative/) is deliberately absent.
_SDR_CLEAN_PATHS: tuple[str, ...] = (
    "examples/systems/sdr_transceiver/adc_chain.cupr",
    "examples/systems/sdr_transceiver/board.cupr",
    "examples/systems/sdr_transceiver/clock_tree.cupr",
    "examples/systems/sdr_transceiver/contracts.cupr",
    "examples/systems/sdr_transceiver/dds_core.cupr",
    "examples/systems/sdr_transceiver/dsp_core.cupr",
    "examples/systems/sdr_transceiver/enclosure.hema",
    "examples/systems/sdr_transceiver/firmware.cupr",
    "examples/systems/sdr_transceiver/rf_frontend.cupr",
    "examples/systems/sdr_transceiver/sdr.cupr",
    "examples/systems/sdr_transceiver/sdr_ctl.cupr",
)

_CORPUS: dict[str, tuple[str, ...]] = {
    "cubesat": ("examples/systems/cubesat",),
    "gear_reducer": ("examples/tracks/hematite/gear_reducer.hema",),
    "buck_converter": ("examples/tracks/cuprite/buck_converter.cupr",),
    # Cycle-23 stress corpus (D119) + the D120 HDL fixture pairs (the
    # foreign .v/.sv/.vhd files are invisible to discovery by design).
    "sdr_transceiver": _SDR_CLEAN_PATHS,
    "hdl": ("examples/hdl",),
    # Cycle-23 stress corpus (D119): the D117 expert-ladder rungs in
    # the wild over a full mech+elec machine. `coolant.fluo` is
    # invisible to discovery today (the fluorite extension is not yet
    # in the regolith-syntax registry, WO-31) so passing the whole
    # directory is safe -- same "foreign file invisible by design"
    # shape as the hdl fixture pairs above.
    "cnc_router": ("examples/systems/cnc_router",),
    # Cycle-23 stress corpus (D119), fluorite-first: the .fluo files
    # are invisible to discovery today (WO-31), same shape as
    # cnc_router's coolant.fluo, so the whole directory is safe here.
    "espresso_machine": ("examples/systems/espresso_machine",),
    # WO-32 D6: standalone fluorite tracks exercising the D1-D5 fluid
    # lowering pipeline end to end (flownet elaboration -> payload-ref
    # obligations), now that `.fluo` is a registered, discovered
    # extension (WO-31) and the pipeline actually populates
    # `payload.flownets` (D4b). One simple, self-contained subnet
    # (garden_irrigation: plain Pipe edges + a named-list Orifice
    # orbit) and one richer one (dual_brake_circuit) keep this cheap
    # (AD-11: golden corpus runs in the default `make check` gate)
    # while covering more than one flownet shape.
    "fluorite_garden_irrigation": ("examples/tracks/fluorite/garden_irrigation.fluo",),
    "fluorite_dual_brake_circuit": (
        "examples/tracks/fluorite/dual_brake_circuit.fluo",
    ),
    # WO-33 deliverable 5: the two named fixtures exercising the
    # compute-claim/field-datum pipeline end to end -- a zone-indexed
    # producer/consumer pair (regen_chamber) and a config-indexed pair
    # with a slope projection (suspension_link). Both are honest
    # deferrals today (no field-producing model registered, D98's
    # interim); the golden freezes the FieldDatum ledger entries plus
    # the deferred obligation shapes.
    "regen_chamber": ("examples/tracks/hematite/regen_chamber.hema",),
    "suspension_link": ("examples/tracks/hematite/suspension_link.hema",),
}


def _golden_path(name: str) -> Path:
    return _DATA_DIR / f"{name}.json"


def _run_snapshot(paths: tuple[str, ...]) -> dict[str, object]:
    result = compiler.check(paths)
    assert result.is_ok, f"check({paths!r}) returned Err: {result}"
    outcome = result.danger_ok
    return stable_snapshot(outcome.payload_json)


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_golden_corpus(name: str) -> None:
    """Current stable output for one corpus member matches its golden file."""
    snapshot = _run_snapshot(_CORPUS[name])
    golden_path = _golden_path(name)

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {golden_path}")

    assert golden_path.exists(), (
        f"no golden file at {golden_path}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    expected = json.loads(golden_path.read_text())
    assert snapshot == expected, (
        f"golden drift for {name!r} -- if this is an intended compiler "
        "change, regenerate with REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_golden_corpus_is_deterministic(name: str) -> None:
    """Two independent `check()` calls over the same corpus member agree
    on the stable snapshot (a narrower, per-member INV-10 sanity check;
    the full-payload byte-identity assertion lives in
    `tests/invariants/test_inv_10_reproducibility.py`)."""
    first = _run_snapshot(_CORPUS[name])
    second = _run_snapshot(_CORPUS[name])
    assert first == second


@pytest.mark.parametrize(
    "name", ["fluorite_garden_irrigation", "fluorite_dual_brake_circuit"]
)
def test_flownet_payload_digests_are_deterministic(name: str) -> None:
    """WO-32 D6 (deliverable 5's leftover determinism-test item,
    fluorite/03 sec. 5: "payload determinism = geometry snapshot hash +
    record refs"): two independent `check()` calls over the same
    fluorite source produce byte-identical `flownet` payload content
    per flownet name -- a narrower, flownet-specific form of INV-10
    (see `tests/invariants/test_inv_10_reproducibility.py` for the
    whole-payload version)."""
    paths = _CORPUS[name]
    first = _run_snapshot(paths)
    second = _run_snapshot(paths)
    assert first["flownet_digests"] == second["flownet_digests"]
    assert first["flownet_digests"], (
        f"{name}: expected at least one elaborated flownet, got none"
    )


def test_sdr_transceiver_db_illegal_fixture_is_rejected() -> None:
    """The deliberate negative fixture (examples/systems/sdr_transceiver/
    negative/db_illegal.cupr, excluded from `_SDR_CLEAN_PATHS` above)
    MUST fail with E0104 (illegal logarithmic-unit sum) for BOTH the
    plain-literal spelling (`30dBm + 27dBm`) and the negative-literal
    spelling (`30dBm + -110dBm`) -- the common link-budget spelling
    that used to silently escape the L1 log-sum check (checks.rs
    `log_terms` bailed out on the unary-minus leaf instead of folding
    its sign into the term list)."""
    fixture = "examples/systems/sdr_transceiver/negative/db_illegal.cupr"
    result = compiler.check((fixture,))
    assert result.is_ok, f"check({fixture}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    bases = {
        "parse": 100,
        "references": 300,
        "contracts": 400,
        "instances": 500,
        "rule_packs": 600,
        "evidence": 700,
    }
    codes = [
        f"E{bases[diag['code']['family']] + diag['code']['offset']:04d}"
        for diag in payload["diagnostics"]
    ]
    assert codes.count("E0104") >= 2, (
        f"expected E0104 for both the plain and negative-literal log "
        f"sums in {fixture}, got {codes}"
    )
