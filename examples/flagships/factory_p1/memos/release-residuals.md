# factory_p1 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the
residual is genuinely unbounded (the wall), and the discharge path
that would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- D250.4 certified-tier-only claim kinds (no lithos built-in by design)

`withstand`, `coordination`, `arc_flash`, `grounding`, `harmonics`:
charter 43 sec. 3/D250.4 draws the boundary rule deliberately --
`regolith.harness.models.power` registers a model for exactly the
seven kinds WO-135 names and NO OTHERS; these five stay certified/
numeric-solver tier (feldspar's IEC 60909/ANSI short circuit, IEEE
1584 arc flash, protective-device coordination, IEEE 519 harmonics).
This is the acceptance test of D250.4: `arc_flash` in particular must
NEVER discharge through a lithos screening estimate wearing a
study's clothes. Every calc sheet these claims land on still carries
the D250.2 "this is not a stamped study" statement.

Retirement: feldspar's certified solver pack lands for the kind
(separate repo, its own WO); the claim then routes there instead of
deferring.

## Accepted -- D250.3 honest undeclared input (never a default)

`fault_standby`: the genset-side (`Tie`) transformer's nameplate `pct_z`
was never obtained at design time -- deliberately left undeclared, per
this WO's deliverable 2 (proving BOTH the declared-with-citation path,
`fault_main`, and the honest-undeclared path exist in the same plant).
`Model.discharge`'s shared port-check refuses with a named `InputError`
before `TransformerFaultCurrentScreeningModel.estimate` ever runs --
genuinely unbounded at build, by design, never a "typical" %Z
substituted.

Retirement: obtain the genset-side transformer's real nameplate %Z
(a physical nameplate read, not a design choice) and declare it.

## Accepted -- No std.civil section record for the named section key

`strength[RoofDeck]`/`strength[XfmrPad]`: `steel_deck_38mm`/
`equip_pad_300mm` name no record in `stdlib/std.civil/records/
sections.toml` (verified 2026-07-19: only `comp_deck_140mm` and the
w-shape/HSS/channel families are on file). The section key is this
design's own real read of a manufacturer's deck/pad product line;
never fabricated as a record that does not exist (D224.1 posture, the
same wall small_office's `DeckR`/`Deck2` waivers already carry).
`bearing_x` cascades from the same wall: `XfmrPad`'s reaction into
`FX` cannot resolve while its own section is unresolved
(`frame_reaction_unresolved`), a genuine machinery residual, not a
missing claim.

Retirement: add the real product-line records to `std.civil`'s
section table (a stdlib content WO, not this flagship's scope).

## Accepted -- Module-import conformance edge (D195.3/D213)

A bare `import` statement has no scalar comparison window for the
conformance machinery to check; a landed grammar/lowering increment
(D213) is the real retirement path, not this project's concern.
