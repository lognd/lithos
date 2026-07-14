# 31. Diagnostics and `regolith explain`

Every user-facing failure the toolchain can produce has a stable
code, whichever language raises it, and `regolith explain <code>`
tells you what it means, why it fired, and how to fix it. That is
not a convention -- it is machine-checked (D247).

## 1. One code space

There is exactly ONE code registry:
`crates/regolith-diag/src/code.rs`, with the explain content beside
it in `explain.rs`. Rust raises coded diagnostics directly. Python
raises coded failures too, importing GENERATED constants from
`regolith._codes` -- produced by `make codes` from the Rust
registry, drift-checked in CI (`make codes-check`), and NEVER
hand-edited. This is exactly the `make schema` precedent: Rust is
the source of truth, Python consumes a generated artifact, and a
second registry is never opened.

A Python failure kind that is not in the registry is a build error,
not a string (D247.1). Before D247 the Python side had quietly
grown a parallel, uncoded, unexplainable error vocabulary; the
health gate now makes that impossible (sec. 4).

## 2. The families

A code is a family plus an offset, rendered zero-padded (`E0301`).
**A code's numeric family never changes** -- families are permanent
once assigned, so a code you learned once stays where it was.

| family | codes | what it covers |
|---|---|---|
| Parse | E01xx | quantities, types, units, grammar (the `==` ban is E0102) |
| FluidNet | E02xx | the AD-23 net disciplines: flownets, circulation, load paths |
| References | E03xx | queries, ownership, structure |
| Contracts | E04xx | capability vs demand, ledgers, budgets |
| Instances | E05xx | instances, generics, symmetry |
| RulePacks | E06xx | DFM / DRC / ERC rules, with provenance |
| Evidence | E07xx | waivers, indeterminate discharge, release assumptions |
| Lint | L08xx | style/advisory lints (renders `L`, not `E`) |
| Emission | E09xx | emission/packaging: fab-set completeness, drafting-audit refusal, artifact-index drift |
| Injection | E10xx | injection/override: unexplained override, source-only target, unresolvable target |
| BringUp | E11xx | bring-up/harness: expectation provenance, debug-evidence refusal, tap-map disagreement |

E09xx/E10xx/E11xx are the three families D247 added for the
surfaces cycle 36 grew. E1001-E1003 are RESERVED for the override
channel (WO-129A): registered with their meanings so that work can
raise them without opening a second home, but not yet raised.

## 3. Using `explain`

```
regolith explain E0901          # prose: means / why / how to fix / example
regolith explain E0901 --json   # the same content, machine-readable
```

stdout is the data; logs go to stderr, as everywhere. An unknown
code is a constructive diagnostic, not a bare lookup failure -- it
names near matches (same family first, then edit distance):

```
$ regolith explain E0999
unknown code 'E0999'. Did you mean: E0901, E0902, E0903?
```

Some codes carry an honest stub -- an accurate one-line meaning, and
an explicit "no explanation authored yet" for the why/fix. That is a
legitimate, COUNTED state (sec. 4), not a silent gap. Authoring one
is a welcome, self-contained contribution.

## 4. Completeness is machine-checked

A rule that cannot fail a build is documentation, not doctrine
(D247.4). Two legs enforce this one, and both have negative tests
proving they bite:

- **Every registered code has an explain entry.** A code with no
  entry fails the Rust `explain::completeness_is_total` test (which
  also catches a STALE entry naming a removed code) and the
  `diag_codes` health sub-check. The health leg REPORTS the stub
  count -- the debt stays visible, never hidden.
- **No user-facing failure carries a bare string kind.** An AST
  sweep over `python/regolith/backends/` fails on any
  `BackendError(kind="some_new_string")`. A `kind=` naming an
  imported constant is exactly what is required and passes clean.

Both run in `make health-consistency` (and `make check` via
health-smoke).

## 5. Adding a new coded failure

1. Add the code to `crates/regolith-diag/src/code.rs`: a `pub const`
   in the right family, with a `///` doc comment saying what it
   means, and a row in `codes::ALL`. Pick an existing family -- only
   mint a new one when the surface is genuinely new (and remember it
   is permanent).
2. Add its explain entry to `explain.rs` -- `authored!(...)` with a
   real why/fix/worked example, or `stub!(...)` if you honestly
   cannot write one yet. Leaving it out entirely fails the build.
3. `make codes` to regenerate `regolith._codes`, and commit the
   generated file (CI drift-checks the COMMITTED file).
4. Raise it: in Rust, the `DiagCode` directly; in Python,
   `BackendError(kind=YOUR_CONSTANT, message=...)` importing the
   constant from `regolith._codes` -- never a bare string.
5. `make check`.
