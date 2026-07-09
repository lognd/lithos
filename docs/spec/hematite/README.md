# hematite -- Declarative Mechanical Design

> Spec 0.14 (unified). NAMED **hematite** (`.hema`) in cycle 9 (D78).
> Consolidates draft 0.1, the
> 0.2 rewrite, the syntax and lowering audit (FIX-1..10, all adopted),
> and the 0.3 vocabulary pass (V1..V8) into one coherent tree.
> 0.13 -> 0.14 (cycle 18, WO-28 spec cycle): the `process` rule-pack
> grammar landed (`02-language.md` sec. 10, `04-vocabulary.md`
> sec. I5).

hematite is the mechanical instantiation of the regolith (`../regolith/`).
These documents contain only what is mechanical; everything shared --
value sources, contracts, ownership, claims/evidence, lowering shape,
build system -- is specified once in the regolith and referenced here.

| doc | contents |
|---|---|
| `01-overview.md` | vision, scope, what is mech-specific vs inherited |
| `02-language.md` | parts, stages, setups, scopes, features, profiles, queries, datums |
| `03-contracts-and-assemblies.md` | interfaces, impls, matings, assemblies, tolerances, fits, budgets |
| `04-vocabulary.md` | every keyword: position, meaning, lowering; retired list |
| `05-lowering.md` | the mech L0-L6 stack and the construct x level matrix |
| `06-roadmap.md` | implementation phases A-E |
| `07-open-questions.md` | OPEN / SEAM / watchlist, consolidated from all drafts |

Status: design phase, spec-complete as of 0.13 -- the technical open
queue is empty (`07-open-questions.md`; deferrals carry explicit
reopen criteria). Nothing is implemented; this tree is the agreed
design direction and the contract the work orders
(`../../workflow/`) build against. Naming (OPEN-10) is the one
open decision.
