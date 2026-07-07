# 04 -- Open questions (DRAFT v0; COPEN list)

- **COPEN-1 adoption + naming ratification**: this track is a
  PROPOSED draft (2026-07-07) answering `20-solver-abstraction.md`
  sec. 7 item 6. Needs a design-cycle adversarial read and owner
  ratification (name `calcite`, extension `.calc`). DEMAND UPDATE
  (2026-07-07): the feldspar dune-buggy stress test (G39) wrote
  three more circuits against this draft (coolant loop, fuel feed,
  brake hydraulics -- `../feldspar/examples/lithos/dune_buggy/`);
  the brake circuit exercises a cross-track pressure imposer and
  makes COPEN-5's compliance extraction load-bearing.
- **COPEN-2 net machinery reuse**: implement flownets by
  generalizing cuprite's net ledger (terminal ledger, reachability,
  imposer check are shape-identical) or as a parallel implementation?
  Leaning: one generalized net core in `regolith-sem` with per-track
  discipline plugins; duplication is the known failure mode.
- **COPEN-3 medium mixing**: v1 rejects mixed-media subnets;
  real systems mix (pressurant into propellant ullage). Needs a
  mixture model story (property records for mixtures? state-carrying
  nodes?) before pneumatic press systems are expressible.
- **COPEN-4 compressible networks**: v1 treats gases as
  incompressible-with-corners and screens choking; real GN2 systems
  need Fanno-line network solving. Vocabulary exists pack-side
  (feldspar fluids catalog); the question is whether claims need new
  forms (choked(edge) as a first-class predicate?).
- **COPEN-5 transient tier ownership**: water-hammer claims lower
  fine (event + peak vocabulary), but the discharging tier (MOC
  marching) needs Plenum capacitances and pipe wave speeds --
  elaboration must extract wall compliance from hematite tube walls
  (E, thickness). Decide the extraction rule's home.
- **COPEN-6 leak claims**: `leak(seal) < x scc/s` today lives in
  mech (torch igniter); a circuit-level leak budget (sum over
  fittings) wants calcite. One vocabulary, two owners -- decide the
  home before both grow one.
- **COPEN-7 line-up explosion**: `forall` over k valve states is
  2^k line-ups; swept-obligation coverage (sec. 7 item 2, per-axis)
  must handle discrete state domains, not just continuous boxes.
