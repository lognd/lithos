# WO-133 -- Power lowering + PowerNetPayload + claim routing (D248, charter 43)

Status: open (gated on WO-132)
Language: Rust (regolith-lower: the power payload + claim lowering)
  + Python (orchestrator routing). Schema: a PowerNetPayload is a NEW
  wire shape -- this is the ONE power schema bump; the coordinator
  adjudicates the window (D239/D225) before you touch SCHEMA_VERSION.
  Report the shape you need FIRST.
Spec: charter 43 secs. 1-3 (NORMATIVE); AD-42; D248; AD-25/D128
  (realized-domain IR precedent -- the flownet/frame payloads are your
  models); WO-32 (FlownetPayload, the closest analogue: a conserved-
  flow net with potentials); WO-48 (FramePayload); WO-112 (the
  lowering surface + claim routing by call form).

## Goal

A declared power system lowers to ONE canonical payload -- buses,
branches, sources, transformers, feeders, protective devices, loads
-- and every `elec.power.*` claim routes to a model over real
declared inputs (or defers by NAME with its missing inputs listed).

## Deliverables

1. `PowerNetPayload` (schemars, single-sourced in Rust): buses
   (id, nominal voltage, phases), branches (from/to, kind, impedance
   where declared, conductor + length for feeders), sources
   (available fault current, X/R, voltage -- each an OPTION, never a
   default: D250.3), transformers (kVA, %Z, X/R, vector group, taps),
   protective devices (frame, trip, interrupting rating, curve ref),
   loads (connected kVA, demand factor, continuous, class, motor
   fields). Follow the FlownetPayload idiom exactly.
2. Lowering: the WO-132 CST -> PowerNetPayload, with the discipline
   rules already checked at the front end (do not re-check).
3. Claim routing (the WO-112 call-form machinery): every
   `elec.power.*` claim reaches its model with real inputs, or defers
   with a NAMED reason listing the missing declared inputs. NO
   "typical value" fallback anywhere (D250.3 -- this is not a style
   preference; a guessed fault current is a lethal answer).
4. Census: the power claims appear in the rigor census like every
   other family (WO-117's census v2 shape), with their waivers in the
   D220.2 closed classes.
5. Determinism + goldens for the WO-132 positive design.
6. CROSS-STANDARD GUARD (D255): every std.power record declares its
   `standard_family` (IEC | NEC | ANSI/NEMA). A claim whose apparatus
   record and conductor/grounding record come from DIFFERENT standard
   families emits a coded diagnostic naming both families, both
   records, and the claim at stake. Mixing is NOT forbidden (real
   plants mix) -- mixing SILENTLY is. The author either declares the
   crossing deliberately through the existing honest-deferral ladder
   (`assume!` with a basis) or fixes it. Do NOT build conversion
   tables: naming the crossing is the deliverable; translating an IEC
   %Z into an ANSI assumption is the correctly-computed-lethally-wrong
   move D250 forbids.

## Acceptance

- The positive power design lowers to a byte-stable payload; every
  claim either routes to a model (WO-135) or defers BY NAME with its
  missing inputs.
- A source with no declared available fault current DEFERS the fault/
  withstand/arc-flash claims by name -- it never assumes a value.
- `make check` green; census enrolled.

## Escalation

The schema shape is the one thing you must NOT decide alone: report
the PowerNetPayload shape to the coordinator BEFORE bumping
SCHEMA_VERSION (D239). If claim routing needs a call form the WO-112
machinery cannot express, ledger it (F-WO133-n) rather than inventing
grammar.
