# riscv_hart_rv1 -- release residuals memo

Engineering memo (D207) backing this project's `waive ... by
doc(memos/release-residuals.md)` deviations: per accepted set, why the residual
is genuinely unbounded (the wall), and the discharge path that
would retire the waiver. Hash-pinned like any catalog doc;
unsigned, so it confers `community` tier (INV-14).

## Accepted -- Predicate form outside the scalar-comparison lowering surface

The claim's comparator/form does not lower to a one-sided scalar bound (translate() wall: `comparator 'require' defers`); no numeric obligation can be formed without fabricating one.

- `boot_priv` (unsupported_op): comparator 'require' defers
- `ecall_from_u` (unsupported_op): comparator 'require' defers
- `enters_m` (unsupported_op): comparator 'require' defers
- `exclusive` (unsupported_op): comparator 'require' defers
- `frm_legal` (unsupported_op): comparator 'require' defers
- `guest_needs_v` (unsupported_op): comparator 'require' defers
- `guest_trap_to_hs` (unsupported_op): comparator 'require' defers
- `host_needs_not_v` (unsupported_op): comparator 'require' defers
- `hret_needs_hs` (unsupported_op): comparator 'require' defers
- `hret_restores` (unsupported_op): comparator 'require' defers
- `indivisible` (unsupported_op): comparator 'require' defers
- `mret_needs_m` (unsupported_op): comparator 'require' defers
- `mret_restores` (unsupported_op): comparator 'require' defers
- `sret_needs_sm` (unsupported_op): comparator 'require' defers
- `sret_restores` (unsupported_op): comparator 'require' defers
- `stimulus` (unsupported_op): comparator 'require' defers -- the
  `stimulus: sim(pc_incr_directed_vectors)` claim line rides this same
  require-claim mechanism (WO-157/T-0027, D264); the REAL coverage it
  buys is the separate auto-emitted `hdl.sim_assert` obligation below,
  which discharges for real.

Retirement: the claim-form lowering increment for the named form (charter 30 sec. 1.3 WO-shaped escalation).

## Accepted -- Module-import conformance edges

A bare `import <pkg>` emits a conformance obligation with no window on either side -- genuinely indeterminate per D195.3. Accepted via the D213 `import(<pkg>)` waiver spelling.

- `import:contracts.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:package.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:rv64i_core.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei
- `import:uarch.cupr` (conformance_windows_unresolved): conforms obligation carries no resolved conformance_sense/spec_bound/impl_bound windows (no scalar bound on ei

Retirement: the realized-fact/conformance channels, if a future import contract carries scalar windows.

## Accepted -- impl/iface conformance edges

An interface-conformance edge (`impl:X`, or `extern:X` for the Verilog-backed PcIncrement leg) carries no scalar window on either side -- genuinely indeterminate per D195.3, exactly like a bare import. Accepted via the D215 `impl(<Interface>)` waiver spelling: the full ISA extension surface (ExtA/C/D/F/M, V, the Z*/S* extension set), the pipeline stage contracts (Fetch/Decode/Execute/Mem/Writeback), the cache/MMU/PTW/debug boundaries, RV64ICore, the CSR banks, and the package boundary (ClockInput, CorePowerDomain, DebugPort, DieOutline, ExternalMemPort). Verdicts untouched (INV-2/INV-13).

Retirement: realized impl-side narrowings (e.g. a real per-extension conformance suite binding scalar windows); each waiver then goes stale.

## Discharged for real (WO-113, closing WO109-F3)

The three ClockSi rows retired: WO-109's probe-env plugin loading made the feldspar pack load in the release environment, so `clk_z0.lo`/`clk_z0.hi` and `clk_rs` DISCHARGE for real; their stale "not installed" waivers were shadowing the discharges (the exact D224.2 debt shape) and are deleted.

## Discharged for real (WO-157, T-0027, D264): PcIncrement functional simulation

`uarch.cupr`'s `PcIncrement` decl now declares a directed-vector
stimulus (`stimulus: sim(pc_incr_directed_vectors)`, see
`pc_incr_directed_vectors` beside this file: three hand-typed vectors
-- sequential PC+4, a taken-branch redirect, and a PC+4 low-word
wraparound -- `trust_tier=authored` per D260 ruling 3). Since
`PcIncrement` also carries a known-HDL `extern("pc_incr.v",
verilog2001)` conformance edge, `regolith_lower::claims::sim`
auto-emits one `hdl.sim_assert` obligation (WO-155), which DISCHARGES
FOR REAL through the verilator-backed `std.hdl` pack -- the flagship's
census `discharged` count rises from 4 to 5 (obligations 79 -> 81:
the sim_assert obligation plus the `stimulus` predicate-form byproduct
above), a real reclassification per the F152 honesty bar, not an
invented obligation. This is the sim-half of WO-157's four-project
adoption; sdr_transceiver/mainboard_mx/la_jig8 stimulus coverage and
mainboard/la_jig8's own PcIncrement-shaped subjects are out of THIS
change's scope (see T-0027's Done report / the follow-up ticket it
files for the remainder).
