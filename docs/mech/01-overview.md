# hematite Overview

> Spec 0.13. Named **hematite** (`.hem` files) -- cycle 9, D78.

## 1. Vision

A declarative, goal-oriented language for mechanical design, architected
like a modern compiled language: typed source, multiple IRs, lowering
passes, static verification before expensive computation, reproducible
builds.

```
Traditional:  Geometry -> (manual analysis) -> "does it work?"
hematite:         Claims + Contracts -> (solvers, provers) -> Geometry + Evidence
```

The designer declares **what a part must do**, **how it will be made**,
and **what it promises to other parts**. Dimensions and tolerances may be
left unresolved; the system allocates them. Every geometric reference has
exactly one valid interpretation, enforced statically. Every physical
claim is either backed by evidence or loudly marked as assumed.

## 2. What hematite inherits vs defines

Inherited from the substrate (see `../substrate/`), used without change:

- the three mantras and the defaults test (`01-principles.md`)
- quantity core, intervals, zones, equality ban (`02-quantity-core.md`)
- the five-source value grammar (`03-value-sources.md`)
- the contract model: interfaces, T1/T2/T3 conformance, refinement,
  vendor artifacts, evidence clauses (`04-contracts.md`)
- entity DB, queries, single ownership, borrows, datums, symmetry/`any`
  (`05-ownership-and-queries.md`)
- stages, concurrent scopes, snapshot/commit (`06-execution-model.md`)
- claims, obligations, margin-driven discharge, the orchestrator loop,
  `todo!`/`assume!` (`07-claims-and-evidence.md`)
- the L0-L6 lowering shape (`08-lowering-architecture.md`)
- build tiers, lockfile, diagnostics, coherence (`09-build-and-lockfile.md`)

hematite-specific content, defined in this directory:

- the geometric entity kinds and feature vocabulary (per process module)
- the sketch (`profile`) layer: walk + constraints
- setups and workholding (`setup`, `hold:`, datum letters, `flip about`)
- GD&T, ISO fits, process capability tables, tolerance budgets
- matings (bolted flange, press fit, bearing mount, ...) and the
  DOF/Gruebler ledger
- the mech harness packs: beam theory, joint diagrams, Lame, FEA tiers
- backends: STEP/AP242+PMI, drawings, G-code, BOM

## 3. Non-goals (for now)

- Replacing interactive surfacing / industrial design (Class-A surfaces,
  sculpting). Freehand splines do not exist in the language; curves are
  `from_table(...)` or `from_fn(...)`.
- Building a geometry kernel: we drive OpenCASCADE (via CadQuery /
  Build123d initially).
- A GUI. CLI-first for a long time; previews/LSP/round-trip GUI are
  projections of text.
- Mechanisms beyond the DOF ledger (kinematic sweeps, collision over
  motion) -- v2 model packs over existing hooks; no syntax change
  needed (OPEN-3 closed for v1, cycle 8, D64).

## 4. The two on-ramps

Both are pipeline shortcuts, not special modes:

- **Greenfield, top-down:** write interfaces + connections + boundary
  first; the assembly verifies with zero parts (L0->L2). Parts then
  implement load-annotated contracts independently.
- **Brownfield, verify-first:** `stage src: import("legacy.step") sealed`
  enters at L4; retrofit contracts onto measured geometry and get the
  verification machinery with zero feature-modeling adoption cost.

## 5. Prior art map

OpenCASCADE / CadQuery / Build123d (kernel; nearest selector prior art --
study their limits) - FreeCAD toponaming failure (the bug class the
ownership model exists to kill) - MLIR (lowering architecture) -
SolveSpace (sketch solver) - OpenSCAD (declarative-without-DFM; what to
exceed) - ISO 286, ASME Y14.5 GD&T, VDI 2230 (fits, tolerances,
bolted-joint math) - Dafny/Why3 (obligation-evidence architecture) -
Modelica (acausal physical modeling -- contrast: hematite separates claim
from model deliberately) - component mode synthesis / Guyan reduction
(stiffness-promise verification) - Machinery's Handbook (DFM rules).
