# WO-81: flagship riscv_hart_rv1 (ground-up RISC-V hart)

Status: todo (phase A dispatchable NOW; B gated on WO-82; C on B)
Depends: phase A -- landed toolchain only (authoring). Template:
WO-64's arc + ledger discipline; D189 (NORMATIVE phasing).
Language: corpus authoring (.cupr + records refs) + test enrollment.
Spec: 31-flagships.md, design-log 2026-07-10-cycle-32 D189,
cuprite/02-05 + 09-hdl-coverage.md (the behavioral/HDL surface),
regolith/08 sec. 4 (extern Verilog is the phase-B linkage).

## Phase A deliverables

1. `examples/flagships/riscv_hart_rv1/`: the extension contract
   CATALOG -- RV64I base as the core interface; M/A/F/D/C,
   Zicsr/Zifencei, S-mode, H (hypervisor) as first-class interface
   contracts with their architectural state (CSR sets, privilege
   transitions) as typed contracts/temporal claims; remaining
   ratified extensions as contract stubs (impl todo!) so catalog
   coverage is COMPLETE at contract altitude.
2. Microarchitecture boundaries: fetch/decode/execute/mem/WB
   frames, hart-level memory subsystem (I$/D$/MMU/PTW boundaries),
   debug module boundary -- promises + budgets (area class, power
   class, fmax target as declared basis-cited literals).
3. The walls list (motion-hunt discipline applied to digital):
   every ISA-semantics construct the type system cannot yet express
   (per-instruction semantics, CSR bit-field legality, trap
   priority ordering) recorded with citations -- this list is the
   phase-B/C gate input and feeds the cuprite vocabulary roadmap.
4. Corpus enrollment + contract-graph golden; check clean; zero
   waivers.

## Acceptance (phase A): WO-64 phase-A shape verbatim (check clean,
budgets close, two-sided interfaces, todo! = declared count,
contract-graph golden, walls ledgered, make check green, Status
`phase A done (B/C gated)`).
