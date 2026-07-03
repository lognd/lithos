# WO-02: Quantity core -- dimensions, units, namespaces

Status: todo
Depends: WO-01
Language: Rust (`decl-qty`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/02-quantity-core.md sec. 1-2; substrate/01 sec. 4

## Goal

Typed physical quantities with parse-time dimensional analysis, as the
keystone `qcore` package. No parser yet: a Python API other passes call.

## Deliverables

- `Dimension` (7 SI base exponents as a frozen pydantic model),
  `Unit` (symbol, dimension, scale; ASCII spellings: `mm`, `N/m`,
  `degC`, `ohm`, `bit/s`, `ops`), unit expression algebra.
- `QuantityDecl` (name, namespace, unit, tensor rank: scalar / vector /
  tensor(n) / complex) and `Namespace` registry (`mech`, `elec`,
  `thermo`, `geom`, `info`, `mfg` seeded from the spec).
- `Qty` value type: magnitude x unit, arithmetic returning
  `Result[Qty, QuantityError]`; incompatible-dimension arithmetic is an
  error value carrying both dimensions.
- The `==` ban: `Qty.__eq__` on continuous quantities raises a typed
  programmer-bug error in library code paths and is rejected at parse
  time later (document the hook for WO-05).
- JSON serialization for every model (obligations will embed these;
  substrate/07).

## Acceptance

- Unit tests: dimensional algebra (`N/m * m = N`), offset units
  (`degC`/`K` deltas), prefix parsing (`kN`, `uF`, `mohm`), rejection
  of `1V + 1A` as an error value (not an exception), round-trip
  serialization.
- `count` quantities: `n x thing` counts model as dimensionless
  integer quantities with a member-kind tag (substrate/02 sec. 3).
