# WO-162 -- promotion-ticket rule gains teeth (AD-22 teeth)

Status: open (Depends: none)
Language: Python (the check itself, whichever home it lands in --
  see "Enforcement home" below) + `frob.toml` policy config; no Rust.
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 2 item 2
  (AD-22's promotion rule, hardened); `docs/spec/toolchain/00-
  architecture.md` AD-22 (original rule text); design-log D267.

## Goal

Every forward-authored contract type (a hand-written stand-in for a
not-yet-promoted, properly-schema'd type -- today's standing instance
is `FeatureProgram` in `python/regolith/orchestrator/programs.py`,
per hematite/07 sec. 2a's deferral) must carry a `frob:ticket` edge
to an OPEN promotion ticket for as long as the hand-written form
exists. Promotion (landing the real schema'd type) closes that
ticket AND deletes the shadow type in the SAME change -- never
separately. This WO adds the CHECK that makes an unbound
forward-authored type a build failure, not just a documented
convention.

## Deliverables

1. Identify every current forward-authored contract type in the repo
   (start from `FeatureProgram`; grep for the marker convention this
   WO establishes -- see item 2 -- to find any others once the marker
   exists; today's known instance is the only one named by the
   charter, but do not assume it is the only one without checking:
   grep `class.*Program` and any type whose docstring says
   "forward-authored" / "shadow" / "pre-promotion" / "hand-written
   stand-in").
2. Establish the marker convention: a `frob:ticket T-####` comment
   directive immediately above the forward-authored type's class
   definition (same DSL family as `frob:doc`/`frob:tests`/
   `frob:invariant`/`frob:todo`/`frob:waive` per this repo's
   CLAUDE.md). Add it to `FeatureProgram` now, pointing at
   `FeatureProgram`'s existing promotion ticket if one already exists
   in `tickets.md` (search first -- do not create a duplicate); if
   none exists, create ONE new ticket ("promote FeatureProgram out of
   hand-written form") and point the directive at it.
3. **Enforcement home (design this honestly, do not guess a facade):**
   evaluate two candidate homes and pick one, recording the reasoning
   in this WO's close-out:
   - (a) a `frob` policy rule (tree-sitter query or equivalent,
     alongside the existing `[[policy.forbidden-import]]`-style rules
     in `frob.toml`) that finds every class carrying a
     `frob:ticket`-adjacent marker convention (or, inversely, every
     class matching a "forward-authored" naming/docstring heuristic)
     and fails if the referenced ticket is not `state: queued` or
     `state: in-progress` (i.e. is missing, done, or does not exist) --
     mirrors how other frob DSL directives are already gated;
   - (b) a `make health` / `frob check --only gates` leg: a small
     script under `tools/` (mirroring `tools/health`'s D264-exception
     pattern) that walks the AST for the marker and cross-checks
     `tickets.md`.
   Prefer (a) if the existing policy-rule engine can express "ticket
   referenced by this directive must be open" without new engine
   surface; fall back to (b) only if it cannot, and say why.
4. Wire the new gate into `frob check` (or `make check`, if (b) was
   chosen) so a forward-authored type with a missing/closed ticket
   is a hard failure, and a properly promoted type (marker removed
   in the same change the ticket closes) never trips it.

## Non-goals

- No actual promotion of `FeatureProgram` in this WO -- this WO wires
  the ENFORCEMENT and marks the standing instance; the promotion
  itself is the ticket this WO creates/points at, a separate future
  dispatch.
- No new contract-type work.

## Acceptance

- `FeatureProgram`'s class definition carries the `frob:ticket`
  marker, pointing at a real, open ticket in `tickets.md`.
- A new negative-path test: a scratch forward-authored-style class
  with a marker pointing at a `state: done` (or nonexistent) ticket
  fails the new gate; a class with a marker pointing at a `state:
  queued`/`in-progress` ticket passes.
- `frob check --only gates` (or `make check` if home (b)) shows the
  new gate exercised with 0 unexpected failures against the current
  tree (i.e. `FeatureProgram` itself passes because its own ticket is
  open).
- `make check` green.
</content>
