# Overrides, Hints, Waivers: The Expert Ladder

> Substrate spec. Added in cycle 3. The languages are intent-based and
> best-practice by default -- but a designer who KNOWS better must be
> able to force any decision. This doc is the single doctrine for how:
> every escape hatch states **who** decided (a source position in the
> diff), **why** (evidence or basis), and **what** it affects (scope);
> and none of them can forge a proof.

## 1. The safety property

> **No mechanism in this doc can convert `violated` into
> `discharged`.** Overrides supply better inputs, narrow choices, or
> record accepted risk. The margin-driven evidence math
> (`07-claims-and-evidence.md`) is untouchable from source.

The mechanism, not just the slogan (INV-2 in `13-invariants.md`):
evidence is keyed to content-addressed obligations (claim + subject +
givens + record hashes), so rungs that change inputs or choices
*re-key the obligation* -- old evidence simply stops applying; rungs
6-7 attach **acceptance records** that reference the evidence hash and
never modify status -- the ledger and report always show the true
status plus the acceptance. Hints are verdict-invariant by
construction (INV-3). This is what makes the escape hatches safe to
hand to experts: the worst a wrong override can do is produce a
*recorded, attributed, release-gated* acceptance of risk -- never a
silent green build.

## 2. The ladder

Ordered by how much the human claims to know. Prefer the lowest rung
that expresses the intent.

| rung | construct | claims | proof impact |
|---|---|---|---|
| 1 Assert | literal value (incl. `within [lo, hi]`) | "this is true" | none: all checks run against the asserted value |
| 2 Pin | lock family: `locked:`, `use`, `sequence:`, `merge()`, `hosted_on` | "choose this, not your favorite" | none: checks unchanged; can cause spurious failure, never silent pass |
| 3 Hint | `@hint(...)`, `policy: prefer` | "try this first / this regime holds" | none: droppable by construction |
| 4 Override data | `override <record> by <evidence>` | "the registry fact is wrong here" | checks re-run on new data; evidence clause mandatory |
| 5 Force a model | `model=<impl>` on a claim or connection | "discharge with this model" | margin math unchanged: a forced model that cannot close the margin yields `indeterminate`, not a pass |
| 6 Assume | `assume!(expr, basis=)` | "treat as true; I accept the risk" | obligation accepted without evidence; ledgered; release-gated |
| 7 Waive | `waive <target> [on <scope>]: basis: ... [by <evidence>]` | "I accept THIS failure" | violated/indeterminate stands, explicitly accepted; ledgered |

Rungs 1-5 keep the design fully proven (possibly against
human-supplied facts). Rungs 6-7 are honest holes: visible state, not
optimistic lies.

## 3. `waive` (rung 7) -- the construct

```
waive Manufacture.makeable on milled.deep_bore:
    basis: "wire-EDM vendor confirmed capability; quote Q-2214"
    by test(first_article_fai_112)         # optional evidence clause

waive drc(min_annular_ring) on vias.where(net=vdd_core):
    basis: "fab-confirmed 0.1mm ring at this drill class, mail 3/12"
```

Rules:

1. **Targets** are named claims (`Group.claim`) or rule-pack rules
   (`dfm(rule)`, `drc(rule)`, `erc(rule)`). `on <query>` scopes the
   waiver to specific entities; an unscoped waiver covers the claim
   wherever it fails *in the declaring artifact* -- prefer scoped.
2. **`basis:` is mandatory** -- free text, but it lands in the ledger
   and the diff, so it is socially load-bearing.
3. **Evidence upgrades a waiver to a deviation.** With a `by` clause
   (test report, vendor letter as hash-pinned catalog doc), the waiver
   is a *deviation*: permitted in `--release`, still listed in the
   evidence ledger. Without evidence it is release-gated exactly like
   `assume!` (per-item CLI acknowledgment).
4. **A waiver that stops matching anything is an error** (stale
   waivers do not accumulate silently -- the E07xx family).
5. **The match set is lockfile-recorded, and growth is loud** (INV-12):
   an unscoped waiver that starts covering a *new* failure surfaces in
   the lockfile diff and as a build warning naming the new members --
   a waiver cannot quietly absorb regressions.
6. **A waiver targets a rule's verdict, never its resolution duty.**
   Waiving `dfm(min_bend_radius)` on an entity whose radius is `free`
   is an error: the variable needs another source -- assert the value
   (rung 1) alongside the waiver.
7. **Deviations face trust floors** (INV-14): the evidence on a
   waiver must meet the `trust:` floor of the claim group it waives,
   or the waiver stays release-gated.
8. **Optional expiry**: `expires: <date>`. Past it, the waiver behaves
   as absent (the failure returns) and the waiver itself is a
   stale-waiver error until removed or renewed -- concessions cannot
   outlive their justification.
9. The CLI `--waive Group.claim` remains for *exploration only*: it
   never persists, and a build carrying CLI waivers says so in its
   report. Durable acceptance has exactly one form: this construct, in
   source, in the diff.

## 4. `policy:` (rung 3 hard/soft split) -- preferences and global objectives

```
policy:                          # system/assembly level, or per budget
    prefer vendor(ti) over vendor(onsemi)
    prefer package(sot23)
    forbid package(bga)
    minimize distinct_values     # global objectives: lexicographic,
    minimize total_cost          #   after all claims are satisfiable
```

- **`prefer` is soft**: it reorders candidate exploration in the
  conflict-driven allocation search (`07` section 7). It can never
  cause a failure. When a preference is decisive for a resolved
  decision, the lockfile row carries a `policy: prefer(...)`
  annotation next to the cause -- the defaults test's third prong.
- **`forbid` is hard**: it intersects allocation domains, like a
  structure boundary. Infeasibility caused by a forbid names the
  forbid in the diagnostic.
- **Global objectives** live here -- at policy altitude, never on
  individual variables (this resolves [SOPEN-4]; the retired
  `minimize(count_distinct)` was a global objective misfiled on a
  local variable). Declared order = lexicographic priority, applied
  strictly after claim satisfiability; per-variable
  `minimize`/`maximize` remain the innermost tier. Budget `allocate:`
  is unaffected: it remains the *local share-splitting policy inside
  one budget*, not a global objective.

## 5. Existing rungs, restated as ladder members

- **Rung 1** is the value-source grammar itself (`03-value-sources.md`):
  a literal is the override of `free`/`derived`/`allocated`. Asserting
  a value the system would have computed differently is not fought --
  it is checked (a literal envelope smaller than the derived
  requirement fails conformance; larger is conservative and fine).
- **Rung 2** is the lock family (`09-build-and-lockfile.md` section 6),
  including `locked: pinmux(u_mcu.uart2.tx): pa2` -- the one position
  where a package pin may appear in design source.
- **Rung 4** is trait-coherence override (`09` section 5): immutable
  registry history, evidence-cited local shadowing.
- **Rung 5** names what the connection escalations always were
  (`model=fea_contact`, `stiffness=measured`,
  `model=spice_extracted`): pinning the discharge path. Generalized:
  any claim may carry `model=<impl>`; forcing an *expensive* model is
  harmless (conservative); forcing a *cheap* one cannot lie because
  its error still charges against the margin.
- **Rungs 6-7** are the honest-deferral pair (`07` section 8) plus
  this doc's `waive`.

## 6. The audit surface

Every rung leaves all four trails:

| trail | carries |
|---|---|
| source | the construct itself: author, location, basis -- reviewable in the diff |
| lockfile | the resolved consequence with cause (+ `policy:` annotation when a preference was decisive) |
| evidence ledger | assumes, waivers, deviations, overridden records with their evidence hashes |
| `--release` gates | refuses evidence-less rungs 6-7 except per-item acknowledgment; deviations (evidence-carrying waivers) pass but are listed |

The review question for any surprising build is always answerable in
one place per trail: *what changed* (lockfile diff), *who accepted
what* (ledger), *on what basis* (source).

## 7. The representational twin

This doc covers overriding *decisions*. Overriding *representations*
-- hand-writing a lower lowering level, or linking foreign content
(Verilog, STEP, prebuilt binaries, hand-written G-code) against a
contract -- is `08-lowering-architecture.md` section 4: manual
lowering and `extern` linkage, where the system checks conformance
instead of deriving. Same philosophy: the expert is never fought,
the contract is never silently shadowed, and the trail is complete.
