# The Regolith

The domain-neutral layer both languages are built on. Nothing in this
directory mentions faces, bends, nets, or clocks except as examples; every
concept here is defined abstractly and then *bound* per domain (see
`10-domain-binding.md` for the full binding table).

The regolith is not a hidden implementation detail -- it is the reason the
two languages feel the same. A designer who has internalized value sources,
contracts, ownership, and the claim/evidence loop in one domain carries all
of it to the other; only the vocabulary of entities and physics changes.

## Contents

| doc | contents |
|---|---|
| `01-principles.md` | the three mantras, the defaults test, the four-component system architecture |
| `02-quantity-core.md` | typed physical quantities, units, intervals, zones, shared property registries |
| `03-value-sources.md` | the five-source grammar: who decides every number, and where that decision is recorded |
| `04-contracts.md` | interfaces, implementations, conformance tiers, connections, refinement, vendor artifacts |
| `05-ownership-and-queries.md` | the entity database, semantic queries, single ownership, borrows, joins, datums, symmetry and `any` |
| `06-execution-model.md` | stages, concurrent scopes, snapshot reads, commit and merge rules |
| `07-claims-and-evidence.md` | claims, obligations, signatures, the model registry, margin-driven discharge, the orchestrator loop, `todo!` and `assume!` |
| `08-lowering-architecture.md` | the generic L0-L6 lowering stack and the check-placement law |
| `09-build-and-lockfile.md` | build tiers, the lockfile, diagnostics, waivers, trait coherence |
| `10-domain-binding.md` | concept-by-concept binding for mech and elec; how a new domain would be added |
| `11-packages-and-stdlib.md` | the package manager (magnetite), registry record standard, trust tiers, the standard library; projects, files, and team workflow |
| `12-overrides-and-hints.md` | the expert ladder: assert, pin, hint, override-by-evidence, force-model, assume, waive; `policy:` blocks; the audit surface |
| `13-invariants.md` | the invariant ledger: every load-bearing guarantee with mechanism, proof argument, and test family; normative |

## One-paragraph summary

Every number in a design names its **value source** (who decides it). Every
artifact exposes **contracts** (interfaces) and consumes others' contracts
through **connections**; systems compute with promises, never with actuals.
Every reference to a piece of an artifact is a **semantic query** against an
entity database governed by **single ownership and borrows**, so no
reference is ever ambiguous. Construction happens in **concurrent scopes**
that commit atomically. Everything the designer asserts about physics is a
**claim**, lowered to a self-contained **obligation**, discharged by a
registry model whose error is charged against the margin, returning
**evidence**. The whole pipeline is a fixed **lowering stack** where the
cheapest tier that can catch an error owns it, and every resolved decision
lands in a **lockfile** where a diff will surface it.
