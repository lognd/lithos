# regolith-qty

Quantity core: dimensions, units, intervals, log views, value sources
(`docs/spec/regolith/02-quantity-core.md`, `03-value-sources.md`).
Dimension exponents are rational (AD-9); intervals round outward
(AD-6); resolved values carry a `Cause` (INV-21). This crate is the
keystone: both modeling languages and the harness depend on it, and it
depends on nothing but `regolith-util`. Module map: WO-02 lands
`dimension`, `unit`, `quantity`, `decl`, `count`; WO-03 adds intervals/
ranges; WO-04 adds value sources.

## corner

Corner machinery: enumerate the endpoint assignments of a set of named
interval inputs, and select the worst one for a check
(`docs/spec/regolith/07` sec. 5, corner discipline). Which corner is
worst is the *model's* decision, per-check, never a global policy
(WO-03 goal: expose the mechanism, not a policy). This module yields
the corners and takes the model's direction/evaluator; it does not
decide worseness itself.

## count

Counts: `n x thing`, a discrete quantity of identical members
(`docs/spec/regolith/02-quantity-core.md` sec. 3). A count models as a
dimensionless integer quantity carrying a member-kind tag; the members
form an orbit of entities (`battery(2 x AA_alkaline)`, `pwm x 4`).
Discrete, so exact equality is legal here -- the `==` ban is on
continuous quantities only.

## decl

Quantity declarations and namespaces: the typed vocabulary of physical
quantities the two languages share (`docs/spec/regolith/
02-quantity-core.md` sec. 1). Namespaces are shared across domains (a
thermal quantity means the same thing in a mechanical and an
electrical claim) -- the hook for cross-domain contracts. Declares the
tensor-rank enum a quantity carries.

## dimension

Physical dimensions: the fixed vector of seven SI base-dimension
exponents (AD-9 -- rational exponents, not integer;
`docs/spec/regolith/02-quantity-core.md` sec. 1). Dimensional analysis
runs at parse time; arithmetic between incompatible dimensions is an
error, never a solver input. Rational exponents are genuine: noise
density (`nV/sqrt(Hz)`) is half-integer territory the elec track needs.

## interval

Closed intervals `[a, b]`: the source-of-truth representation for
tolerances, scatter, environment ranges, and process corners
(`docs/spec/regolith/02-quantity-core.md` sec. 3, interval-vs-range
rule, and `07` sec. 5, corner discipline). Interval arithmetic rounds
outward (AD-6) so a computed bound never excludes a physically
reachable value; bounds are `f64` carrying a shared `Unit`. Not
interconvertible with `Range` -- a distinct positional type. No
`PartialEq` on the continuous form (the equality ban, sec. 2):
comparisons go through containment and tolerance forms.

## lib

Crate root: dimensions, units, intervals, log views, value sources
(`docs/spec/regolith/02-quantity-core.md`, `03-value-sources.md`).
Declares `BASE_DIMENSIONS` and the module map every other file in this
crate builds on. Dimension exponents are rational (AD-9); intervals
round outward (AD-6); resolved values carry a `Cause` (INV-21).

## log

Logarithmic unit views (`dB`, `dBm`, `dBi`, `dBc`, ...): decibel
spellings that view an underlying linear quantity
(`docs/spec/regolith/02-quantity-core.md` sec. 5a, SETTLED, closes
SOPEN-5, and INV-17). Log units are views of linear quantities: the
stored, solved, and cached value is always linear; a `dB`-family unit
only affects parsing/printing plus one extra L1 legality check.
Because the view is strictly monotone, interval corners commute with
it -- corner discipline and margin math run in linear space untouched.
The one legality rule (sec. 5a): sum legality equals linear product
legality.

## monomorphize

Monomorphization of discrete `in [...]` domains into per-point
instantiation points, each with a stable identity for caching
(`docs/spec/regolith/03-value-sources.md` sec. 1, integer domains
monomorphize, and sec. 4, structure boundaries as domain constraints).
`variant` axes are externally-chosen: every point must verify, none is
optimizer-picked. The structure-boundary hook here is data only
(WO-04): later passes intersect domains with structure-preserving
regions.

## quantity

`Qty`: a continuous physical quantity value (magnitude x unit) with
dimension-checked arithmetic (`docs/spec/regolith/02-quantity-core.md`
sec. 1-2). The equality ban (sec. 2) is enforced structurally: `Qty`
has no `PartialEq`. Comparisons go through explicit tolerance forms
(`within`, `equal_within`); the parser rejects `==` on continuous
quantities (WO-05 hook). Arithmetic between incompatible dimensions is
an error value carrying both dimensions, never an exception.

## range

Half-open positional ranges `[i .. j]` over semantically ordered
discrete positions (bus bits, memory addresses;
`docs/spec/regolith/02-quantity-core.md` sec. 3). A `Range` is not an
`Interval` and never implicitly converts to one: intervals are
continuous closed values, ranges are half-open discrete addressing.
Keeping them distinct types is the enforcement (WO-03 acceptance: not
interchangeable).

## resolution

Resolution records: a resolved value plus the cause that decided it --
the lockfile row shape (`docs/spec/regolith/03-value-sources.md` sec.
2). Every non-literal source resolves into the lockfile carrying WHY it
got its value; a number that changes in review names why it changed.
Resolutions are constructed only through a `Cause`-requiring API
(INV-21 as a type: a causeless resolved value is unrepresentable).

## unit

Units: a symbol carrying a dimension and an exact conversion to SI
base, plus SI-prefix parsing and multiplicative unit algebra
(`docs/spec/regolith/02-quantity-core.md` sec. 1, ASCII unit spellings
`mm`, `N/m`, `degC`, `ohm`, `bit/s`, `ops`). Scale factors are exact
rationals (AD-9) so conversions never drift. This is the largest module
in the crate: the parser and algebra for compound unit expressions
(products, quotients, powers) live here alongside the base-unit table.

## value_source

The value-source grammar: one union answering "who decides this
number?" for every numeric slot in both languages
(`docs/spec/regolith/03-value-sources.md` sec. 1). Five sources:
literal, `in [lo, hi]` (bounded freedom), `free`, `derived`,
`allocated`. Optimization direction is per-variable and takes no
argument (SOPEN-4). Every IR numeric slot carries one of these;
schemars export (WO-18) feeds the generated pydantic models.

## window

`Window`: a demanded containment window `within [lo, hi]` -- a value
the design must land inside, distinct from an asserted `Interval`
(`docs/spec/regolith/03-value-sources.md` sec. 1). An `Interval` is the
scatter/range the author *asserts*; a `Window` is the band the design
is *required* to satisfy (a flexure stiffness that must be neither too
stiff nor too soft; an oscillator band). Kept a separate type so the
two intents never silently mix (WO-03 acceptance: not interchangeable
with `Interval`).
