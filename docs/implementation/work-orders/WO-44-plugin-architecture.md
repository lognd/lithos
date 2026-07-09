# WO-44: Plugin architecture v1 (`regolith.plugins`, AD-26)

Status: todo
Depends: WO-20 (done -- the discipline being generalized), WO-21
(done -- signature-carried trust), WO-25 framework + WO-37 pack seam
(landed -- the two seams being folded in). Feldspar's entry-point
migration is a named cross-repo follow-up, not a blocker.
Language: Python (`regolith.plugins` new module + touched seams);
no Rust changes; no schema changes to obligations (plugin versions
already fold into evidence keys via the WO-20 mechanism).
Spec: 00-architecture.md AD-26 (NORMATIVE), design-log
2026-07-08-cycle-26 D134; WO-20's pack discovery + conformance
suite (`tests/packs/`) as the pattern; regolith/13 INV-1 (keys move
on plugin upgrade), INV-14/INV-28 (trust is signature-carried).

## Goal

ONE typed discovery seam for every out-of-wheel extension: model
packs, rule packs, MCU family packs, manufacturing backends. Four
grown-independently discovery paths become one auditable mechanism
with deterministic composition, loud duplicates, versioned identity,
and a CLI listing.

## Deliverables

1. `python/regolith/plugins.py` (or package if it needs >1 module):
   `PluginKind` (closed enum: `model_pack`, `rule_pack`, `mcu_pack`,
   `backend`), `PluginManifest` (pydantic frozen: `id`, `kind`,
   `version`, kind-specific registration callable), discovery over
   the `regolith.plugins` entry-point group: deterministic (sorted
   by id), duplicate ids -> a typed error value surfaced in the
   build report (never last-wins), a malformed manifest -> a typed
   error value naming the distribution (never a crash).
2. Migration of the four seams, each behind its existing public API
   (callers unchanged): WO-20's `regolith.model_packs` loader
   delegates to the group (`kind=model_pack`); WO-37's MCU pack seam
   (`realizer/firmware/packs.py`) discovers `kind=mcu_pack`; WO-25's
   backend framework discovers `kind=backend`; WO-28's engine gets
   the `rule_pack` kind RESERVED with a loader stub that returns an
   empty set + a `# TODO(WO-28)` marker (its in-language pack format
   is WO-28's remainder -- do not invent it here).
3. `BuildReport.pack_errors` -> `plugin_errors` (one rename, all
   call sites + tests; keep the field's report semantics identical).
4. `regolith plugin list` CLI verb: id, kind, version, source
   distribution; stdout is data (`--json` supported), logs stderr.
5. Conformance tests extending `tests/packs/`: a fixture plugin per
   kind, the duplicate-id refusal, the malformed-manifest refusal,
   determinism (shuffled discovery order -> identical composition),
   and an INV-1 test that bumping a fixture plugin's version moves
   dependent evidence keys (the WO-20 test, re-pointed).
6. Docs: AD-26 flipped from "decided" to "landed" with a one-line
   note; regolith/11 sec. 2 gains a sentence that pack DISTRIBUTION
   is magnetite's job while RUNTIME discovery is `regolith.plugins`;
   a `# Cross-repo follow-up` note in the WO close-out for
   feldspar's `pyproject.toml` entry-point move (tracked in
   feldspar's TODO.md, one line, same release).

## Acceptance criteria

- All four kinds discoverable through the one group; the old
  `regolith.model_packs` group name is GONE from this repo (grep
  clean) -- feldspar keeps working only after its follow-up, which
  is why the conformance fixture (not feldspar) proves the seam.
- Duplicate/malformed cases are loud typed values in the report;
  nothing raises across a plugin boundary.
- `regolith plugin list` shows the fixture plugins; evidence keys
  move on fixture version bump.
- `make check` green.

## Non-goals

- Language tracks as plugins (AD-26 v1 non-goal, reopen criterion
  recorded there).
- Plugin sandboxing/capability limits: plugins are code you chose to
  install; trust stays evidence-signature-carried (INV-14), nothing
  else.
- A plugin REGISTRY (discovery is entry points on the installed
  environment; distribution is ordinary magnetite/PyPI packaging).
