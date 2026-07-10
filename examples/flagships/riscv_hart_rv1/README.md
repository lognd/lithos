# riscv_hart_rv1 -- ground-up RISC-V hart (flagship, WO-81, D189)

Phase A: the COMPLETE extension contract catalog at contract
altitude. Not a from-scratch bring-up -- a machine-scale proof that
"all extensions" can be a checked, catalog-complete claim before any
gate is drawn.

Envelope-target givens (each is a literal the parity report's
attention list will show -- correct and honest per AD-33, not a
derived value):

- RV64GC-class base (RV64I + M/A/F/D/C) with S-mode and H-mode
  (`riscv_hart_rv1.cupr`, `rv64i_core.cupr`, `priv_smode.cupr`,
  `priv_hmode.cupr`).
- 28nm-class synthesizable in-order single hart, area <= 0.35mm2,
  power <= 45mW, fmax class 1.0GHz (`riscv_hart_rv1.cupr` budgets;
  class basis cited in `uarch.cupr`'s own header).
- 5-stage in-order pipeline (fetch/decode/execute/mem/writeback),
  16KiB I$/D$ class, a single debug module boundary (`uarch.cupr`).

## Citations (spec versions this catalog was checked against)

- RISC-V Unprivileged ISA spec, document version 20240411 (RVA23
  profile release) -- base RV64I, M/A/F/D/C, Zicsr/Zifencei, and
  every Z*/V extension cited inline per-file.
- RISC-V Privileged Architecture spec, document version 20211203 --
  M/S/U privilege levels, CSR access classes, the H (hypervisor)
  extension (ch. 9), Sv*/S* supervisor refinements.
- RISC-V Debug Specification v1.0 stable (2019) -- the debug module
  boundary (`uarch.cupr`).

## Files

- `magnetite.toml` -- manifest, cost-profile pair (D147 shape, no
  BOM this phase).
- `rv64i_core.cupr` -- `RV64ICore` (the base integer ISA + mandatory
  M-mode reset/trap state) + `Zicsr`/`Zifencei` (mandatory
  companion extensions).
- `ext_std.cupr` -- `ExtM`/`ExtA`/`ExtF`/`ExtD`/`ExtC`: the G-minus-
  base standard extensions, each a full architectural-state contract.
- `priv_smode.cupr` -- `SmodeCsrs` (S-mode CSR set + ECALL/xRET
  privilege-transition claims via the typed temporal vocabulary) +
  four S-mode-adjacent supervisor extension stubs (Svinval, Sstc,
  Smstateen, Sscofpmf).
- `priv_hmode.cupr` -- `HmodeCsrs` (the H hypervisor extension: four
  privilege levels M/HS/VS/VU, guest CSR set, trap-and-emulate
  claims) + `GStagePtw` (the second-stage translation boundary).
- `ext_stubs.cupr` -- every remaining ratified extension this
  catalog does not give a full contract: B (Zba/Zbb/Zbs/Zbc), Zk*
  (Zbkb/Zkn/Zks/Zkr/Zkt), V, Zfh/Zfa, Zfinx, Zicntr/Zihpm, Zmmul,
  Zc* (Zca/Zcmp/Zcmt), Ztso/Zawrs, Zicbom/Zicboz, Svnapot/Svpbmt --
  25 contract stubs, catalog-complete at contract altitude.
- `uarch.cupr` -- microarchitecture boundaries: the 5-stage pipeline
  frame boundaries, I$/D$/MMU/PTW boundaries, the debug module
  boundary -- promises only, no realized datapath.
- `riscv_hart_rv1.cupr` -- the top-level system: area/power budgets
  that sum and close over the uarch boundaries, the fmax target
  (declared literal, see the WO ledger's wall W4).

## The extension catalog (D189 phase A deliverable 1)

| Extension | Contract file | Status | Spec version |
|---|---|---|---|
| RV64I (base) | `rv64i_core.cupr` `RV64ICore` | full contract | unpriv 20240411 chs. 2, 4 |
| Zicsr | `rv64i_core.cupr` `Zicsr` | full contract | unpriv 20240411 ch. 6 |
| Zifencei | `rv64i_core.cupr` `Zifencei` | full contract | unpriv 20240411 ch. 6 |
| M | `ext_std.cupr` `ExtM` | full contract | unpriv 20240411 ch. 7 |
| A | `ext_std.cupr` `ExtA` | full contract | unpriv 20240411 ch. 8 |
| F | `ext_std.cupr` `ExtF` | full contract | unpriv 20240411 ch. 11 |
| D | `ext_std.cupr` `ExtD` | full contract | unpriv 20240411 ch. 13 |
| C | `ext_std.cupr` `ExtC` | full contract | unpriv 20240411 ch. 16 |
| S-mode | `priv_smode.cupr` `SmodeCsrs` | full contract | priv 20211203 ch. 3, sec 4.3 |
| H (hypervisor) | `priv_hmode.cupr` `HmodeCsrs` + `GStagePtw` | full contract | priv 20211203 ch. 9 |
| Zba/Zbb/Zbs (B) | `ext_stubs.cupr` `ZbaExt`/`ZbbExt`/`ZbsExt` | stub | unpriv 20240411 ch. 28, v1.0.0 (2021) |
| Zbc | `ext_stubs.cupr` `ZbcExt` | stub | v1.0.0 (2021) |
| Zbkb | `ext_stubs.cupr` `ZbkbExt` | stub | v1.0.1 (2021) |
| Zkn | `ext_stubs.cupr` `ZknExt` | stub | v1.0.1 (2021) |
| Zks | `ext_stubs.cupr` `ZksExt` | stub | v1.0.1 (2021) |
| Zkr | `ext_stubs.cupr` `ZkrExt` | stub | v1.0.1 (2021) |
| Zkt | `ext_stubs.cupr` `ZktExt` | stub | v1.0.1 (2021) |
| V (vector) | `ext_stubs.cupr` `VExt` | stub | unpriv 20240411 ch. 2 (vector set), v1.0 (2021) |
| Zfh | `ext_stubs.cupr` `ZfhExt` | stub | unpriv 20240411 ch. 12, v1.0 (2021) |
| Zfa | `ext_stubs.cupr` `ZfaExt` | stub | unpriv 20240411 ch. 15, v1.0 (2023) |
| Zfinx | `ext_stubs.cupr` `ZfinxExt` | stub | unpriv 20240411 ch. 20, v1.0 (2022) |
| Zicntr | `ext_stubs.cupr` `ZicntrExt` | stub | unpriv 20240411 ch. 9, v2.0 (2019) |
| Zihpm | `ext_stubs.cupr` `ZihpmExt` | stub | v2.0 (2019) |
| Zmmul | `ext_stubs.cupr` `ZmmulExt` | stub | unpriv 20240411 ch. 7, v1.0 (2021) |
| Zca/Zcmp/Zcmt | `ext_stubs.cupr` | stub | unpriv 20240411 ch. 27, v1.0.0 (2022-23) |
| Ztso | `ext_stubs.cupr` `ZtsoExt` | stub | unpriv 20240411 ch. 19, v1.0 (2023) |
| Zawrs | `ext_stubs.cupr` `ZawrsExt` | stub | unpriv 20240411 ch. 18, v1.0 (2023) |
| Zicbom/Zicboz | `ext_stubs.cupr` | stub | unpriv 20240411 ch. 10, v1.0 (2021) |
| Svinval/Sstc/Smstateen/Sscofpmf | `priv_smode.cupr` | stub | priv spec, v1.0 each (2021-22) |
| Svnapot/Svpbmt | `ext_stubs.cupr` | stub | priv 20211203 sec 4.4/4.5, v1.0 (2021) |

10 full contracts + 25 contract stubs = 35 declared artifacts (plus
11 microarchitecture-boundary artifacts in `uarch.cupr`, each a
promise-only stub) -- 50 total honest-deferral (`todo!`) sites,
matching `regolith check`'s own count exactly (see the WO ledger).

See `docs/workflow/work-orders/WO-81-flagship-riscv.md` for the full
ledger, the walls list, and the architecture-summary close-out.
