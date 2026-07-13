# WO-122 -- Quantity-aware bound parsing (F132.2, the truncation hazard)

Status: open
Language: Python (orchestrator/translate.py bound resolution) +
  Rust regolith-qty read-side if the unit tables need a new query
  (escalate before adding one); no schema bump.
Spec: F132.2 (the ruling); WO110-F1 (the evidence: `<= 0.10 mrad`
  parsed as unitless 0.10; `> 1.4 * 9200rpm` truncated to 1.4 and
  FROZEN in a pre-WO-110 golden); D220 (this is verdict-honesty
  machinery: a truncated limit is a WRONG limit); regolith-qty
  (the ONE unit engine, D135 exception note).

## Goal

No bound text is ever silently truncated or unit-stripped again:
every comparator bound resolves through quantity-aware parsing to
an SI value, defers with a named reason when it cannot, and the
truncating `_parse_float` leading-float path is dead.

## Deliverables

1. One bound-resolution home: parse `<number> <unit>` and
   arithmetic bound expressions (`1.4 * 9200rpm`) through
   regolith-qty's unit reduction (the same tables L1 uses); the
   result is an SI-reduced limit + recorded source text.
2. Every translate route (generic fallback, kwargs routes, window
   halves, temporal reductions) consumes it; `_parse_float` on
   bound text is removed (grep-proven in the close-out).
3. Unresolvable bounds defer NAMED (`bound_unit_unresolved` /
   `bound_expression_unresolved`, naming the text) -- never a
   truncated number.
4. Golden sweep: regenerate + review; every previously-truncated
   limit either resolves correctly now or moves to the named
   deferral (enumerate the flips in the close-out -- each one is
   a claim whose effective limit CHANGED; verify no verdict
   flipped to a false pass, and report any that flip to VIOLATED
   as D224.3 items for WO-113).
5. Fixtures both ways per route family.

## Acceptance

- The WO110-F1 examples resolve exactly (0.10 mrad -> 1.0e-4 rad;
  1.4 * 9200rpm -> the SI angular rate) with tests.
- Zero `_parse_float`-on-bound sites remain; make check green;
  golden diff reviewed with the flip enumeration.

## Escalation

Bound grammars beyond number/unit/scalar-arithmetic (record refs,
function calls) stay on their existing named paths -- do not grow
scope; report anything ambiguous.
