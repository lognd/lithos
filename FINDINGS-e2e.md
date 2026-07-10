# Lithos audit round 1 (2026-07-09 e2e session) -- 1 HIGH / 2 MEDIUM / 3 LOW

## HIGH

### H1. Ship native-artifact priming trusts on-disk PCB bytes without verifying against the pinned content hash [FIXED]

FIXED: added `NativeArtifactStore.put_verified(digest, data)` in
`python/regolith/backends/artifacts.py`, which recomputes
`hashlib.sha256(data).hexdigest()` and returns `Err(BackendError(kind=
"native_artifact_hash_mismatch"))` on mismatch instead of trusting the
caller's digest (the store's own scheme is confirmed plain SHA-256 hex,
per the module docstring and `put()`'s own `hashlib.sha256` call --
NOT the `blake3:`-prefixed magnetite convention). `cli/app.py`'s ship
priming call site now calls `put_verified` instead of `put_at` and
refuses the ship (prints the diagnostic, `raise typer.Exit(EXIT_DIAGNOSTICS)`)
on `Err`. Tests: `tests/backends/test_artifacts.py::test_put_verified_accepts_matching_bytes`,
`::test_put_verified_refuses_tampered_bytes`.

- Where: python/regolith/cli/app.py ~904 (store.put_at(layout.kicad_pcb_content_hash,
  pcb_path.read_bytes())) + backends/artifacts.py:56 NativeArtifactStore.put_at
  (stores under caller-supplied digest, never recomputes/compares).
- Failure: build records kicad_pcb_content_hash=H; the on-disk board.kicad_pcb is
  then edited/stale; ship primes put_at(H, tampered_bytes) with no check, emits the
  tampered PCB, and signs a release over it -- manifest looks internally consistent.
- Fix: before priming, sha256(pcb_bytes) must equal layout.kicad_pcb_content_hash;
  on mismatch refuse the ship with a named diagnostic (nonzero exit). Add a
  put_verified(digest, data) / verify=True path on the store and use it here.

## MEDIUM

### M1. _FileTransport for file:// sources has no path confinement (dot-segment traversal / DoS) [FIXED]

FIXED: `_FileTransport` in `python/regolith/cli/app.py` now takes
`roots: tuple[Path, ...]` at construction (`_registry_client` builds it
from `registry.index_url`/`registry.archive_url`'s own directories when
they are `file://`), resolves each request path and requires
`resolved.is_relative_to(root)` for one of the roots, refuses symlinks
and non-regular files, and caps reads at `_FILE_TRANSPORT_MAX_READ_BYTES`
(8 MiB). Out-of-root/symlink/oversized requests get a 404/413, logged
as a warning. Tests: `tests/test_cli_vendor.py::test_fetch_with_dot_dot_package_name_is_refused`
(a `../secret.txt` package name refused, EXIT_DIAGNOSTICS, secret
content never in output) and `::test_fetch_prints_resolved_archive`
(normal in-root fetch still works); full existing vendor suite green.

- Where: cli/app.py:138-146 (_FileTransport.handle_request reads Path(url.path)
  verbatim), reachable via RegistryClient.fetch_index and the fetch CLI
  (package name is a user arg; httpx normalizes .. before the transport sees it).
- Failure: [sources] index_url=file:///srv/mirror; `reg magnetite fetch
  "../../../../etc/passwd" 1.0` reads /etc/passwd (existence oracle + parse
  attempt); /dev/zero or a pipe blocks read_bytes() (DoS).
- Fix: pass the registry root into the transport; require
  resolved.is_relative_to(root), reject symlinks/non-is_file(), cap read size.
  Archive leg is safe (blake3 hex filename can't carry ..).

### M2. DXF TEXT values not newline-stripped -> stream corruption/injection [FIXED]

FIXED: added `_sanitize_text_value` in
`python/regolith/backends/drawings/renderer_dxf.py`, applied in
`_text_entity` after the existing ASCII pass: `\n`/`\r`/any control
char (`ord < 0x20`) is replaced with a space, logged as a warning when
it fires. Combined with the L2 fix below (same helper). Tests:
`tests/backends/test_drawings.py::TestDxfRenderer::test_text_value_newline_is_neutralized_group_pairing_intact`
(a `"0\nSECTION"` value still produces exactly 7 well-formed code/value
pairs, no raw `\n`/`\r` in the emitted value line) and
`::test_sanitize_text_value_replaces_control_chars_with_space`.

- Where: backends/drawings/renderer_dxf.py:_text_entity (~200) + _group; values
  from annotation text, table cells, title-block subject/title. R12 is strictly
  line-paired; an embedded \n desyncs every following code/value pair.
- Failure: a table cell / annotation / subject containing "0\nSECTION" splits
  across lines -> parse error or injected entity. PDF is safe (parens delimit).
- Fix: in _text_entity strip/replace \n and \r (and control chars) after the
  ASCII pass, or Err on them.

## LOW

### L1. Scaffold accepts ".." as the derived package name [FIXED]

FIXED: `scaffold_project` in `python/regolith/magnetite/scaffold.py`
now rejects `package_name in (".", "..")` with a named `invalid_name`
`DocError`, right after the existing empty-name guard (same `Err`
kind, so callers already handling `invalid_name` need no change).
NOTE: the finding's suggested "non-identifier" reject was tried first
(`not package_name.isidentifier()`) but reverted -- it broke the
existing `test_new_and_magnetite_new_produce_identical_results` test,
which scaffolds a project named `top-proj` (a hyphenated but
completely legitimate package name); only `.`/`..` are the actual
traversal-smuggling shapes the finding's failure scenario describes,
so the fix is scoped to exactly those. Tests:
`tests/magnetite/test_scaffold.py::test_scaffold_refuses_dotdot_name`
(`magnetite new ".."`), `::test_scaffold_refuses_dotdot_path_component`
(`"sub/.."`), `::test_scaffold_refuses_dotdot_absolute_name` (absolute
NAME ending in `..`). A literal `"."` NAME is not independently
testable the same way -- `Path(parent / ".")` normalizes the `.`
segment away before `.name` is read, so it never reaches
`scaffold_project` as a literal `"."`; the guard still covers it
defensively.

- Where: magnetite/scaffold.py:scaffold_project (~90). Path(...)/".." has
  .name == ".." (truthy), passes the empty-name guard; name ".." lands in
  magnetite.toml and project_dir points at the parent's parent.
- Fix: reject ".", "..", and non-identifier names with an invalid_name DocError.

### L2. PDF/DXF silently replace non-ASCII text with "?" instead of rejecting [FIXED]

FIXED: chose the documented-lossy-replacement contract, not rejection
(RECOMMENDATION's fallback option) -- neither `_text_entity`/`_group`
in the DXF renderer nor `_ContentBuilder`/`_pdf_text` in the PDF
renderer have a `Result`-return seam without a larger refactor of the
whole `render_dxf`/`render_pdf` call graph (every leaf helper returns
`list[str]`/`str` directly, composed by plain concatenation). Instead:
both `_sanitize_text_value` (DXF) and `_pdf_text` (PDF) now log a
`WARNING` naming the offending value whenever the ASCII pass actually
changes it, and both docstrings now say plainly "lossily replaced with
`?`, not rejected" so the contract is explicit rather than implicit.
Tests: `tests/backends/test_drawings.py::TestDxfRenderer::test_sanitize_text_value_replaces_non_ascii_with_question_mark`,
`::TestPdfRenderer::test_pdf_text_replaces_non_ascii_with_question_mark`.

- Where: renderer_pdf.py:_pdf_text + _ContentBuilder.to_bytes; renderer_dxf.py:
  _text_entity (all encode("ascii", errors="replace")). Silent data corruption
  in a deterministic-golden path; PDF docstring implies rejection.
- Fix: decide the contract -- Err/diagnostic on non-ASCII, or document the lossy
  replacement at the API boundary. No silent "?".

### L3. check clean-summary and _summary_line count warnings with different substrings [FIXED]

FIXED: added `_count_warnings(rendered)` in `python/regolith/cli/app.py`
(counts `"warning["`, the honest total, matching the finding's
recommendation) and made both the single-shot clean-summary (`check`'s
own `if ok:` branch) and `_summary_line` (used by `check --watch`) call
it, so a non-L0 warning now reports the same count in both paths. Test:
`tests/test_cli_app.py::test_summary_line_and_clean_message_agree_on_non_l0_warning_count`.

- Where: cli/app.py:284 (rendered.count("warning[")) vs :252 (_summary_line:
  count("warning[L0")). A non-L0 warning makes single-shot "clean (2 warnings)"
  and watch-mode "lints=0" disagree.
- Fix: share one counting rule between both paths.
