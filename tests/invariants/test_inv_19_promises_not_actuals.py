"""INV-19 Promises, not actuals (substrate/13-invariants.md).

Ledger statement:
    **No system-level verdict depends on an artifact's internals except
    through a declared escalation edge.** Mechanism: the L2 solver reads
    contract IR only (promises, connection models, boundary); artifact
    internals are not reachable from that input set. Argument: by
    construction of the L2 input set, an artifact edit that leaves the
    contract surface unchanged leaves every promise-backed system
    obligation content-identical (INV-1 content addressing), so it drives
    zero system-obligation re-runs.

Mechanism provided by: WO-12 (SystemNode: boundary/reserves/flows/
targets) + the WO-19 lowering pipeline (content-addressed obligation
keys, INV-1/INV-10). This module is part of the WO-17 invariant suite: a
spec change that alters INV-19's proof argument must change this module
in the same commit.

Ledger test: "edit an artifact internal without a contract change; assert
zero system-obligation re-runs absent escalation edges." Realized here as
a two-build content-addressing fixture, mirroring the INV-27 technique:
the same design is built twice, differing ONLY in an artifact internal (a
part's `material`, a field no system-level claim reaches). The internal
edit genuinely moves the part's own content identity and its part-level
obligations, yet every SYSTEM-level obligation key (the assembly's
promise-backed `require`) is byte-identical across the two builds -- zero
system-obligation re-runs. A teeth control edits a PROMISED contract-
surface bound (the assembly mass budget) and shows the system obligation
key DOES change, so the invariance above is not vacuous.

Future work (left honest, NOT faked): the "except through a declared
escalation edge" clause -- where `model=`, `measured`, or
`spice_extracted` legitimately makes a system verdict depend on an
internal -- needs escalation-edge lowering that does not exist yet
(WO-12/escalation). The primary promises-not-actuals guarantee is sound
and non-vacuous WITHOUT it; the escalation-opt-in negative control
remains future work.
"""

from __future__ import annotations

import json

from regolith import compiler

from tests.golden import _util

# The one assembly in the fixture is the system node; its promise-backed
# `require` obligations are the SYSTEM-level obligations INV-19 governs.
_SYSTEM_NODE = "Rig"

# A minimal design: one part with a genuine internal (`material`) and a
# part-level self-check that reads it, plus an assembly (the system node)
# whose sole system-level claim is a promise-backed mass budget. `{mat}`
# is the artifact internal; `{mass}` is the promised contract-surface
# bound. Neither the assembly boundary nor its `require` reaches `material`.
_DESIGN = """interface Load<n: int>:
    x: n

part Widget:
    material: {mat}
    stage machined: process=cnc_mill(axes=3, rect(10mm, 10mm, 10mm))
        then:
            body = Contour(WProfile, keep=inside, through)
    impl Load<n=5> for self:
        x = 5
    require Strength:
        peak_load: mech.stress.von_mises < material.sigma_y / 1.6

profile WProfile:
    walk:
        from base_plane
        line right
        line up
        line left
        close
    constraints:
        a.length = 8mm
        b.length = 6mm

assembly Rig:
    parts:
        w: Widget
    boundary:
        ambient: [-10degC, 50degC]
    require SystemMass:
        total: mech.mass(all) <= {mass}
"""


def _build(tmp_path, name, *, mat, mass):  # type: ignore[no-untyped-def]
    """Write one design variant into its own dir and return its payload."""
    d = tmp_path / name
    d.mkdir()
    (d / "m.hem").write_text(_DESIGN.format(mat=mat, mass=mass), encoding="ascii")
    payload = json.loads(compiler.check((str(d),)).danger_ok.payload_json)
    return payload


def _system_obligation_keys(payload) -> list[str]:  # type: ignore[no-untyped-def]
    """Sorted content keys of the SYSTEM-level obligations -- those whose
    subject is the system node (the assembly). These are the keys whose
    stability across an internal edit is the promises-not-actuals
    guarantee: an unchanged key is a cache hit is zero re-runs (INV-1)."""
    scope_of = {s["hash"]: s["scope"] for s in payload["snapshots"]}
    return sorted(
        _util._obligation_key(ob)
        for ob in payload["obligations"]
        if scope_of.get(ob["subject_ref"]) == _SYSTEM_NODE
    )


def test_inv_19_internal_edit_drives_zero_system_reruns(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Editing an artifact internal (a part's `material`, unreachable from
    any system-level claim) leaves every system-level obligation key
    byte-identical -- zero system-obligation re-runs -- even though the
    part's own content identity and part-level obligations do change. The
    system verdict is backed by promises, never the artifact's actuals
    (INV-19)."""
    base = _build(tmp_path, "base", mat="AL6061_T6", mass="210g")
    variant = _build(tmp_path, "variant", mat="AL7075_T6", mass="210g")

    base_sys = _system_obligation_keys(base)
    variant_sys = _system_obligation_keys(variant)

    # There is a system-level obligation to protect (guards against a
    # vacuous "no system obligations at all" pass).
    assert base_sys, "expected at least one system-level obligation"
    # THE GUARANTEE: the internal edit perturbs no system-level obligation
    # key -- zero re-runs of promise-backed system evidence.
    assert base_sys == variant_sys

    # Non-vacuity: the internal edit is REAL -- it moves the part's own
    # content-addressed snapshot and thus its part-level obligations. The
    # system-level invariance above is genuine isolation, not a global
    # no-op.
    base_full = _util.stable_snapshot(
        compiler.check((str(tmp_path / "base"),)).danger_ok.payload_json
    )
    variant_full = _util.stable_snapshot(
        compiler.check((str(tmp_path / "variant"),)).danger_ok.payload_json
    )
    assert base_full != variant_full, (
        "internal edit must move some artifact-level identity, else the "
        "system-level invariance is vacuous"
    )


def test_inv_19_promised_bound_edit_reruns_system_obligation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Teeth control: editing a PROMISED contract-surface bound (the
    assembly's mass budget) DOES change the system-level obligation key --
    a legitimate re-run. This proves the primary test is non-vacuous: the
    system obligation genuinely tracks the promise surface, so its
    invariance under an internal edit is a real guarantee, not an artifact
    of keys that never move."""
    base = _build(tmp_path, "base", mat="AL6061_T6", mass="210g")
    tighter = _build(tmp_path, "tighter", mat="AL6061_T6", mass="150g")

    base_sys = _system_obligation_keys(base)
    tighter_sys = _system_obligation_keys(tighter)

    assert base_sys, "expected at least one system-level obligation"
    assert base_sys != tighter_sys, (
        "editing a promised contract-surface bound must re-key the "
        "system obligation -- else the primary test proves nothing"
    )
