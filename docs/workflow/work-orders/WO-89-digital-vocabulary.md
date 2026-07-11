# WO-89 -- Digital vocabulary cluster + riscv phase B

Status: todo
Language: Rust (regolith-lower claims/translate seams) + Python
  (harness routing) + corpus (riscv_hart_rv1)
Spec: F112 (the cluster's four named asks, verbatim: "per-
  instruction ISA semantics, CSR bit-field legality, memory-model
  claims, generic-default deref via parts:"); WO-81 (the riscv
  flagship -- phase A landed the ratified-extension contract
  catalog; phase B is UN-GATED by WO-82); WO-82 (std.hdl verilator
  pack: build/sim/equiv tiers -- the discharge machinery phase B
  consumes); cuprite/08 (computer-track claim forms -- VERIFY what
  it already declares before implementing ANY form; undeclared
  shapes are escalations, the D194/D200 precedent); charter
  36/WO-79 (board-correctness posture for rule-shaped legality
  checks).

## Goal

riscv_hart_rv1 is the fleet's only all-zero flagship left with a
landed discharge path (WO-82's sim/equiv tiers + ghdl/verilator
present on the host). Phase B: its contract catalog's digital
claims move from catalog-only to formed-and-evaluated obligations
through the WO-82 tiers, using the F112 vocabulary where cuprite/08
already declares it.

## Deliverables

1. VERIFICATION FIRST (the protocol's step 1, and this WO's most
   important deliverable): for each of the four F112 asks, locate
   what cuprite/08 (and the WO-81 catalog) ALREADY declares --
   claim-form shape, spelling, obligation shape. Produce the
   declared-vs-undeclared table in your plan BEFORE any code.
   Undeclared shapes: STOP that leaf, record the ask + a concrete
   recommendation (the D194 pattern); the coordinator rules and
   re-dispatches. Do NOT invent grammar.
2. For DECLARED shapes: lowering/translate wiring so the claims
   form obligations routed to the WO-82 tiers (sim expectations
   through the verilator pack; ghdl for VHDL fixtures) or to
   rule-shaped legality checks (CSR bit-fields may be
   rule-pack-shaped -- follow what the spec says, WO-79's posture
   if rules).
3. riscv phase B corpus: the flagship's catalog claims wired to
   real fixtures (WO-82's fixture tiers are the precedent);
   `regolith test` scenarios; census before/after (74/0 is the
   F115 baseline).
4. Docs: WO-81 phase-B ledger; guide additions only where
   user-facing behavior exists.

## Acceptance criteria

- riscv_hart_rv1 release build: discharge count strictly above 0
  OR every remaining zero honestly attributed to an escalated
  undeclared shape (the declared-vs-undeclared table is the
  ledger).
- No SCHEMA_VERSION bump; no grammar invention; goldens via make
  targets; zero lowered->deferred fleet-wide.
- `make check` green.

## Dependencies

WO-82 (landed), WO-81 phase A (landed), host verilator+ghdl
(present). Serializes with WO-78 at integration (both touch elec
translate surfaces; WO-78 is in flight -- rebase over it).
