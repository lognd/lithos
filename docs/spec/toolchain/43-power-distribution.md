# Charter 43 -- Facility power distribution (cuprite's power discipline, in tandem with calcite) (AD-42)

Decided cycle 36 (D248/D249/D250, owner directive 2026-07-15; recon
F148). Machinery: WO-132 (front end), WO-133 (lowering + payload),
WO-134 (std.power records), WO-135 (models, both repos), WO-136
(the calcite tandem), WO-137 (the factory flagship). This charter
wins over the WO bodies it governs.

Owner's ask: cuprite must do non-PCB electrical work -- the power
system, transformers and all, for a large factory, designed in
tandem with calcite.

## 0. The finding that shapes the design (F148)

cuprite today is PCB-scale: nets, pins, packages, signal integrity,
firmware. `power:` exists only as a per-mode CONSUMPTION envelope.
There is no apparatus (transformer, switchgear, feeder, motor), no
ampacity, no voltage drop over a run of conductor, no fault current,
no coordination, no arc flash.

But the machinery is largely already here, and that is what makes
this an extension rather than a second language:

- AD-23 says there is ONE net core in `regolith-sem`, parameterized
  by a `NetDiscipline` (elec, fluid, civil circulation/load-path).
  Power distribution is a FOURTH discipline over that same core --
  buses are nodes, sources/transformers/feeders are edges, current
  (kVA) is the conserved flow, voltage is the potential. Kirchhoff
  is the conservation law the fluid discipline already runs.
- calcite already carries `civil.bearing_pressure`, embedment,
  spaces, and load paths -- so a 2.5 MVA transformer's mass landing
  on a slab is an EXISTING claim kind, not a new one.
- The regolith's contract model already lets one artifact carry
  roles in several domains (docs/README: "a board is simultaneously
  an electrical artifact and a mechanical one"). A substation is
  simultaneously electrical, structural, and thermal.

## 1. Power is a net discipline (D248; AD-42)

Added to AD-23's discipline set:

- **power** -- nodes are BUSES (service, switchgear, panelboard, MCC,
  branch); edges are SOURCES (utility service, generator),
  TRANSFORMERS, FEEDERS (conductor runs), and PROTECTIVE DEVICES;
  terminals join buses exactly as elec terminals join nets.

Discipline rules (the power analogue of "at most one voltage imposer
per analog net"):

1. Every energized subnet has AT LEAST ONE source imposer (utility
   service or generator). An unsourced load is a diagnostic, never
   an assumption.
2. A radial system has EXACTLY ONE source path per bus unless a TIE
   is explicitly declared (parallel sources, main-tie-main). An
   undeclared parallel path is a diagnostic -- accidental parallelism
   is how equipment gets destroyed.
3. Every ampacity transition (a feeder narrowing, a bus stepping
   down) has a declared protective device. An unprotected transition
   is a diagnostic.
4. Every load traces to a source (reachability -- the net core's
   existing reference-reachability check, reused).

Nothing above is new machinery. It is a `NetDiscipline`
parameterization plus a vocabulary.

## 2. The vocabulary (WO-132)

Apparatus declared as ordinary cuprite artifacts with power roles --
one word one idea, and every one of them is a thing an electrical
engineer already names:

`service` (utility point of delivery: available fault current, X/R,
voltage, phases), `generator`, `transformer` (kVA, primary/secondary
voltage, %Z, X/R, vector group, taps), `switchgear` / `panelboard` /
`mcc` (bus rating, bracing/withstand, main device), `feeder` (a
conductor run: conductor record, size, length, raceway, ambient,
grouping), `busway`, `breaker` / `fuse` / `relay` (frame, trip,
interrupting rating, curve), `motor` (HP/kW, code letter, service
factor, PF, efficiency), `load` (connected kVA, demand factor,
continuous flag, class).

Claim kinds (`elec.power.*`, the AD-37 dotted scheme):
`demand_load`, `voltage_drop`, `ampacity`, `fault_current`,
`withstand` (equipment rating vs available fault),
`transformer_loading`, `motor_start_dip`, `coordination`
(selectivity), `arc_flash` (incident energy, boundary, PPE
category), `grounding`, `power_factor`, `harmonics`.

## 3. Where the models live (D248.3, AD-37's boundary rule)

- lithos harness built-ins (closed-form pad checks, per AD-37):
  NEC Art. 220 demand load, conductor voltage drop, ampacity with
  temperature/fill derating (NEC 310.15), transformer %Z
  single-source bus fault, motor starting voltage dip, transformer
  loading, power factor.
- feldspar (numerics/certified, per AD-37): full load flow with
  multiple sources and contributions, IEC 60909 / ANSI short-circuit
  with motor contribution, IEEE 1584 arc-flash incident energy,
  protective-device coordination (curve intersection over real trip
  curves), harmonic distortion (IEEE 519).

The line is the same one AD-37 already draws and for the same
reason: a pad check tells you a feeder is obviously undersized; only
a certified solver tells you what an arc flash will do to a person.

## 4. The calcite tandem: sited equipment (D249; WO-136)

The point of doing this in lithos rather than in a power tool is
that the factory's electrical system and the factory's BUILDING are
one design. An item of apparatus is declared ONCE and carries roles
in several domains simultaneously:

- ELECTRICAL: its buses, its ratings, its claims (above).
- CIVIL (calcite): its MASS lands on a slab or pad -->
  `civil.bearing_pressure` (an EXISTING claim kind); its FOOTPRINT
  plus its NEC 110.26 WORKING CLEARANCE occupies space in an
  electrical room --> a spatial containment claim over calcite
  geometry (D102's containment machinery); its egress path from the
  working space is a calcite circulation claim (existing).
- THERMAL/FLUID (fluorite, where declared): its heat rejection is a
  load on the room's cooling.

New claim kind `elec.power.working_clearance(<apparatus>)`, checked
against the calcite space that contains it -- the first claim whose
subject is electrical and whose evidence is architectural. That is
the seam this whole charter exists to prove, and it is exactly the
cross-domain composition `regolith/10-domain-binding.md` designed.

Serviceability/egress and clearance failures are DIAGNOSTICS, not
warnings: a transformer that fits the room only if you cannot open
its door is a design error.

## 5. Safety honesty (D250 -- the rule that outranks convenience)

Power engineering kills people when it is wrong. The D224 provenance
law is not merely kept here; it is sharpened:

1. EVERY power model cites its standard AND edition (NEC/NFPA 70
   article, IEEE 1584-2018, IEEE 242, IEC 60909, NFPA 70E). An
   uncited power model may not ship.
2. THE TOOLCHAIN DOES NOT CERTIFY CODE COMPLIANCE and does not
   replace a licensed engineer's stamped study. It produces the
   calculation, its inputs, its provenance, and its evidence trail.
   Every power calc sheet and the power section of every report
   carries that statement, verbatim and unmissable.
3. AN UNVERIFIABLE INPUT IS A NAMED ABSENCE, NEVER A DEFAULT. The
   utility's available fault current and X/R ratio, a motor's
   locked-rotor code, a transformer's actual %Z: if it is not
   declared from a real source (utility letter, nameplate,
   datasheet), the claim DEFERS with the input named. There is no
   "typical value" fallback anywhere in this charter. A guessed
   fault current produces a correctly-computed, lethally-wrong
   answer.
4. ARC FLASH IS RELEASE-TIER ONLY THROUGH A CERTIFIED SOLVER
   (feldspar, IEEE 1584). A closed-form pad check may never present
   itself as an arc-flash study; the built-in tier, if any, is
   labeled a screening estimate and cannot discharge an
   `arc_flash` claim at release trust (INV-14's tier machinery,
   already built, is what enforces this).

## 6. Non-goals (named, with reopen criteria)

- Utility-side transmission/distribution planning (this charter is
  service-entrance-inward). Reopen: a real design needs it.
- Relay protection settings beyond coordination curves (differential
  schemes, distance protection). Reopen: a real substation design.
- Renewable/storage interconnection studies. Reopen: a real design.
- Replacing a PE's stamped study. NOT a reopen candidate -- see
  sec. 5.2; this is a permanent non-goal by design.
