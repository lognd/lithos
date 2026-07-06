# cuprite Vocabulary Sketch

> cuprite spec 0.11. Draft keyword tables in the same format as
> `../hematite/04-vocabulary.md`, subject to the same vocabulary principles
> (one word, one idea; blocks declare / sources resolve / claims prove /
> selectors select; ASCII canonical). Keywords marked **[S]** are
> regolith vocabulary shared verbatim with hematite -- by design, most of
> the load-bearing words. Everything unmarked is a sketch, not settled.

## A. Shared registries

All of section A in the mech vocabulary applies (`namespace`, `quantity`,
`zones`, `class`, `properties:`, `contact`, `process`, `capability:`,
`signature`, `impl <sig> by`), plus:

| keyword | position | purpose |
|---|---|---|
| `component` | top-level | concrete catalog part: datasheet limits as intervals, `f(T)`/`f(V)` derating, package(s), behavioral model refs |
| `family` | top-level | logic family / IO standard record: voltage windows, drive classes (the fit-table analog of ISO 286) |
| `protocol` | top-level | bus/link contract pack: roles, timing templates, conformance claim set |

## A2. Rule packs [SETTLED, cycle 18]

The regolith rule grammar, shared verbatim with hematite
(`../hematite/02-language.md` sec. 10, `04-vocabulary.md` sec. I5;
elec binding `04-structural-layer.md` sec. 4). All [S] except the
block words, which are per-track jargon:

| keyword | position | purpose |
|---|---|---|
| `drc:` / `erc:` | in `process` | the elec rule-pack blocks: layout-facing (DRC) and electrical (ERC) rules (`dfm:` is the mech block) |
| `rule <name>:` [S] | in a pack block | one named, citable rule (`waive drc(<pack>.<name>)`, lockfile causes, E06xx provenance) |
| `forall <var> in <query>` [S] | first rule line | the match domain: the settled claim quantifier over an entity query |
| `demand:` / `advise:` [S] | in `rule` | error vs warning severity; exactly two, no priority arithmetic |
| `resolves: <field> from free` [S] | in `rule` | eager resolver of a `free` slot; `cause: drc(<pack>.<rule>)` |
| `per:` / `why:` [S] | in `rule` | citation and one-line physical reason (the diagnostic text) |
| `expect:` / `pass:` / `fail:` [S] | in `rule` | in-pack fixtures; both cases lint-required |

Built-in net discipline (shorts, single-driver, one voltage-imposer;
`03` sec. 2) is E03xx core semantics, never pack content -- see `04`
sec. 4 note 3.

## B. Intent layer

| keyword | position | purpose |
|---|---|---|
| `system` | top-level | the top artifact: intents, flows, boundary, reserves, connections, budgets, claims |
| `intents:` | in `system` | named intent declarations from the verb vocabulary (inline or block form) |
| `sense`, `actuate`, `communicate`, `interact`, `convert` | boundary verbs | product functions at the boundary; `communicate` is boundary-only -- internal buses are derived, never declared |
| `compute`, `store` | interior verbs | computation/retention demands with quality parameters |
| `indicate`, `probe`, `debug_access` | verbs (std.debug) | debug/bring-up intents, used inside targets |
| `flows:` | in `system` | `a -> b` typed flow; ledger-checked; realization derived and lockfile-caused |
| `discard` | flow target; terminal statement | explicit sink for intentionally unconsumed outputs AND intentionally unconnected terminals (`discard u1.dnc`) -- one idea, registered overload |
| `boundary:` [S] | in `system` | the only human-asserted physical truth: supply, ambient, EMC class, life, duty |
| `reserves:` / `target ... of` / `draws:` [S] | system / top-level | set-asides and additive overlays (debug builds) |
| `workloads:` | in `computer` | declared computation demands (`loop`, `stream`, `event`, `batch`) |
| `realizes <intent>[, ...]` | on workloads | ties a workload to the compute intents it serves; exactly-one-realization ledger + demand implication at L2 (05-computer-track sec. 1; resolved EOPEN-15) |
| `hosted_on <part>` | on synthesized-block bindings; inline on intents | pins which part hosts derived content: a `by spec` impl on a programmable part (EOPEN-17, settled cycle 6) or an intent's realization on an artifact (the D48 partition pin); otherwise planner-allocated |
| `exposing op: {..}` [S] | in `system` | system-level operating-mode config variable (regolith `04` sec. 5: exposers are connections, blocks, or the system) |
| `computer` | top-level | a computation artifact: workloads + architecture + bindings |
| `architecture` | in/for `computer` | promised resources (`executor`, `memory`, `mover`, `fabric`), `peripherals:` demand vector, `schedule:` |
| `image` | top-level | firmware artifact: `realizes:` a schedule contract; toolchain-realized; map/stack/WCET measured |

## C. Behavioral layer

| keyword | position | purpose |
|---|---|---|
| `block` | top-level | an **abstract functional contract**: ports, params, `spec:`, claims |
| `ports:` | in `block` | contract roles: `supply(in\|out)`, `reference`, `analog()`, `digital()`, `clock()`, `bus()`, `adc/dac/comparator` |
| `params:` [S] | in `block` | impl-chosen internal variables, value-source-typed; `<...>` params are caller-chosen (regolith `04-contracts.md`) |
| `spec:` [S] | in `block` | the behavioral specification (what any impl must satisfy) |
| `impl <Block> by spec / composing / circuit / vendor(ref) / extern(ref, fmt)` [S] | top-level | concrete realization; equivalence to `spec:` is a T3 obligation; realizable specs get implicit `by spec`; named with `as` when several coexist; `extern` links foreign sources/netlists (regolith `08` sec. 4) |
| `on <event>:` | in `spec` / impl bodies | clocked/evented discrete body; `<=` non-blocking; RTL-equivalent subset (was `process on`; renamed -- `process` is the [S] manufacturing module) |
| `continuous:` | in `spec` / impl bodies | DAE relations over quantities; `'` = d/dt |
| `nets:` | in `impl by circuit` | terminal joins (`swn: (u1.sw, l1.a)`); v1 discipline: terminal ledger, reference reachability, one voltage-imposer, supply-short check (03-behavioral sec. 2; resolved EOPEN-16) |
| `arbitrate` | net construct | explicit shared-drive discipline (tri-state, open-drain wired-AND, `bidir(granted_by=...)`, `parallel(<share>)`); the ownership join |
| `domain` | on clocks/supplies | declares a clock or voltage domain (a frame [S]) |
| `reset <event>` | on `on <event>:` bodies | declared reset membership |
| `strap` | component port role | boot/config pin role; must be bound or explicitly defaulted, never floating |
| `board` | top-level | the physical artifact: stage pipeline (fab, assembly, program) |
| `load(image_ref)` | in `programmed` stage | hash-pinned firmware/bitstream load as a construction step |

## D. Contract layer ([S] almost entirely)

`interface`, `frame:`, `roles:`, `demands:` (the regolith block name;
mech binds it as `tolerances:`, elec keeps `demands:`), promise slots,
`structure:`, `refines`, `mating`, `align:`, `dof:`-ledger analog,
`couples:`, `preload:` (bias/termination state), `effects:`,
`capability:`, `require <Group>:` -- all regolith, with elec promise
slots:

| slot | purpose |
|---|---|
| `drive:` | output capability (source/sink, edge rates) |
| `timing:` | setup/hold/prop promises relative to a clock frame |
| `power:` | consumption envelope per mode |
| `protocol:` | conformance promise against a `protocol` pack |

Stdlib matings sketch: `NetBind`, `BusAttach<proto>`, `LevelShift<fam_a,
fam_b>`, `cdc_sync`/`async_fifo` (domain crossings), `SupplyRail`,
`ConnectorMate<series>`.

## E. System layer ([S] almost entirely)

`parts:`, `vendor()`, `connect:`, `exposing` (config variables:
`pivot.theta` analogs, block modes `pm.mode`, system modes `op`),
`budget` (`kind=` is pack-provided, D49: std ships `power | timing |
noise | error | mass | energy` here, `tolerance | deflection` in mech;
members may span domains), `members:`, `allocate:`, `locked:` (the
lock family -- never `pins:` in this domain).

## F. Claims, value sources, selectors, coherence, build

Sections F-J of the mech vocabulary apply verbatim ([S]): `require`,
`forall`, `sf=`, `@hint`, `assume!`, `todo!`, `waive` (in-source,
scoped, `basis:`-mandatory; regolith `12`), `policy:`
(`prefer`/`forbid`/global `minimize`), `model=` on claims, evidence
clauses; the five value sources; `.where/.all/.only/.any/.nearest`,
`&` joins, `.as_datum()`; `override by`, `use`;
`check/build/optimize/--release` (CLI `--waive` is exploratory-only
and never persists). Elec-specific selectors sketch:

| form | purpose |
|---|---|
| `nets.where(domain=, kind=)` | net queries |
| `x.instances.any` | orbit-checked channel/site selection |
| `routes(net_set)` | routed-geometry entities of nets (L4) |
| `.coupled_to(net)` | derived coupling-pair entities (L4) |
| `pairwise(set_a, set_b)` | orbit zip: element-wise connection of equal-cardinality sets in layout order |
| `flatten(set.port) -> bus` | concatenate per-instance ports into one bus, layout order, width-checked |
| `port.bits` / `bus[i .. j]` | per-bit set of a width'd port; half-open semantic bit ranges (slicing splits the orbit) |
| `bind <computer>:` | groups resource->implementation decisions into one reviewable block |
| `partitions:` | owned memory-map regions on an `image` (`app: flash[32kB .. 1MB]`; `remainder` rule applies) |

## G. Deliberately absent

No pin numbers in source. No positional port maps. No `X`/`Z` logic
values (unknowns are modeling gaps -> indeterminate evidence; high-Z is
an `arbitrate` state, not a value). No side-file timing constraints. No
freehand "draw a wire" -- connection is by contract.
