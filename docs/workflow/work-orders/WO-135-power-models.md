# WO-135 -- Power models: closed-form built-ins (lithos) + certified solvers (feldspar) (D248.3/AD-37)

Status: open (gated on WO-132/133; the feldspar half may start on
  the charter alone)
Language: Python (lithos harness built-ins) + feldspar (its repo, its
  own WO, pushed there).
Spec: charter 43 secs. 3 + 5 (NORMATIVE); AD-37 + charter 39 +
  feldspar spec 12 (THE BOUNDARY RULE, shared verbatim: pad-check
  closed forms are lithos harness built-ins; numerics/certified
  solving is feldspar; ONE home per physics, no double-homes);
  D250 (safety honesty -- every model cites standard + edition; no
  typical-value fallbacks; arc flash is certified-solver-only);
  INV-14 (evidence tiers -- the machinery that ENFORCES D250.4).

## Goal

Every `elec.power.*` claim discharges through a real model over real
declared inputs, at the right trust tier -- and the life-safety
claims cannot be discharged by a screening estimate wearing a
study's clothes.

## Deliverables (lithos half -- closed-form built-ins)

1. NEC Art. 220 demand load (connected -> demand, by load class).
2. Conductor voltage drop (single/three phase, PF, run length).
3. Ampacity with derating (NEC 310.15: temperature correction +
   conduit fill), against the WO-134 tables.
4. Transformer %Z single-source bus fault (the screening estimate).
5. Motor starting voltage dip.
6. Transformer loading; power factor.
Each cites its standard AND edition in its docstring/citation field
(D250.1; the WO-114 calc book prints it).

## Deliverables (feldspar half -- certified/numeric; its repo)

7. Load flow (multi-source, with contributions).
8. IEC 60909 / ANSI short circuit WITH motor contribution.
9. IEEE 1584-2018 arc-flash incident energy, boundary, PPE category.
10. Protective-device coordination (curve intersection over the
    WO-134 curves; defers by name where a curve is an honest
    absence).
11. IEEE 519 harmonics.

## Acceptance

- `arc_flash` CANNOT reach release trust through a lithos built-in:
  the built-in screening estimate is tier-labeled and a test PROVES
  the release gate refuses it as an arc-flash discharge (D250.4 via
  INV-14). This test is the most important one in the WO.
- Every model's citation is present and printed on its calc sheet.
- A claim whose input is undeclared (utility fault current, X/R,
  locked-rotor code, actual %Z) DEFERS by name -- a test proves no
  default is ever substituted (D250.3).
- Both repos' gates green; no double-homes (the charter 39 / spec 12
  sweep proves it).

## Escalation

If a physics belongs in neither home cleanly, STOP -- the boundary
rule is shared verbatim between the repos precisely so it cannot
drift; ambiguity is a coordinator call.
