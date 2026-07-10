# 36 -- Board correctness: the zero-silent-hazard program (design charter; D187, cycle 32)

> Charter widening D186's SI discipline into the full professional
> board-review checklist, encoded: every known hardware failure
> class carries a demanded claim or cited rule; hazards ship only
> as attributed acceptances, never silence. Machinery: WO-79
> (wave 1); the catalog grows forever by the post-mortem law
> (every real hardware bug becomes a rule in the same change that
> diagnoses it). Where this doc and a WO body conflict, this doc
> wins.

## 1. The doctrine

"Impossible to get hardware bugs" is not provable; what IS
enforceable: (a) an encoded checklist -- each check a `demand:`
rule or claim with a `per:` citation (vendor app note, standard,
or a design-log post-mortem entry); (b) coverage visibility -- the
parity/audit surface lists which rule families ran against a
board and which were N/A-by-declaration (silence unrepresentable);
(c) the waive ladder as the ONLY exception path. The checklist is
a living pack: incompleteness is a known, named state, not a lie.

## 2. Wave-1 rule families (WO-79; each: >= 3 rules, citations, pass/fail fixtures)

1. **PDN/decoupling**: per-supply-pin shunt-C presence + value
   class; bulk-per-rail presence; (distance bounds activate where
   layout exists -- realized-fact tier).
2. **Bring-up/config**: every strap/boot/config pin explicitly
   pulled or driven (never floating); programming/debug header
   presence per MCU family record; reset supervision on rails that
   need it (per the MCU record's declared requirement).
3. **Interface protection**: ESD on every external-world connector
   class; VBUS-class inrush/protection; TVS presence on declared
   exposed nets.
4. **Clock discipline**: crystal load-cap sizing (calculated,
   evidence-visible, per the crystal record's CL); one-driver
   clock nets (the landed ledger already enforces single-driver --
   extend with the source-termination rule via D186's models).
5. **DFT**: declared test-point coverage over named critical nets.

## 3. Interaction + growth

Rules ride AD-21 verbatim (two severities, waive-only overrides,
static vs realized-fact tiers derived from referenced facts).
Component-record fields the rules need (crystal CL, MCU strap
tables, connector exposure class) enter stdlib under AD-34 -- a
rule may not invent a fact a record does not state. The post-mortem
law is normative: a diagnosed hardware bug without a same-change
rule is an incomplete fix.

## 4. Non-goals (reopen criteria)

Full EMC compliance prediction (pre-scan only, honestly labeled);
SI crosstalk/eye analysis (charter 35's own non-goal); automated
component placement. Reopen each on flagship evidence.

## 5. Acceptance shape (WO-79)

The wave-1 families landed as in-language packs with fixtures both
ways; a deliberately-hazardous fixture board trips every family;
the mainboard/printer flagship boards run the packs with zero
silent gaps (each family either fires, passes, or is N/A by an
explicit declaration); coverage renders in the audit surface.
