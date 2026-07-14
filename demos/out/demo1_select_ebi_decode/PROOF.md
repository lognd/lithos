# PROOF: discrete select() choice point (ebi_decode, WO-56)

- optimized quantity: **cost** (declared closed-form per-candidate table)
- domain: `decoder_board.AddressDecodeGlue` over `select(nor_glue, cpld, mcu_chip_selects)`
  lowered from real source `examples/tracks/cuprite/ebi_decode.cupr` (a REAL `BuildPayload.choice_points` entry, not a fixture)
- winner: **mcu_chip_selects** (cost 0.0 -- the MCU's built-in FSMC controller adds no part)
- cause row (verbatim from `regolith.lock`):

```
decoder_board.AddressDecodeGlue=mcu_chip_selects    cause: optimize(cost, trace=blake3:3cf5c2efcb541a5adbf9412b02a3c32b9dfff5230df782a21f4b7c09ad515686)
```

## Policy-flip proof (the winner is genuinely searched, not hardcoded)

Reversing the declared cost preference flips the winner to **nor_glue**:

```
decoder_board.AddressDecodeGlue=nor_glue    cause: optimize(cost, trace=blake3:21f1e0ea10b715932a5ae57fb30cc7859ece8bbdf2760f4e88aa00fe2b9d4d98)
```

See `regolith.flip.lock` for the full reversed-cost pin.

## Where a human SEES it

`opt_trace.svg` / `opt_trace.pdf` -- the optimization-trace sheet: every evaluated candidate with its cost, the convergence polyline, and the winner annotation citing the trace digest `blake3:3cf5c2efcb541a5adbf9412b02a3c32b9dfff5230df782a21f4b7c09ad515686`.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `opt_trace.pdf` | 4377 | `sha256:805c7d35b280b7c0446240561065e871f193edf2e723876b8f57d3d1b8ca7627` |
| `opt_trace.svg` | 6774 | `sha256:2383819ca6a5a09bdad48e784ec79aa33fb14ad123199a163ef7a3e9c4929a7f` |
| `regolith.flip.lock` | 233 | `sha256:92b9928dbac7cc074ab8918a99d0e0fab65f4e574fd50bb2af2cd95ea2942d69` |
| `regolith.lock` | 241 | `sha256:9adf5d8d880214163d3a02b65fbd95e725ded895833f4a84fe344c59cc6d5f11` |
