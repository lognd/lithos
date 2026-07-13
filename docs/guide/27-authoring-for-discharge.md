# Authoring for discharge

STATUS: WORKING. This is a design-authoring discipline, not a piece of
machinery -- it walks D224's three rules through two REAL corpus
changes from the cycle-35 enrichment campaign (WO-113, F133): a bearing
claim that discharged for real, and a wing-spar claim that discharged
by fixing the DESIGN after an honest violation.

Source: design-log `2026-07-13-cycle-35.md` D224 (the three rules)
and F133 (the campaign result: fleet-wide 45 -> 72 discharged, zero
violated); `examples/flagships/arm_a6/base.hema`;
`examples/flagships/uav_talon/airframe.hema`.

## The three rules (D224)

Adding a claim's missing inputs is legitimate design authoring, not
fabrication, under exactly three rules:

1. **PROVENANCE.** Every added value must be one of:
   - `record` -- pulled from a `std.*`/registry record (preferred; if
     the part is real, add the record);
   - `derivation` -- derived from already-declared design data, with
     the derivation written out in-file;
   - `citation` -- an external datasheet/handbook value, cited
     in-file.
   Never reverse-engineer a value from the model to force a margin
   positive -- a value chosen to make a claim pass without a source
   is fabrication, and refused.
2. **SAME-CHANGE BURN-DOWN.** When a claim discharges for real, its
   `waive` block is DELETED in the same change, and the acceptance
   memo/ledger is regenerated. A waiver still shadowing a real
   discharge is debt, not caution.
3. **HONEST FAILURES ARE FINDINGS.** If real declared inputs produce
   a `VIOLATED` verdict, the DESIGN is wrong -- fix it like an
   engineer would (resize the member, pick the bigger bearing),
   record the change. Never touch the model or the window to make
   the failure go away.

## Worked example: declaring inputs for a real discharge (arm_a6)

`examples/flagships/arm_a6/base.hema`'s J1 joint claims an ISO 281
L10 bearing life:

```
require Life:
    j1_bearing: mech.bearing.l10_hours(pair=dgb_6006,
                    under=interface_envelope(base.j1_seat),
                    c_rating=13200, p_load=500, speed_rpm=30,
                    p_exponent=3.0) >= 20000hr
```

Before WO-113, this claim was waived -- the model existed
(`bearing_life.py`, post-WO-72) but the inputs were not declared. The
enrichment pass added four scalars, each with its provenance recorded
in-file:

- `c_rating = 13200 N` -- **record**: the 6006 deep-groove ball's
  basic dynamic load rating, `stdlib/std.bearings/records/deep_groove_ball.toml`
  key `"6006"` (ISO 15:2011 boundary dims, manufacturer general-catalog
  rating).
- `p_load = 500 N` -- **derivation**: the J1 pair reacts the base's own
  derived 9.4 N*m tipping moment as a couple across the ~20mm
  effective seat/turret row spread (9.4 / 0.020 = 470N radial), plus
  ~26N axial from the arm's own declared mass arithmetic; Fa/Fr small
  enough that P = Fr per the ISO 281 X/Y rule, rounded up to 500N --
  the arithmetic is written out at the claim site, not asserted bare.
- `speed_rpm = 30` -- **citation**: the J1 rated max continuous joint
  speed spec (180 deg/s, desktop-arm class), a declared design spec,
  conservative-high for life since L10h scales as 1/n.
- `p_exponent = 3.0` -- **citation**: ISO 281:2007's own fixed ball-
  bearing load-life exponent, an engineering constant, not a design
  choice.

With all four declared, `l10_hours(...)` computes for real and the
claim discharges. The waiver that used to shadow it was deleted in
the SAME change (rule 2) -- the comment trail in `base.hema` records
this explicitly ("`j1_bearing` waiver DELETED (WO-113/D224.2): inputs
declared above with provenance").

## Worked example: an honest VIOLATED verdict forcing a design fix (uav_talon)

`examples/flagships/uav_talon/airframe.hema`'s wing spar originally
declared its structural depth `b` over `[3mm, 8mm]` -- a thin flat
strip. Declaring the real CS-23/MIL-HDBK-5J gust-case inputs (a cited,
literal 15 m/s vertical gust load case, the flagship's own
attention-list entry) and running the real cantilever-deflection model
against that domain produced a `tip_defl` violation by THREE ORDERS OF
MAGNITUDE: a 3mm x 3-8mm aluminum ribbon is not a wing spar under a
real gust load.

Rule 3 applies directly: the model and the 25mm deflection window are
both untouchable (D220.1). The fix is to the DESIGN:

```
# WO-113/D224.3 DESIGN FIX: b is the spar's structural DEPTH (the 3mm
# sheet stands on edge as the shear web), re-specced from the original
# [3mm, 8mm] flat-strip domain. Declaring the real gust-case inputs
# showed the flat strip VIOLATED tip_defl by three orders of
# magnitude -- a 3x3mm aluminum ribbon is not a wing spar. The fix
# matches the committed physical reading this repo's own tests
# already model: minimum depth 52mm is the smallest that clears the
# 25mm gust deflection limit with the model's 5% shear-term margin
# (I_req derivation at the claim site), 60mm the sheet-nesting cap.
b.length = in [52mm, 60mm] minimize
```

The domain widened from a flat 3-8mm strip to a real 52-60mm structural
depth -- the spar now stands on edge as a shear web, matching the
physical reading the repo's own test fixtures
(`tests/harness/test_wo70_uav_talon_discharge.py`,
`tests/test_flagship_uav_talon_sheets.py`) already assumed. The
derivation for the 52mm floor (`I_req` from the gust force, span, and
material modulus, with the model's own 5% shear-term margin) is
written at the claim site, not asserted. This is what "the corpus now
agrees with its own committed tests" (F133) means in practice: a
design authored to actually survive its own declared load case, not a
window loosened to let a bad design through.

## The pattern to follow

1. Find the claim's `waive` block and read WHY it is waived -- almost
   always a missing input, occasionally a genuine machinery gap
   (those stay waived, named, per D220.2(c)).
2. For each missing input, look for a `std.*` record first. If the
   part is real and no record exists, that is itself worth adding to
   `stdlib/` (see `docs/guide/28-growing-the-stdlib.md`).
3. If no record applies, derive the value from data the design
   already declares, and write the derivation out at the claim site
   -- a reviewer must be able to follow the arithmetic without
   re-deriving it themselves.
4. If neither, cite an external source in-file. If you cannot cite
   it, leave the input undeclared and the claim honestly waived
   (D224.1's refusal case) -- never guess a plausible-looking number.
5. Run the build. If it discharges, delete the waiver in the SAME
   change (never a follow-up commit -- a waiver shadowing a real
   discharge is the exact debt D224.2 forbids).
6. If it comes back VIOLATED, the design is telling you something
   real. Resize, re-pick, re-spec -- and record why, the way
   `airframe.hema`'s comment block does -- never touch the model.

## See also

- `docs/guide/26-reading-the-rigor-census.md` -- the fleet-wide view
  this authoring discipline feeds.
- `docs/guide/24-calc-package.md` -- the calc sheet a discharged claim
  produces, including how it renders each input's provenance tag.
- `docs/guide/28-growing-the-stdlib.md` -- adding the `std.*` record a
  claim's provenance should prefer.
