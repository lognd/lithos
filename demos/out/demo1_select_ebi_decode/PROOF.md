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
| `opt_trace.pdf` | 5505 | `sha256:17f878a45a9687ee2ec67729c58bd30c64a3cf558751fc24cbffc3fdb620a581` |
| `opt_trace.svg` | 8607 | `sha256:e144cedbc2148ea57c342d0125c05c123e2632479782ed49a3dcdeae0fd5d521` |
| `regolith.flip.lock` | 233 | `sha256:92b9928dbac7cc074ab8918a99d0e0fab65f4e574fd50bb2af2cd95ea2942d69` |
| `regolith.lock` | 241 | `sha256:9adf5d8d880214163d3a02b65fbd95e725ded895833f4a84fe344c59cc6d5f11` |
