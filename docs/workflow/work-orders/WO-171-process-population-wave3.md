# WO-171 -- process population wave 3: the long tail (D269 item 4)

Status: open (Depends: WO-168 [process record schema]; independent of
  WO-169/WO-170 -- may run in parallel with either)
Language: data (TOML/stdlib records), same convention as WO-169/170.
Spec: D269 item 4 ("...then the long tail"); D269 sec. 3 taxonomy +
  the same-day amendment's additions (powder metallurgy, ECM, gear
  cutting, hydroforming, hemming, incremental forming, cold heading,
  swaging, FSW, laser/ultrasonic welding, electroless/PVD/CVD coating,
  induction hardening/austemper/martemper/solution-treat-age are
  covered by WO-169 already where they overlap heat-treat -- do NOT
  duplicate those; this WO's scope is everything the rollup's
  coverage table lists that WO-169/170 do not already own); the full
  process-research rollup `procres/rollup.md` coverage table (the
  denominator: 100 entries across 12 families, 100/100 `done` in
  dossier form -- this WO converts the REMAINING dossier entries, not
  already claimed by WO-169/170, into `std.process` records).

## Goal

Convert every remaining process-research dossier entry (per
`procres/rollup.md`'s coverage table, minus the families WO-169 and
WO-170 already own) into a real `std.process` record + DFM
check-set: the rest of subtractive (milling, turning, drilling,
reaming, boring, tapping/threading, honing, lapping, superfinishing,
sawing, broaching, sinker EDM if not already folded into WO-169,
waterjet, laser, plasma, oxy-fuel, ECM, gear hobbing/shaping), the
rest of sheet (shearing, blanking/punching, deep drawing, roll
forming, spinning, hydroforming, hemming/seaming, ISF), casting (sand,
investment, die, permanent mold, centrifugal, continuous, lost foam),
molding (injection, blow, rotational, thermoforming, compression,
transfer, RIM), powder (PM press+sinter, MIM, HIP), additive (FDM/
FFF, SLA/DLP, SLS, DMLS/SLM, binder jetting, DED, material jetting),
joining (TIG, MIG, stick, resistance spot, brazing, soldering,
adhesive, threaded fasteners, riveting, press fits, FSW, laser
welding, ultrasonic welding), bulk forming (open/closed-die forging,
extrusion, rolling, wire/bar drawing, cold heading, swaging), and the
rest of surface (anodizing, electroplating, electroless plating,
passivation, painting, powder coating, black oxide, PVD/CVD).

## Deliverables

1. One `ProcessRecord` + `DfmCheckSet` per remaining named process,
   each citing its matching `procres/*.md` dossier entry file and
   section, `provenance` populated honestly (the rollup's own
   estimate: ~78% of ALL 100 entries are `gek`-dominant -- expect
   most of this wave's records to be `gek`, mark them so plainly, do
   not manufacture citations to look better-sourced than the dossier
   found them to be).
2. Named refusals carried over verbatim from the dossier's own
   refusal list (ISO 965/286 fit-and-thread tables, AGMA/ISO 1328
   gear-tolerance tables, ASM Metals Handbook casting/forging tables,
   MPIF PM density/property tables, SAE J442/J443 Almen-strip tables,
   ASTM A967/AMS 2700 passivation specs, NEC Ch.9 Table 1/NEC 358.24
   verbatim tables, ISO/ASTM 52900 category text) -- do not
   re-litigate whether to refuse; the dossier already decided, this
   WO's job is to encode that decision in the schema's
   `named_refusal` posture field per process.
3. The two out-of-scope-for-per-part-DFM entries the rollup flags
   (continuous casting, rolling, wire/bar drawing -- "stock-supply"
   not "part-manufacturing") get records too (for completeness of the
   100-entry denominator) but their `DfmCheckSet` may be empty/marked
   N/A with a note explaining why, rather than forcing a fabricated
   per-part check onto a stock-supply process.

## Non-goals

- No re-opening the D266 counsel items (stays open per D269 item 2's
  explicit non-relitigation).
- No families beyond the rollup's 100-entry denominator (if a
  genuinely new family surfaces during this wave, that is a new
  ticket, not silent scope growth here).

## Acceptance

- Every dossier entry not already claimed by WO-169/WO-170 has a
  corresponding `std.process` record (grep-checkable count: 100 total
  dossier entries minus WO-169's ~13 minus WO-170's ~9 equals this
  WO's expected record count, +/- the family-overlap notes above --
  reconcile the exact count in this WO's close-out against the
  rollup's own table rather than assuming the arithmetic here is
  exact).
- Provenance distribution roughly matches the rollup's own estimate
  (~78% gek, ~8% pd_gov-anchored, ~20% carrying a named refusal,
  buckets overlapping as the rollup itself notes) -- a wildly
  different distribution in the landed records is a signal something
  was mis-sourced and should be checked before closing.
- `make check` green.
</content>
