# WO-52: fluorite `Mixer` + the compressible-regime corpus (D141/D142)

Status: todo
Depends: WO-31/32 (done), WO-49 (the medium-binding check this
extends -- land WO-49 first or together; the mixer boundary
treatment plugs into its consistency check).
Language: Rust (`regolith-syntax` component row, `regolith-lower`
medium-boundary treatment) + fixtures.
Spec: docs/spec/fluorite/02-language.md sec. 3 (`Mixer`, D142) +
sec. 1 (the boundary rule), docs/spec/fluorite/01-overview.md
(amended scope), docs/spec/fluorite/04-open-questions.md (FOPEN-1/2
closure records), design-log 2026-07-08-cycle-27 D141/D142.

## Goal

Mixing designs and gas-regime designs are first-class: `Mixer` is a
declared medium boundary the consistency checker respects, and the
corpus proves the compressible-regime route (claims unchanged,
regime tags select the tier).

## Deliverables

1. `Mixer(outlet=<medium>)` parses as an ordinary component; its
   terminals are medium-subnet BOUNDARIES in the WO-49 consistency
   check (each side its own single-medium subnet; outlet medium
   declared); a mixer whose outlet medium lacks property records is
   the ordinary phantom-record diagnostic.
2. The flownet payload carries mixer edges with their declared
   outlet `MediumRef` -- per-subnet payloads stay structurally
   single-medium (D142's whole point); assert it in the payload
   determinism test.
3. Corpus: `gn2_purge.fluo` (gas blowdown through a regulator and
   long line: `choked` + `fluids.mach` screening claims, dp claim
   whose margin will demand the compressible tier -- honestly
   indeterminate until feldspar Phase 2 registers it) and a
   `Mixer`-exercising fixture (pressurant-into-ullage tank
   interface, the FOPEN-1 expected case). Negative fixture: a mixer
   used to LAUNDER a medium mismatch (undeclared outlet) must still
   diagnose.
4. fluorite/04 FOPEN-1 entry flips to CLOSED (with WO-49) in the
   same change; the tracks README file map gains both rows.

## Acceptance criteria

- Mixed-media designs with a declared Mixer pass the consistency
  check; the same topology without it fails with WO-49's
  diagnostic; goldens for the existing corpus unchanged.
- gn2_purge lowers to obligations whose regime tags ride the D97
  channel (assert the request content), staying honestly
  indeterminate absent a compressible model.
- `make check` green; FOPEN-1 marked CLOSED.

## Non-goals

- Composition-varying mixtures (outlet medium is DECLARED; solved
  composition is rejected by D142).
- The compressible solver itself (feldspar WO-20).
