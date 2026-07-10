# WO-84 -- Record-path resolution for CLI builds

Status: in-progress (dispatched with the cycle-33 support wave)
Language: Python
Spec: design-log 2026-07-10-cycle-33 D192/F114; regolith/09 sec. 2-3
  (lockfile pins, INV-22); toolchain/27-costing.md (record loaders);
  toolchain/29-interaction-surface.md (config doctrine, WO-59);
  WO-48 close-out (frame_context), WO-69 (plan_context).

## Goal

`[depends] "std.*"` in a project's `magnetite.toml` must actually
reach the record loaders when a build runs through the CLI, so a
flagship's `regolith build --release` discharges exactly what its
committed tests prove dischargeable. Today the CLI passes no record
search paths at all (F114's root-cause chain): every stdlib-backed
claim defers with `frame_section_family_not_landed` /
`cost_record_unresolved` on every one of the 16 corpus projects.

## Deliverables

1. ONE resolver in `python/regolith/magnetite/`:
   `resolve_record_search_paths(project_root)` returning the record
   search-path roots for the project's `std.*` dependencies.
   Precedence: explicit config key (config doctrine) > vendored
   copies under the project > development fallback (walk up to a
   `stdlib/` containing the `std.quantities` sentinel). Unresolved
   dependencies are logged, not errors (the per-obligation honest
   deferrals already carry the user-facing story).
2. `staged_build` gains `frame_record_paths` / `plan_record_paths`
   mirroring the existing `cost_record_paths`, forwarded to the
   inner build (`load_cost_context` / `load_frame_context` /
   `load_plan_context`).
3. Every discharge-running CLI verb (`build`, `ship`, `optimize`,
   `test`) resolves and threads all three path sets.
4. Tests: resolver unit tests (config override, vendor preference,
   dev-walk, missing-package honesty); one integration test from a
   non-repo-root CWD proving a std.*-backed obligation resolves its
   record through the CLI entry path.
5. Docs: build-verb docstring + the guide page that describes
   std.* consumption, same change.

## Acceptance criteria

- `regolith build --release examples/flagships/timber_pavilion`
  resolves the `timber_sawn` family (11 candidates reach the WO-65
  section search) and the `construction` cost profile's rate
  record, from any CWD.
- Lockfile record-pin semantics unchanged (INV-22).
- No SCHEMA_VERSION bump; Rust core untouched.
- `make check` green.

## Dependencies

None (WO-59 config doctrine and WO-48/54/69 context loaders all
landed). Blocks honest interpretation of every fleet release build.
