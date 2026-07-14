"""Tests for the WO-130 universal artifact index (D244/AD-41)."""

from __future__ import annotations

from regolith._codes import ARTIFACT_INDEX_DRIFT
from regolith.backends.artifact_index import (
    ArtifactIndex,
    ArtifactRow,
    build_index,
    check_index_consistency,
    classify,
    family_of,
)
from regolith.backends.framework import OutputFile
from regolith.backends.package import FAMILY_DIRS
from regolith.backends.registry import (
    ArtifactFamilyRegistration,
    ArtifactFamilyRegistry,
    default_artifact_family_registry,
)


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


def test_classify_gerber_layer():
    kind, viewer, media = classify("boards/gerbers/board-F_Cu.gtl", "boards")
    assert kind == "gerber_layer.F_Cu"
    # `None` = inherit the `boards` family's own registered default,
    # which IS `gerber` -- `build_index` resolves it (asserted below).
    assert viewer is None
    assert media == "application/vnd.gerber"


def test_classify_job_file_is_json_not_gerber():
    kind, viewer, media = classify("boards/gerbers/board-job.gbrjob", "boards")
    assert viewer == "json"
    assert kind == "job_file"


def test_classify_drill_layer():
    kind, viewer, _ = classify("boards/drill/board-PTH.drl", "boards")
    assert viewer is None  # inherits the `boards` family default (`gerber`)
    assert kind == "drill.PTH"


def test_classify_unmapped_extension_falls_back_honestly():
    kind, viewer, media = classify("firmware/x/image.bin", "firmware")
    assert viewer == "binary"
    assert kind == "firmware_image"


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


def test_every_row_carries_source_refs_defaults():
    files = (OutputFile.of("bom/bom.csv", b"a,b\n1,2\n"),)
    result = build_index("proj", files)
    assert result.is_ok
    row = result.danger_ok.rows[0]
    assert row.source_refs == ()


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
            ),
        ),
    )
    result = check_index_consistency(index, files)
    assert result.is_err
    assert result.danger_err.kind == ARTIFACT_INDEX_DRIFT
    assert "nofamily" in result.danger_err.message


def test_artifact_family_registry_rejects_duplicate_registration():
    registry = ArtifactFamilyRegistry()
    first = registry.register(ArtifactFamilyRegistration("boards", "gerber"))
    second = registry.register(ArtifactFamilyRegistration("boards", "table"))
    assert first.is_ok
    assert second.is_err
