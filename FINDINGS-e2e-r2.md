# Lithos audit round 2 (2026-07-09) -- NOT CONVERGED: 1 HIGH regression

## HIGH

### H1-REGRESSION. put_verified compares bare hex against the sha256:-prefixed IR hash; every clean elec ship via --build is falsely refused [FIXED]

**Fix applied:** `put_verified` in `python/regolith/backends/artifacts.py` now
compares `actual != digest.removeprefix("sha256:")` (matching the existing
`removeprefix("sha256:")` idiom already used at
`realizer/elec/realized.py:155`), so both a bare hex digest (mech's
`step_content_hash` convention) and a `"sha256:"`-prefixed digest (elec's
`kicad_pcb_content_hash` convention) verify correctly against the recomputed
bare SHA-256. The bytes are still stored under the caller's ORIGINAL digest
string (`put_at(digest, data)` unchanged), so the resolve key at
`backends/elec.py:113` and the `put_at` key convention are unaffected.
Confirmed only `cli/app.py:954` calls `put_verified` today (no mech path
currently calls it), but the fix makes the function correct for both digest
forms since `put_at`/`put_verified` are shared infrastructure.

Added two tests in `tests/backends/test_artifacts.py`:
`test_put_verified_accepts_matching_bytes_with_sha256_prefix` (fails before
the fix, passes after -- this is the crux, reproducing the false-refusal of
a clean elec board) and
`test_put_verified_refuses_tampered_bytes_with_sha256_prefix` (confirms
tampered bytes are still refused under a prefixed digest). Existing bare-digest
tests (`test_put_verified_accepts_matching_bytes`,
`test_put_verified_refuses_tampered_bytes`) still pass unchanged.

Verified: `uv run pytest -q tests/backends/test_artifacts.py
tests/backends/test_ship.py` (17 passed), full `uv run pytest -q` (987 passed,
2 skipped, 23 xfailed), `uv run ruff check` + `uv run ty check` on
artifacts.py (clean), `uv run ruff format --check .` (230 files formatted),
`make guard-core` (clean). No `_core.abi3.so` ABI mismatch was hit, so no
`maturin develop` rebuild was needed.

---

- Where: python/regolith/backends/artifacts.py put_verified (actual =
  hashlib.sha256(data).hexdigest(); if actual != digest). Call site cli/app.py
  ~955 passes layout.kicad_pcb_content_hash, which is ALWAYS "sha256:<hex>"
  (kicad.py:262 hash_pcb_file returns f"sha256:{digest}"; realized.py:79,155).
- Failure: ship --build with an elec board + on-disk pcb -> put_verified
  ("sha256:c3de...", good bytes) recomputes bare "c3de..." -> "c3de..." !=
  "sha256:c3de..." -> Err(native_artifact_hash_mismatch) -> raise Exit(1). A
  clean release is refused as tampered. The round-1 unit tests
  (test_put_verified_*) miss it because they feed a BARE hexdigest, not the
  prefixed form the real IR uses.
- Convention split to handle: mech step_content_hash is BARE
  (realizer/mech/interpreter.py:530); elec kicad_pcb_content_hash is PREFIXED.
  put_verified/put_at are shared, so the fix must accept both.
- Fix: in put_verified, normalize before comparing -- strip a leading "sha256:"
  from the supplied digest (or compare f"sha256:{actual}" when prefixed), and
  STORE under the caller's ORIGINAL digest string so resolve's key at elec.py:113
  still matches. Add a regression test feeding the real "sha256:"-prefixed digest
  (this is what the round-1 tests missed). Verify a mech (bare-hash) put_verified
  path, if any, still works.

Round-1 M1/M2/L1/L3 and the formatter/drawings/scaffold slices verified clean.
Two non-findings recorded: dead is_symlink() check after resolve() (containment
still holds); multi-segment ../ scaffold name escape (guarded by no-overwrite).
