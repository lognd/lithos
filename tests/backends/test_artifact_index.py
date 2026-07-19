"""Tests for the WO-130 universal artifact index (D244/AD-41), the
WO-160 provenance tier (AD-45), and the WO-161 registration-derived
classification (AD-46)."""

from __future__ import annotations

from regolith._codes import ARTIFACT_INDEX_DRIFT
from regolith.backends.artifact_index import (
    ArtifactIndex,
    ArtifactRow,
    build_index,
    check_index_consistency,
    family_of,
)
from regolith.backends.framework import ArtifactProvenance, OutputFile, ToolIdentity
from regolith.backends.package import FAMILY_DIRS
from regolith.backends.registry import (
    ArtifactFamilyRegistration,
    ArtifactFamilyRegistry,
    PathPattern,
    default_artifact_family_registry,
    match_path_pattern,
)

_DETERMINISTIC = ArtifactProvenance(tier="deterministic", tool=None)


# frob:tests python/regolith/backends/registry.py::default_artifact_family_registry kind="unit"
def test_family_registry_matches_package_family_dirs():
    """The registry's family set is EXACTLY `FAMILY_DIRS` plus
    `"ledgers"` -- the two must never drift apart (WO-130)."""
    registry = default_artifact_family_registry()
    assert set(registry.families()) == set(FAMILY_DIRS) | {"ledgers"}


def test_family_of_top_level_side_file_is_ledgers():
    assert family_of("manifest.json") == "ledgers"
    assert family_of("index.md") == "ledgers"
    assert family_of("artifact_index.json") == "ledgers"


def test_family_of_directory_prefixed_file():
    assert family_of("boards/gerbers/board-F_Cu.gtl") == "boards"
    assert family_of("drawings/CarrierSi.svg") == "drawings"


# --- WO-161: classification is now registration data (path_patterns) ---


def test_classify_gerber_layer():
    registry = default_artifact_family_registry()
    registration = registry.get("boards")
    assert registration is not None
    matched = match_path_pattern("boards/gerbers/board-F_Cu.gtl", registration)
    assert matched is not None
    kind, viewer, media = matched
    assert kind == "gerber_layer.F_Cu"
    # `None` = inherit the `boards` family's own registered default,
    # which IS `gerber` -- `build_index` resolves it (asserted below).
    assert viewer is None
    assert media == "application/vnd.gerber"


def test_classify_job_file_is_json_not_gerber():
    registry = default_artifact_family_registry()
    registration = registry.get("boards")
    assert registration is not None
    matched = match_path_pattern("boards/gerbers/board-job.gbrjob", registration)
    assert matched is not None
    kind, viewer, _ = matched
    assert viewer == "json"
    assert kind == "job_file"


def test_classify_drill_layer():
    registry = default_artifact_family_registry()
    registration = registry.get("boards")
    assert registration is not None
    matched = match_path_pattern("boards/drill/board-PTH.drl", registration)
    assert matched is not None
    kind, viewer, _ = matched
    assert viewer is None  # inherits the `boards` family default (`gerber`)
    assert kind == "drill.PTH"


def test_classify_unmapped_extension_falls_back_honestly():
    registry = default_artifact_family_registry()
    registration = registry.get("firmware")
    assert registration is not None
    matched = match_path_pattern("firmware/x/image.bin", registration)
    assert matched is not None
    kind, viewer, _ = matched
    assert viewer == "binary"
    assert kind == "firmware_image"


def test_classify_deleted_no_such_function():
    """WO-161 acceptance: the hand-written dispatcher is gone."""
    import regolith.backends.artifact_index as artifact_index_module

    assert not hasattr(artifact_index_module, "classify")


def test_match_path_pattern_returns_none_when_nothing_matches():
    """A registration with no path_patterns entry (e.g. a hand-built
    test registry) refuses to classify -- the registration error
    `build_index`/`check_index_consistency` surface (WO-161)."""
    empty_registration = ArtifactFamilyRegistration("mystery", "binary")
    assert match_path_pattern("mystery/thing.bin", empty_registration) is None


def test_build_index_over_a_small_mixed_set():
    files = (
        OutputFile.of("boards/gerbers/board-F_Cu.gtl", b"gerber bytes"),
        OutputFile.of("boards/board_status.json", b'{"label": "unrouted"}'),
        OutputFile.of("harness/tap_map.json", b"{}"),
        OutputFile.of("manifest.json", b"{}"),
    )
    result = build_index("proj", files)
    assert result.is_ok
    index = result.danger_ok
    assert len(index.rows) == 4
    by_path = {r.relpath: r for r in index.rows}
    assert by_path["boards/gerbers/board-F_Cu.gtl"].viewer == "gerber"  # family default
    assert by_path["boards/gerbers/board-F_Cu.gtl"].family == "boards"
    assert by_path["boards/board_status.json"].viewer == "json"
    assert by_path["harness/tap_map.json"].family == "harness"
    assert by_path["manifest.json"].family == "ledgers"


def test_build_index_refuses_unregistered_family_loudly():
    files = (OutputFile.of("mystery/unknown.bin", b"x"),)
    result = build_index("proj", files)
    assert result.is_err
    assert result.danger_err.kind == "artifact_family_unregistered"


def test_build_index_refuses_unclassified_path_loudly():
    """WO-161: a family registered with NO matching path_patterns entry
    is the same loud refusal an unregistered family gets -- never a
    silent gap."""
    registry = ArtifactFamilyRegistry()
    registry.register(ArtifactFamilyRegistration("mystery", "binary"))
    files = (OutputFile.of("mystery/thing.bin", b"x"),)
    result = build_index("proj", files, family_registry=registry)
    assert result.is_err
    assert result.danger_err.kind == "artifact_path_unclassified"


def test_every_row_carries_source_refs_defaults():
    files = (OutputFile.of("bom/bom.csv", b"a,b\n1,2\n"),)
    result = build_index("proj", files)
    assert result.is_ok
    row = result.danger_ok.rows[0]
    assert row.source_refs == ()


# --- WO-160: the provenance tier ---


def test_artifact_row_provenance_field_is_required():
    assert ArtifactRow.model_fields["provenance"].is_required()


def test_untagged_output_file_resolves_to_deterministic_tier():
    files = (OutputFile.of("bom/bom.csv", b"a,b\n1,2\n"),)
    row = build_index("proj", files).danger_ok.rows[0]
    assert row.provenance.tier == "deterministic"
    assert row.provenance.tool is None


def test_real_tool_tagged_output_file_carries_tool_identity():
    provenance = ArtifactProvenance(
        tier="real_tool",
        tool=ToolIdentity(name="kicad-cli", version_digest="10.0.4"),
    )
    files = (
        OutputFile.of(
            "boards/gerbers/board-F_Cu.gtl", b"gerber bytes", provenance=provenance
        ),
    )
    row = build_index("proj", files).danger_ok.rows[0]
    assert row.provenance.tier == "real_tool"
    assert row.provenance.tool is not None
    assert row.provenance.tool.name == "kicad-cli"


def test_deterministic_tagged_output_file_has_no_tool():
    files = (
        OutputFile.of(
            "boards/gerbers/board-Edge_Cuts.gm1", b"fake gerber", provenance=_DETERMINISTIC
        ),
    )
    row = build_index("proj", files).danger_ok.rows[0]
    assert row.provenance.tier == "deterministic"
    assert row.provenance.tool is None


def test_check_index_consistency_catches_malformed_provenance_missing_tool():
    """A `real_tool` row with `tool=None` is drift, not a warning."""
    files: tuple[OutputFile, ...] = ()
    bad_provenance = ArtifactProvenance(tier="real_tool", tool=None)
    index = ArtifactIndex(
        project="proj",
        rows=(
            ArtifactRow(
                family="bom",
                kind="csv",
                relpath="bom/bom.csv",
                content_hash="deadbeef",
                bytes=4,
                media_type="text/csv",
                viewer="table",
                provenance=bad_provenance,
            ),
        ),
    )
    result = check_index_consistency(index, files)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT
    assert "bom/bom.csv" in result.danger_err.message


def test_check_index_consistency_ok_on_a_matched_index():
    files = (OutputFile.of("bom/bom.csv", b"a,b\n1,2\n"),)
    index = build_index("proj", files).danger_ok
    assert check_index_consistency(index, files).is_ok


def test_check_index_consistency_catches_missing_from_index():
    files = (OutputFile.of("bom/bom.csv", b"a,b\n1,2\n"),)
    index = ArtifactIndex(project="proj", rows=())
    result = check_index_consistency(index, files)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT


def test_check_index_consistency_catches_unresolved_row():
    files: tuple[OutputFile, ...] = ()
    index = ArtifactIndex(
        project="proj",
        rows=(
            ArtifactRow(
                family="bom",
                kind="csv",
                relpath="bom/bom.csv",
                content_hash="deadbeef",
                bytes=4,
                media_type="text/csv",
                viewer="table",
                provenance=_DETERMINISTIC,
            ),
        ),
    )
    result = check_index_consistency(index, files)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT


def test_check_index_consistency_catches_a_deliberately_hintless_family():
    """WO-130 acceptance: the health check fails a deliberately
    hint-less family (constructed here by bypassing `build_index`'s own
    refusal, simulating index/registry drift after the fact)."""
    files = (OutputFile.of("nofamily/thing.bin", b"x"),)
    index = ArtifactIndex(
        project="proj",
        rows=(
            ArtifactRow(
                family="nofamily",
                kind="file",
                relpath="nofamily/thing.bin",
                content_hash=OutputFile.of("nofamily/thing.bin", b"x").sha256,
                bytes=1,
                media_type="application/octet-stream",
                viewer="binary",
                provenance=_DETERMINISTIC,
            ),
        ),
    )
    result = check_index_consistency(index, files)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT
    assert "nofamily" in result.danger_err.message


def test_check_index_consistency_catches_unmatched_path_pattern():
    """WO-161: a row whose family carries NO path_patterns entry
    matching its relpath is drift, even though the family itself is
    registered (proves the gate still catches a new artifact type that
    sneaks in without registering patterns, per the WO-161 charter
    text)."""
    registry = ArtifactFamilyRegistry()
    registry.register(ArtifactFamilyRegistration("mystery", "binary"))
    files = (OutputFile.of("mystery/thing.bin", b"x"),)
    index = ArtifactIndex(
        project="proj",
        rows=(
            ArtifactRow(
                family="mystery",
                kind="file",
                relpath="mystery/thing.bin",
                content_hash=files[0].sha256,
                bytes=1,
                media_type="application/octet-stream",
                viewer="binary",
                provenance=_DETERMINISTIC,
            ),
        ),
    )
    result = check_index_consistency(index, files, family_registry=registry)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT
    assert "mystery/thing.bin" in result.danger_err.message


def test_artifact_family_registry_rejects_duplicate_registration():
    registry = ArtifactFamilyRegistry()
    first = registry.register(ArtifactFamilyRegistration("boards", "gerber"))
    second = registry.register(ArtifactFamilyRegistration("boards", "table"))
    assert first.is_ok
    assert second.is_err


def test_match_path_pattern_falls_through_to_catchall_for_unknown_extension():
    """An extension with no entry in the common baseline (e.g. `.xyz`)
    still matches the built-in registration's trailing catch-all
    pattern -- the honest `file`/`binary` fallback (WO-161), exercising
    both the ext-mismatch `continue` branches (walking past every
    specific pattern) and the final always-match branch."""
    registry = default_artifact_family_registry()
    registration = registry.get("firmware")
    assert registration is not None
    matched = match_path_pattern("firmware/x/blob.xyz", registration)
    assert matched == ("file", "binary", "application/octet-stream")


def test_match_path_pattern_contains_mismatch_skips_to_next_pattern():
    """A `boards` file OUTSIDE `/gerbers/` and `/drill/` walks past both
    boards-specific `contains`-gated patterns (the `contains truthy,
    not found` `continue` branch) before landing on the common
    baseline."""
    registry = default_artifact_family_registry()
    registration = registry.get("boards")
    assert registration is not None
    matched = match_path_pattern("boards/board_status.json", registration)
    assert matched == ("json", "json", "application/json")


def test_path_pattern_stem_substitution_strips_prefix_and_extension():
    pattern = PathPattern(
        contains="/gerbers/",
        exts=frozenset({".gtl"}),
        kind="gerber_layer.{stem}",
        viewer=None,
        media_type="application/vnd.gerber",
        strip_prefix="board-",
    )
    registration = ArtifactFamilyRegistration("boards", "gerber", path_patterns=(pattern,))
    matched = match_path_pattern("boards/gerbers/board-F_Cu.gtl", registration)
    assert matched == ("gerber_layer.F_Cu", None, "application/vnd.gerber")
