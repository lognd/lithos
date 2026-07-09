# 26 -- Pattern and mechanism libraries (design charter; D144, cycle 27)

> Charter for reusable engineering patterns -- mechanical mechanisms,
> electrical circuit patterns, fluid sub-circuits, civil assembly
> families -- as stdlib content the toolchain RECOMMENDS, so the
> design cycle leans on proven building blocks instead of re-derived
> ones. Ledger rule: AD-28 (00-architecture.md). Machinery: WO-53.
> The owner's directive, verbatim in spirit: "a ton of mechanical
> mechanisms (and electrical patterns...) -- easily include them,
> recommend them in place of other things, make the design cycle
> easier on the engineer."

## 0. The gap this closes

Every discipline has a canon: four-bar linkages, lead screws, belt
drives, bearing arrangements; buck converters, level shifters,
sensor frontends, protection networks; relief legs and accumulator
stations; braced bays and rated wall types. Today an engineer
re-declares them from primitives and re-earns their verification
content each time. The regolith already has every mechanism needed
to package them (contracts with `spec:` laws, `parts`-kind packages,
two-halved model packs, the rule engine) -- what was missing is the
COMMITMENT: a curated library, and machinery that puts the library
in front of the engineer at the moment it helps.

## 1. Design decisions (load-bearing)

1. **A pattern is a package, not a language feature** (AD-28). Each
   pattern ships as ordinary registry content: an interface/contract
   (params, promises, a `spec:` behavioral law -- a four-bar's
   coupler law, a buck's conversion ratio), zero or more reference
   impls (`parts` kind), matings where the pattern is a connection
   discipline (bearing arrangements: fixed/floating), and the
   HARNESS HALF (model nodes discharging the pattern's claims --
   kinematic range/transmission-angle models, converter ripple
   models), co-versioned per the two-halves rule. Consuming a
   pattern buys verification content, not just structure. D64's
   kinematics closure ("v2 is a models-and-stdlib project") is
   exactly this project.
2. **The catalog** (initial curation; grows by ordinary publishing):
   `std.mech.mechanisms` -- four-bar/slider-crank/toggle linkages,
   lead + ball screws, belt/chain/gear drives, bearing arrangements,
   flexure pivots, detents/latches, counterbalances.
   `std.elec.patterns` -- converter topologies (buck/boost/flyback),
   level shifters, RC/active filters, sensor frontends (the
   NtcFrontend example generalized), protection (TVS/polyfuse/
   reverse-polarity), gate-drive and current-sense blocks.
   `std.fluid.circuits` -- relief/bypass legs, filter loops,
   accumulator/plenum stations, fill-and-drain manifolds.
   `std.civil.assemblies` -- braced-bay and moment-frame patterns,
   rated wall/roof/floor families (UL-shaped record sets),
   stair/egress cores.
3. **Recommendation is `advise:`, never louder** (AD-28; INV-3
   discipline). Pattern packs ship RECOGNITION RULES on the WO-28
   engine: `forall <var> in <query>` matching hand-rolled shapes
   (a pivot pair whose `couples:` law matches a four-bar; a
   discrete-transistor arrangement matching a level shifter; three
   fittings forming an unprotected pump inlet), with `advise:`
   naming the pattern, its contract, and what adopting it buys
   (models, DFM coverage, prior evidence). Advice is verdict-inert
   and never release-gated; the engineer stays sovereign. There is
   NO auto-substitution and NO priority arithmetic -- adopting a
   recommendation is an ordinary source edit.
4. **Ergonomics ride existing surfaces** (no new channels, AD-24):
   `magnetite new --template <pattern>` scaffolds a consuming
   artifact (WO-41 machinery); `regolith doc` renders a pattern
   DATASHEET from its contract (params, promises, spec law, model
   coverage, citations) -- the long-watchlisted "connection
   datasheet" view lands here; the LSP completes pattern contracts
   from imported packs like any interface. `regolith explain
   <advice-code>` prints the recognition rule's `why:`/`per:`.
5. **Trust and provenance unchanged**: pattern packs are signed like
   any pack (INV-14/28); a pattern's models carry citations and
   calibration (feldspar-side where numeric); recognition rules
   carry `per:` citations to the design literature (Shigley,
   Sclater & Chironis, Horowitz & Hill, Idelchik, AISC) exactly as
   DFM rules cite handbooks.

## 2. What already carries it

Contracts + `spec:` (regolith/04), packages/registries (regolith/11
-- the `parts` kind was built for this), the rule engine + `advise:`
severity (AD-21), scaffolding + docsgen (WO-41), the plugin seam
(AD-26), signature/model machinery for the harness halves. This
charter adds CONTENT and curation discipline, plus one engine
convenience WO-53 must verify exists: recognition rules may match on
contract/connection STRUCTURE (the query surface already exposes
entities, matings, and config couplings -- if a needed predicate is
missing, WO-53 escalates per AD-22 rather than growing a side query
path).

## 3. Non-goals (reopen criteria attached)

- Auto-substitution / refactoring tools that rewrite source into a
  pattern: reopen only on owner demand; the recommendation names the
  edit, the human makes it.
- A pattern DSL: patterns are ordinary declarations; a
  meta-language would violate D60's no-host-language rationale.
- Exhaustive catalogs at launch: the catalog grows by publishing;
  WO-53 ships the seed set (sec. 4) and proves the machinery.

## 4. Acceptance shape (what WO-53 must prove)

One pattern per leg, end to end: `std.mech.mechanisms.four_bar`
(contract + spec law + range/transmission-angle model + a
recognition rule that flags a hand-rolled pivot pair in a corpus
fixture) and `std.elec.patterns.level_shifter` (contract + reference
impl + a recognition rule flagging the discrete equivalent);
`magnetite new --template` scaffolds each; `regolith doc` renders
both datasheets; all advice verdict-inert by test.
