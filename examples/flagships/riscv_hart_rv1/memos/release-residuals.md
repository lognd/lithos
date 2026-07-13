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
