# Writing DFM/DRC rules

How to turn manufacturing knowledge -- "holes tear out near edges",
"unrelieved bends crack", "don't fan a signal out to more than eight
loads" -- into rules the compiler enforces on every design, every
build, with your name and your source on the error message.

This guide is written for two people sitting together: a domain
expert (a manufacturing engineer, a fab AE, a professor) who owns
the KNOWLEDGE, and a regolith user who owns the KEYBOARD. By the end
of a session you should have a rule pack: versioned, tested,
signable, publishable.

STATUS: the rule system is DESIGNED and work-ordered (WO-28,
`docs/implementation/21-rule-packs.md`); the engine and the
`regolith rules` commands land with it. Syntax below is the accepted
design; spellings are confirmed in WO-28's spec cycle. Normative
sources once landed: hematite/04 (`process`), cuprite/04 sec. 4,
regolith/12 sec. 3 (overrides).

## 1. Where rules live

Rules live in `process` modules -- the same modules that carry a
process's capability table. A pack is ordinary source, in a file,
in a package:

```
process sheet_metal_3xx:
    capability:
        thickness: [0.5mm, 3mm]
        min_bend_ratio: 1.6

    dfm:
        rule hole_edge_distance:
            forall h in holes
            demand: distance(h, nearest_edge(h)) >= 2 * h.diameter
            per: "DML handbook rev 4, hole tear-out"
            why: "holes near an edge tear out during forming"
            expect:
                pass: hole(diameter=3mm, edge_distance=8mm)
                fail: hole(diameter=3mm, edge_distance=4mm)
```

Three block kinds, one rule shape: `dfm:` (mechanical process
rules), `drc:` (board/layout rules), `erc:` (electrical rules --
drive/load, domain crossings). A design picks up a pack through its
stages (`stage cut: process=laser_cut(...)` -- the pack rides the
process) or project-wide attachment.

## 2. Anatomy of a rule (exhaustive)

| field | required | meaning |
|---|---|---|
| `rule <name>:` | yes | the citable identity: `waive dfm(<pack>.<name>)`, lockfile causes, E06xx provenance all use it |
| `forall <var> in <query>` | yes | what the rule ranges over -- any entity query: `holes`, `bends.where(not b.at_free_edge)`, `nets.where(kind=signal)` |
| `demand: <expr>` | one of demand/advise | the claim that must hold for every match; quantity-core expression; violation = error, release-gated |
| `advise: <expr>` | one of demand/advise | same, but a WARNING: rendered, never blocks release, never an obligation |
| `per: "<source>"` | strongly encouraged | the citation -- handbook section, IPC table, datasheet. Renders in the error a designer reads years from now |
| `why: "<reason>"` | yes | the one-line physical reason. This IS the error message's explanation |
| `resolves: <field> from free` | optional | marks this rule as the eager resolver for a `free` value: the engine picks the cheapest legal value and pins it in the lockfile as `cause: dfm(<pack>.<rule>)` |
| `expect:` with `pass:` / `fail:` | lint-required | minimal fixtures proving the rule fires correctly; `regolith rules test` runs them; a rule without both is a lint warning |

Severities: exactly two. `demand` errors; `advise` warns. There is
no priority arithmetic, no severity levels to rank, no rule
ordering. If you are unsure: `demand`. A wrongly-strict rule gets
waived visibly; a wrongly-lax rule fails silently forever.

Conditions vs exceptions -- the load-bearing distinction:

- A condition you can state GENERALLY belongs in the rule:
  `forall b in bends.where(not b.at_free_edge)` -- free-edge bends
  are exempt BY PHYSICS, so the rule says so.
- An exception for ONE design belongs in a `waive` in that design
  (section 5), where it is attributed, justified, and visible at
  release. Rules never enumerate customers.

## 3. The authoring workflow (the working session)

1. **Start from the checklist.** Every shop has one -- a wall
   poster, a PDF, a folklore list. Each line becomes a candidate
   rule.
2. **Write the `expect:` cases FIRST.** For "holes 2x diameter from
   edges": what passes (8mm away at 3mm dia) and what fails (4mm
   away)? If the expert cannot produce a failing example, the rule
   is not ready.
3. **Write the rule; run `regolith rules test <pack>`.** Green means
   the fixtures behave; the fail case firing is the moment the
   knowledge became executable.
4. **Run `regolith rules try <pack> <design-file>`** against a real
   design: every match, its verdict, and near-misses (within 20% of
   the limit) print. Near-misses are the interesting conversation --
   they are where the expert says "that one's actually fine" (loosen
   the rule) or "that's been failing in the field" (it was never a
   near-miss).
5. **Cite as you go.** Every `per:` you fill in now saves an
   archaeology session later. "Where did 2x come from?" should have
   an answer IN the error message.
6. **Sign and publish.** A pack is registry content: the expert
   signs it with their key (`quarry` trust machinery); consumers who
   designate that key get the expert's trust tier on every rule and
   resolution the pack produces. Authority travels with the
   signature, not the anecdote.

## 4. Worked examples

### Sheet metal (mech)

```
process press_brake_shop:
    capability:
        thickness: [0.5mm, 4mm]
        min_bend_ratio: 1.6           # inside radius / thickness

    dfm:
        rule min_bend_radius:
            forall b in bends
            demand: b.radius >= capability.min_bend_ratio * thickness
            resolves: b.radius from free
            per: "press pack table, 300-series stainless"
            why: "tighter radii crack the outer grain"
            expect:
                pass: bend(radius=2.4mm, thickness=1.5mm)
                fail: bend(radius=1.0mm, thickness=1.5mm)

        rule bend_relief:
            forall b in bends.where(not b.at_free_edge)
            demand: b.relief_cuts.count >= 1
            per: "DML handbook rev 4, fig 9.12"
            why: "unrelieved interior bends tear at the web"
            expect:
                pass: bend(interior, relief_cuts=1)
                fail: bend(interior, relief_cuts=0)

        rule hole_to_bend:
            forall h in holes
            demand: distance(h, nearest(bend_lines)) >= 2.5 * thickness
            per: "IPC-sourced? no -- shop scrap data, lot 2024-Q3"
            why: "holes inside the deformation zone go oval"
            expect:
                pass: hole(dia=4mm, to_bend=6mm, thickness=1.5mm)
                fail: hole(dia=4mm, to_bend=2mm, thickness=1.5mm)
```

Note `resolves:` on the first rule: a designer who writes
`radius=free` gets 2.4mm at 1.5mm stock, pinned in the lockfile as
`cause: dfm(press_brake_shop.min_bend_radius)` -- your rule is now
answering design questions, not just catching mistakes.

### PCB (elec)

```
process jlc_2l:
    capability:
        min_trace: 0.09mm
        min_space: 0.09mm
        min_drill: 0.2mm

    drc:
        rule fanout_limit:
            forall n in nets.where(kind=signal)
            demand: n.loads.count <= 8
            per: "family drive derating, cmos_3v3"
            why: "edge rates collapse past eight loads"
            expect:
                pass: net(kind=signal, loads=6)
                fail: net(kind=signal, loads=11)

        rule decouple_per_supply_pin:
            forall p in pins.where(role=supply, kind=in)
            demand: p.decouplers.where(dist <= 3mm).count >= 1
            why: "supply pins need local charge storage"
            expect:
                pass: supply_pin(decouplers_within_3mm=1)
                fail: supply_pin(decouplers_within_3mm=0)

        rule bus_length_match:
            forall b in buses.where(matched)
            demand: spread(routes(b).length) <= 2mm
            per: "IPC-2141A, matched group skew"
            why: "length spread eats the timing budget"
            expect:
                pass: bus(matched, length_spread=0.8mm)
                fail: bus(matched, length_spread=5mm)
```

The first two rules are STATIC -- checkable from the netlist, they
fire on every `regolith check`. `bus_length_match` references routed
geometry (`routes(...)`), so the engine automatically defers it: it
becomes an obligation that stays honestly "indeterminate" until
layout exists, then discharges or fails post-route. You never
declare this; the engine derives it from what the predicate touches.
A predicate referencing a fact NO layer can provide is a compile
error on the rule itself -- rules fail loud at definition time.

## 5. Overrides: the waive ladder

A rule violation blocks release. The ONLY way past it is a waive --
in the design's source, scoped, justified:

```
waive dfm(press_brake_shop.hole_to_bend) on cut.blank.wire_pass:
    basis: "prototype lot only; slight ovality acceptable, EV-31"
```

- `on <query>` scopes it to specific entities -- everything else
  the rule matches is still enforced.
- `basis:` is mandatory: the human reason, ledgered, diff-visible.
- Without evidence, the waive itself is release-gated (`--release`
  demands per-item acknowledgment). With `by <evidence>` it becomes
  a listed DEVIATION, permitted in release.
- A waive matching nothing is an error (stale waivers rot); a waive
  silently absorbing NEW failures is flagged from the lockfile diff.
- Nothing -- not a waive, not a hint, not a policy -- converts a
  violated result into a discharged one. Waives record acceptance
  of risk; they never rewrite physics.

What does NOT exist, deliberately: disabling a rule globally,
severity downgrades, priority tie-breaking, config-file opt-outs.
If a pack's rule is wrong, fix the pack (it is versioned source with
a test suite); if a design is a justified exception, waive it where
the justification is visible.

## 6. Levels and composition

| level | mechanism | example |
|---|---|---|
| vendor/registry pack | `stage ...: process=<pack>` | `jlc_2l`, `press_brake_shop` from the registry |
| project house rules | a local `process` module, attached project-wide | "we want 2.5x on hole-edge, tighter than the vendor's 2x" |
| one artifact | ordinary `require` block on the part/board | one-off demand; no rule machinery needed |

Composition is UNION: every attached pack's rules run. Two rules
with the same qualified name is a compile error (no silent
shadowing). A stricter house rule beside a looser vendor rule is
fine -- both run; the binding one governs. Loosening a vendor rule
is impossible by construction: don't attach the pack, or waive per
design. There is no third path, which is the point.

## 7. Checklist for a good rule

- [ ] Named so the waive reads well (`waive dfm(pack.name)` is a
      sentence someone will write).
- [ ] `forall` domain is the RIGHT entity set -- filters for
      physics-exempt cases live in the query, not in folklore.
- [ ] `demand` uses real quantities and units; the compiler
      dimension-checks it.
- [ ] `per:` names a source you would show an auditor.
- [ ] `why:` explains the failure mode, not the rule ("holes tear
      out", not "violates rule 7").
- [ ] `expect:` has at least one pass AND one fail.
- [ ] If the rule defines a minimum for something designers leave
      `free`, it carries `resolves:`.
- [ ] Numbers come from `capability:` when they are capability
      numbers -- one source, referenced, never copy-pasted into
      each rule.
