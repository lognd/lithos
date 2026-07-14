# la_jig8 release residuals (WO-127, D206/D207)

Every `waive` in this project cites this memo. Each row below is an
ACCEPTED DEVIATION in one of the D220.2 closed classes -- a named
machinery residual, never a silenced verdict. Verdict math is
untouched (INV-2): a waived claim is still reported, still counted,
and never converts to `discharged`.

The jig exists to SURFACE gaps (charter 40 sec. 4, the WO-127
escalation clause), so these residuals are the exemplar's actual
output, not embarrassments to be hidden. The findings are ledgered
in `../README.md` as F-WO127-1..4.

## Class: no registered harness model for the claim kind (F126.1)

The registered elec-side model surface is: buck ripple / efficiency /
transient, lumped thermal, link budget, cost, workload realization.
The claims below are outside it. Each is authored with its inputs
declared and its arithmetic written out at the claim site -- the
NUMBERS are real and reviewable by hand; what is missing is a
registered model to evaluate them mechanically. None is fabricated as
discharged.

| Claim | Where | Why deferred |
|---|---|---|
| `v_tolerance` | `front_end.cupr` | no `elec.input_tolerance` model (F-WO127-2) |
| `edge_rate` | `front_end.cupr` | no `elec.rc_corner` model (F-WO127-2) |
| `sample_rate` | `la_jig8.cupr` | no `compute.sample_rate` model (F-WO127-2) |
| `channel_count` | `la_jig8.cupr` | no model consumes a structural count claim (F-WO127-2) |

## Class: module-import conformance edge (D195.3, addressable per D213)

A bare `import` carries no scalar window, so the conformance check has
nothing to refine. Project-wide, not jig-specific: every multi-file
project in the fleet carries these rows.

## Class: recorded rule-pack deferral surface

`interface_protection.vbus_inrush_protection` and
`dft_test_points.test_point_probe_clearance` have no engine input at
this tier -- the same two rows `mainboard_mx` carries. NOTE: these are
the ONLY two board_correctness rows waived. Every other rule the five
packs evaluated on this board PASSES for real, and the five that
initially violated (TVS on the USB pair, per-pin bypass on all six
RP2040 power pins, bulk per rail, the debug header, and the core-rail
test point) were fixed as DESIGN fixes -- no rule touched, no window
moved (guide 27 rule 3 / D224.3).

## What DISCHARGED for real

Recorded here so the waiver list is not mistaken for the whole story:

- `mcu_junction` (`la_jig8.cupr`) -- the RP2040 junction temperature,
  through the registered `thermo.temperature` lumped model over three
  declared inputs (ambient from the system's own boundary, power from
  the bus-power budget allocation, r_theta from the JESD51-3 package
  class). Real model, real inputs, real margin.
