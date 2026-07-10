# WO-78: signal integrity machinery (records, claims, stackup select, SI sheet)

Status: todo (dispatch AFTER feldspar WO-25 lands -- the models are
the discharge path; its close-out names the direction signatures)
Depends: feldspar WO-25 (impedance/termination models; HARD),
WO-55/56 (engine + select), WO-50/61 (table sheets), WO-40/28
(lint/rule engine for the erc: rules), AD-34 (stackup records).
NO SCHEMA_VERSION bump expected; if a payload field proves
necessary, escalate per the D168 train rule before bumping.
Language: records + Rust only if a claim-form grammar gap is
proven (escalate first) + Python (translate wiring, sheet
producer, fixtures).
Spec: docs/spec/toolchain/35-signal-integrity.md (NORMATIVE),
design-log 2026-07-10-cycle-32 D186, 21-rule-packs.md (erc:),
28-optimization.md (boundary-finding + select).

## Deliverables

1. `std.elec.stackups`: >= 6 fab-published stackup records (2/4/6
   layer classes), AD-34-cited.
2. Claim wiring: `elec.impedance(...) within [..]` (SE + diff) and
   `elec.termination(..., scheme=...)` routed through translate to
   the feldspar WO-25 directions; pre-layout width/gap as
   `in [lo, hi]` slots solved by the engine against the impedance
   claim (calculation inputs/outputs in evidence).
3. erc: seed rules (AD-21 pack): supply-pin ac_shunt presence
   (distance-bounded where layout exists, static presence
   otherwise), declared high-speed class carries its scheme;
   pass/fail fixtures per the rule-pack law.
4. Stackup `by select` demo: cost objective, impedance-feasibility
   screen, policy-flip test.
5. The SI table sheet producer (DrawingModel tables; WO-58/61
   conventions), golden-enrolled; parity classes every sized value.
6. Corpus exemplar board exercising all of it; docs (guide section
   + charter cross-refs + ledger).

## Acceptance criteria: charter 35 sec. 3, verbatim.
