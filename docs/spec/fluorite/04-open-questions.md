# 04 -- Open questions (FOPEN ledger)

Ratification disposition (cycle 20, D93): the draft's COPEN-1/2/5/6/7
are CLOSED -- adoption+naming by D93 itself, net-core reuse by
D100/AD-23 (one generalized net core in `regolith-sem`, per-track
discipline plugins), compliance extraction by D93 (home: lowering,
03 sec. 1), leak-claim ownership by D93 (budget owner: the flownet;
component seal promises stay mech-side), and line-up coverage by D95
(discrete axes in the structured coverage encoding).

Completion disposition (cycle 27, owner closure directive): BOTH
remaining deferrals are now decided at spec level. The FOPEN queue is
empty with nothing deferred -- what remains is scheduled
implementation (WO-49, WO-52), not open design.

- **FOPEN-1 medium mixing** (was COPEN-3): the v1
  one-medium-per-subnet rule STANDS; its enforcement (the
  `impl FluidPort<medium=...>` binding + the per-edge compatibility
  check) is WO-49. The design question this deferral held open
  ("mixture property records vs state-carrying nodes") is ANSWERED
  (D142, cycle 27): **records, never state-carrying nodes**. Mixing
  enters through the declared-outlet `Mixer` component (02 sec. 3)
  -- a medium boundary whose sides are ordinary single-medium
  subnets and whose outlet properties are ordinary mixture records.
  State-carrying nodes were rejected because composition-as-network-
  state would break the static single-medium payload property and
  corner discipline together. The expected first case
  (pressurant-into-ullage) is a Mixer-shaped tank interface.
  Enforcement LANDED (WO-49): `impl FluidPort<medium=...>` bindings
  are harvested per component and checked against each flownet's
  own `medium=` header in `regolith_lower::fluid::check_flownet`
  (diagnostic `E0210`) -- pure front-end AST, no WO-32 lowering data
  needed after all. Implementation: WO-52 remains for the `Mixer`
  boundary treatment (parse + medium-consistency plugging into this
  same check). This entry flips to CLOSED when both land; nothing
  about it remains undecided.

- **FOPEN-2 compressible networks** (was COPEN-4): CLOSED at spec
  level (D141, cycle 27). The deferral's own question -- "whether
  new claim FORMS are needed beyond `choked`" -- is answered: NO.
  Gas-subnet dp/pressure/mdot claims are already the vocabulary;
  compressible network solving (Fanno-line tier, feldspar `fluids`
  catalog) is a DISCHARGE TIER selected by the margin through the
  regime machinery (`fluids.mach(edge)` screening tags via the D97
  channel), exactly the fidelity ladder every domain rides. 01's
  scope note is amended; the corpus gains a GN2 purge fixture
  exercising the regime route (WO-52); the pack-side tier is
  feldspar Phase 2 content (its WO-20). No reopen criterion needed
  -- there is nothing left to decide.
