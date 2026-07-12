# WO-105 -- Fleet ship campaign: every example builds --release and ships

Status: open
Language: corpus authoring (design sources, magnetite manifests,
  memos) + small Python where a named discharge gap is trivially
  closable; NO verdict-machinery changes
Spec: D206/D207/D210 (the campaign law -- read them FIRST);
  regolith/12 sec. 3 (waive rules 1-9); D195/F116 (never invent
  windows); each flagship's WO close-out ledger (WO-70..94) for
  the wall-by-wall residual inventory.

## Goal

Every D210 fleet project reaches `build --release` green and ships
a complete package; every `examples/tracks/**` single-file design
builds `--release` green. Green means PROVEN OR ACCEPTED: first
discharge what the machinery honestly can, then author scoped,
memo-backed `waive` deviations for the genuinely-unbounded
residuals, per-project.

## Deliverables

1. Provisioning: `magnetite.toml` for dune_buggy, reaction_wheel,
   regen_engine (mirror a flagship manifest's shape); DELETE
   `examples/systems/cnc_router` (D210.2) retargeting its
   deferral golden at the flagship; fix any stale prose refs.
2. Per-project discharge pass BEFORE any waiver: re-run release
   builds on current master (post WO-98..104 merges); for each
   remaining deferral check the ledgered walls -- if a record,
   given, or claim-form fix the specs already permit closes it
   (e.g. declaring an explicit impl-side bound where a real
   narrowing exists, adding a missing std record row WITH a
   citable source, targeting a load the payload can carry),
   apply it as ordinary corpus authoring. NEVER fabricate a
   bound that the design does not actually assert (D195).
3. Waiver authoring: for each genuinely-unbounded residual,
   a SCOPED `waive` in the owning design file with: target +
   `on` scope, a basis naming the wall (WO ledger / design-log
   citation), `by doc(<memo>)` evidence -- one memo per project
   (`memos/release-residuals.md`) written per D207's required
   content (accepted set, why unbounded, retirement path).
   Prefer many scoped waivers over one blanket waiver; unscoped
   only where the claim genuinely fails artifact-wide.
4. Ship specs: each fleet project gets/updates its `--spec` (or
   auto-derivation coverage) so the package contains every
   applicable family (drawings, 3d, bom, instructions, boards,
   firmware/hdl, cost) -- absence must be the named-absent kind,
   not silence.
5. Evidence refresh (D210.5): regenerate every checked-in
   `.regolith/build/build_report.json` at RELEASE tier on final
   master; regenerate goldens; REVIEW diffs (no new error-level
   rows; acceptance counts are visible census data, not noise).
6. Close-out ledger: per-project table (obligations / discharged
   / deviated-accepted / notes) recorded in this WO file -- the
   fleet census the cycle closes on.

## Acceptance criteria

- Every fleet project: `regolith build --release` rc=0 with
  release_ok=true AND `regolith ship` emits a `ship --verify`-
  clean package.
- Every tracks corpus file: `--release` green (in-file waivers
  permitted); negative corpus unchanged-failing; registry/hdl
  parse clean.
- Zero fabricated bounds/windows: every acceptance traceable to a
  basis + memo; the census table distinguishes proven from
  accepted per project.
- `make check` green fleet-wide.
