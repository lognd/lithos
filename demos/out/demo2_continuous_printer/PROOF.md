# PROOF: continuous golden-section over a realized-mass evaluator (printer_k1, WO-57/64)

- optimized quantity: **mass** (realized plate volume x density, measured by the real OCCT interpreter -- never synthesized)
- domain: two declared continuous minimize dims off the printer_k1 flagship --
  - `HeatedBed.BedPlateFlat.a` in [220mm, 240mm]
  - `XCarriage.CarriagePlateFlat.b` in [35mm, 45mm]
- winner: **a = 220.003 mm** (bed) and **b = 35.003 mm** (carriage) -- each search lands at its lower bound, where realized mass is minimal
- cause rows (verbatim from `regolith.lock`):

```
x=0.22000346140543425    cause: optimize(mass, trace=blake3:1898112aa879d6355da087b4d8072fb48aab6108aa3b93dc7a386755639a9740)
x=0.035002800335820726    cause: optimize(mass, trace=blake3:c78579ff7747f0d825c3ee50dcd07853d3a62fcd50e91a06adda8682f93edea2)
```

## Note on the exemplar (honest substitution)

The WO body names `duct_vane`, which is not a landed corpus member (`tests/backends/test_parity.py` records the same gap). The LANDED continuous evaluator machinery (WO-57) is proven here over the printer_k1 flagship's own real minimize dims, exactly the WO-64 phase-B recipe.

## Where a human SEES it

- `bed_before_240mm.step/.glb/.viewer.html` vs `bed_after_pinned.step/.glb/.viewer.html` -- the before (upper bound) and after (pinned winner) heated-bed solid; open either `.viewer.html` offline to rotate it.
- `opt_trace_bed.svg/.pdf` (trace `blake3:1898112aa879d6355da087b4d8072fb48aab6108aa3b93dc7a386755639a9740`) and `opt_trace_carriage.svg/.pdf` (trace `blake3:c78579ff7747f0d825c3ee50dcd07853d3a62fcd50e91a06adda8682f93edea2`) -- every realized candidate's measured mass, the convergence polyline, and the winner annotation.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `bed_after_pinned.glb` | 840 | `sha256:9d86efc1fa40122f09a88b28e6d46700ea7f0b634c80f9e8ed74524008de1ff7` |
| `bed_after_pinned.step` | 15688 | `sha256:471d3cc9ebe412d98418b9047da8f43d3b90548eae658fc8aad4539a54020c54` |
| `bed_after_pinned.viewer.html` | 10606 | `sha256:34462fa098d078faa2745db7f2a9885beaedf1a985f66a5c217861c01c265f00` |
| `bed_before_240mm.glb` | 836 | `sha256:39d10b014d025020540ba1fdec8e7169ba603e5d70f0af2be944fb908028bc16` |
| `bed_before_240mm.step` | 15428 | `sha256:06efd8a9080fb49adbb1a27c61184f302249a65f8696390c1a09347bc17f875e` |
| `bed_before_240mm.viewer.html` | 10602 | `sha256:df8b3fafc34d27492f0d3de0a3da4e74a4ff1e0358565465cfebda801328476f` |
| `opt_trace_bed.pdf` | 10336 | `sha256:a5e84d66ca490e7397094a10ea56b7cb290f9f212f9dd3558b9bea74e6190228` |
| `opt_trace_bed.svg` | 15267 | `sha256:cddd09c8c454de9a8c452d858b2e290fbdcbe3f5b4280d2da81bd374c3cdf6c6` |
| `opt_trace_carriage.pdf` | 10100 | `sha256:5b59ba0346882250bf82efd1b4ec27824081e4f29fdb02812821c75a979ac598` |
| `opt_trace_carriage.svg` | 14941 | `sha256:e487f7c2fa3f6b7e97409206f03533172fdf2a34999c3224d80a4b66a0d4848b` |
| `regolith.lock` | 371 | `sha256:0eb638fce1db9e938db985ef2d1335572f91fb9639a74a9eb0cef7ae5d9dc440` |
