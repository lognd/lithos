# 09 -- HDL coverage matrix (cuprite 0.12, cycle 23 / D120)

One sentence: cuprite is a SEMANTIC superset of the synthesizable
design subset of Verilog / VHDL / SystemVerilog / Veryl and an
EMBEDDING superset of everything else (`by extern`), with the claim
made testable by this matrix plus the `examples/hdl/` fixture pairs
-- and it is explicitly NOT a syntactic superset (cuprite never
parses HDL text as cuprite).

Status: normative inventory (D120). A row with neither a native
mechanism nor an extern fixture is a finding by definition. Fixture
column names the `examples/hdl/` pair proving the row (native
cuprite + embedded original + an equivalence obligation binding
them); rows marked (planned) are the WO-shaped debt of this doc and
must exist before the claim is cited externally.

## 1. The design subset (native, usually stronger)

| HDL feature class | cuprite mechanism | stronger because | fixture |
|---|---|---|---|
| module / entity+architecture, ports | blocks with typed ports (02/03) | ports carry quantity KINDS + units, not bit soup | counter (planned) |
| hierarchy / instantiation | construction scopes; `parts:` | instances are entities with ownership + queries | counter (planned) |
| parameters / generics | generics + monomorphization (INV-11) | arity/type checked per instantiation site, dead generics are E0503 | alu_generic (planned) |
| generate loops / arrays of instances | orbits + patterns | symmetry is a checked fact usable by verification (INV-4), not textual expansion | alu_generic (planned) |
| always_ff / VHDL clocked process / Veryl `always_ff` | `on <clk domain event>:` under event-bounded hybrid semantics (03 sec. 1a, EOPEN-7 settled) | continuous quantities coexist; sampling is explicit | counter (planned) |
| always_comb / concurrent assignment | derived signals in `spec:`/behavioral bodies | dimension/unit checked at L1 | counter (planned) |
| FSMs (case-based or enum types) | mode machinery + `on`-event transitions | modes bind claims per state; exhaustiveness is checkable | fsm_traffic (planned) |
| SV interfaces / modports | cuprite interfaces + roles (regolith/04 contracts) | interfaces carry CONTRACTS (promises/demands with evidence), not just signal bundles | fifo_cdc (planned) |
| packages / imports / libraries | quarry packages + registry records | versioned, hash-pinned, trust-tiered | (covered by every project) |
| typed signals, VHDL enums/records | typed regolith quantities, records, config domains | physical units, intervals, corner discipline | counter (planned) |
| clock/reset abstraction (Veryl `clock`/`reset` types) | clock/voltage DOMAINS with membership typing (04/06) | domain crossing is a static ledger, not a lint | fifo_cdc (planned) |
| CDC handling (conventions/linters in SV) | crossing ledger at L3 -- compile-checked | E03xx-family error, not a style warning | fifo_cdc (planned) |
| timing constraints (SDC beside the HDL) | timing budgets over structure (`budget ... kind=timing`, 04 sec. 5) | budgets allocate slack between silicon and ROUTES in one system | sdr project |
| tristate / inout / open-drain | port classes + arbitrate discipline (03 sec. 2) | single-driver/arbitration is the net ledger, not X-propagation debugging | (covered by net-discipline fixtures) |

## 2. The verification subset (mapped, deliberately not reproduced)

| HDL feature class | cuprite/regolith mechanism | mapping quality | fixture |
|---|---|---|---|
| SVA immediate assertions | claims on signals (`require:` comparisons) | FULL | assertions_map (planned) |
| SVA concurrent properties (implication over clocks, bounded delays) | temporal claim vocabulary: `within d after e`, `settles`, `stays_within(mask)`, `peak` (regolith/02 sec. 5, D102 families) | PARTIAL -- bounded-window properties map; deep sequence algebra (repetition operators, `throughout`, sequence composition) does NOT map natively. Route: keep the SVA in an extern-bound verification file; its simulation run enters as `by test(...)` evidence | assertions_map (planned) |
| covergroups / functional coverage | the structured coverage encoding on evidence (D95) + swept-obligation domains | DIFFERENT BY DESIGN -- regolith states coverage of CLAIM domains, not of simulation stimulus; stimulus coverage lives with the discharging model/testbench and enters through the evidence coverage statement | assertions_map (planned) |
| constrained randomization | value-source intervals + planner allocation (`free`/`in [lo,hi]`) | DIFFERENT BY DESIGN -- regolith solves for values against claims instead of randomizing then checking | (covered by every project) |
| UVM class machinery / testbench OOP | the verification harness itself (models, packs, obligations) | NOT REPRODUCED -- regolith IS the testbench framework; foreign UVM benches run externally and land as `by test` evidence with signed attribution (WO-21) | -- |

## 3. The embedding route (everything else)

`by extern(ref, format)` (regolith/08 sec. 4; 03 sec. 2):

- **Verilog**: TRANSPARENT -- elaborates into the structural layer,
  gets the full static tier + an equivalence obligation against any
  native-declared contract.
- **VHDL / SystemVerilog**: OPAQUE-with-contracts in v1 -- linked as
  pinned artifacts, contracts retro-declared, equivalence + promise
  obligations attach; transparency is demand-gated (reopen: the
  first user corpus where opaque VHDL blocks a load-bearing check).
- **Veryl**: embed the SystemVerilog it emits (Veryl is a
  transpiler); a native-Veryl transparent path is not planned --
  its language-level features (clock/reset types, explicit
  ff/comb) are exactly the rows sec. 1 covers natively.

Every embedded block is hash-pinned (INV-22) and carries either a
retro-contract or an explicit `sealed` acknowledgment -- the D117
uncontracted-injection lint fires on an extern with neither.

## 4. The superset direction (what HDLs cannot say at all)

For the record, since a superset claim should name its strict part:
continuous physical quantities with units on every signal; interval
values + corner discipline; contracts with evidence and trust tiers;
physical realization in the same source (pins, layout, budgets to
gerbers -- L4-L6); cross-track coupling (a cuprite signal
commanding a fluorite valve through one event ledger); the
claim/obligation/evidence pipeline itself.

## 5. Fixture debt

`examples/hdl/` fixture pairs (counter, alu_generic, fsm_traffic,
fifo_cdc, assertions_map) are authored with the cycle-23 stress
corpus (D121); until they land, rows marked (planned) make this
matrix a stated intent, not an asserted fact -- do not cite the
superset claim externally before the fixtures exist and pass
`regolith check` parse-clean with their deferrals captured in the
deferral golden.
