"""The D220.2 waiver-class vocabulary -- ONE home (WO-117, D220.3).

Every accepted deviation (waiver) in the fleet must sit in one of the
four permitted terminal classes D220.2 closes the waiver set to. The
classifier below is the census's mechanical reading of a waiver's
``basis`` text, keyed on the F131/F132/F133 exclusion vocabulary the
cycle-35 burn-down left at every remaining waiver:

* class ``a`` -- structural conformance edges (import/impl bindings, no
  scalar window exists on the edge; D195.3/D213/D215). Every such basis
  says "conformance edge".
* class ``b`` -- D195-gated conformance windows (the owner queue). The
  fleet's window halves surface as named DEFERRALS
  (``conformance_windows_unresolved``) covered by class-a edge waivers,
  so this class is empty in today's ledger -- kept because D220.2 names
  it, and a future waiver written directly against a D195 window must
  classify here, not fall to a finding.
* class ``c`` -- named machinery exclusions carrying a design-log
  F-number / work-order citation and a reopen criterion (F126.1 model
  gaps, the translate() wall, D103/D102 residuals, WO113-F1..F5
  realizer gaps, F132.3 process families, the WO-113 cost-marker wall,
  rule-pack engine inputs, WO-27/WO-33/WO-48/WO-60/WO-74/WO-86 walls).
* class ``d`` -- author-intent exclusions: physical-evidence memos
  (FAI/qual/proto lots), D224.1 sourcing refusals (a vendor table that
  cannot be verified offline), and deliberate non-declarations recorded
  in-file.

An UNCLASSIFIABLE basis is a finding, not a shrug (D220.3): the fleet
leg fails the census on any waiver this function returns ``None`` for.

Precedence (most-specific first): a (the edge vocabulary is exact),
then d (author-intent markers are rare and explicit), then b, then c
(the broad machinery vocabulary). A basis matching none is ``None``.
"""

from __future__ import annotations

import re

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The four permitted classes, in golden/report order.
# frob:doc docs/modules/tools.md#health-waiver-classes
WAIVER_CLASSES: tuple[str, ...] = ("a", "b", "c", "d")

# Class a: structural conformance edges. The D195.3/D213/D215 burn-down
# left the phrase "conformance edge" on every such basis.
_CLASS_A = re.compile(r"conformance edge")

# Class d: author-intent / physical-evidence / D224.1-refusal markers.
# Explicit and rare by design -- each phrase below appears on a basis an
# AUTHOR wrote as intent or measured evidence, never on machinery text.
_CLASS_D = re.compile(
    r"proven FAI|report VR-|proto lot|survived GEVS|measured .*ok"
    r"|by design|deliberately NOT declared|does not publish"
    r"|does not declare|never fabricated|intended-behavior"
    r"|separately-computed"
)

# Class b: a waiver written directly against a D195-gated conformance
# window (owner queue). Distinct from class a: it names the window, not
# the edge.
_CLASS_B = re.compile(r"D195(?!\.3).*window|conformance window")

# Class c: named machinery exclusions. Broad by design (the residue IS
# machinery, F133), but every alternation below still demands a NAMED
# citation or wall: an F/D/WO number, the F126.1 model-gap phrasing, or
# one of the enumerated machinery walls the design log dispositioned.
_CLASS_C = re.compile(
    r"F1\d\d(\.\d)?|WO-?\d+|WO\d+-F\d+|D10[23]|D19[45]|D21[56]"
    r"|model gap|translate\(\) wall|machinery residual|machinery escalation"
    r"|record chain|realizes no geometry|non_scalar|indeterminate.chain"
    r"|rule-pack deferral|no engine input|lowering surface|lowering drops"
    r"|frame-chain cut|record gap|names no std\.civil|inputs_missing"
    r"|no frame model|matches no registered route|scalar request shape"
    r"|given_unresolved"
)


# frob:doc docs/modules/tools.md#health-waiver-classes
def classify_basis(basis: str) -> str | None:
    """Map one waiver ``basis`` text to its D220.2 class (or ``None``).

    ``None`` means the waiver sits OUTSIDE the closed class set -- the
    caller treats that as a census failure (D220.3), never a shrug.
    """
    if _CLASS_A.search(basis):
        return "a"
    if _CLASS_D.search(basis):
        return "d"
    if _CLASS_B.search(basis):
        return "b"
    if _CLASS_C.search(basis):
        return "c"
    _log.debug("waiver basis classifies to NO D220.2 class: %r", basis[:160])
    return None


# frob:doc docs/modules/tools.md#health-waiver-classes
def classify_deviations(bases: list[str]) -> tuple[dict[str, int], list[str]]:
    """Count waiver rows per class; return ``(counts, unclassified)``.

    ``counts`` always carries every class key (zero-filled) so the
    census golden's shape is stable; ``unclassified`` returns the
    offending basis texts for the fleet leg's named failure row.
    """
    counts: dict[str, int] = dict.fromkeys(WAIVER_CLASSES, 0)
    unclassified: list[str] = []
    for basis in bases:
        cls = classify_basis(basis)
        if cls is None:
            unclassified.append(basis)
        else:
            counts[cls] += 1
    return counts, unclassified
