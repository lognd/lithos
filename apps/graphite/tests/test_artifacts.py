"""`graphite.artifacts`: generic disk-scanning over sheets/payloads/traces."""

from __future__ import annotations

import json

from graphite.artifacts import (
    find_drawings_dirs,
    find_trace_files,
    list_payload_files,
    list_sheets,
    read_json,
)


def test_list_sheets_absent_dir_is_empty(tmp_path):
    assert list_sheets(tmp_path / "nope") == ()


def test_list_sheets_groups_by_subject_and_reads_track(tmp_path):
    drawings = tmp_path / "drawings"
    drawings.mkdir()
    (drawings / "board_a.drawing.json").write_text(json.dumps({"track": "elec_blocks"}))
    (drawings / "board_a.drawing.svg").write_text("<svg></svg>")
    (drawings / "board_a.explain.txt").write_text("explanation")
    (drawings / "part_b.drawing.json").write_text(json.dumps({"track": "mech"}))
    (drawings / "part_b.drawing.pdf").write_bytes(b"%PDF-1.4")

    sheets = list_sheets(drawings)
    assert [s.subject for s in sheets] == ["board_a", "part_b"]
    board = sheets[0]
    assert board.track == "elec_blocks"
    assert board.svg_path is not None
    assert board.explain_path is not None
    part = sheets[1]
    assert part.track == "mech"
    assert part.pdf_path is not None
    assert part.svg_path is None


def test_list_sheets_never_hardcodes_a_track_name(tmp_path):
    """A never-seen track name still lists generically (dispatch note:
    the GUI does not hard-code opt_trace/contract_graph)."""
    drawings = tmp_path / "drawings"
    drawings.mkdir()
    (drawings / "future.drawing.json").write_text(
        json.dumps({"track": "brand_new_track"})
    )
    sheets = list_sheets(drawings)
    assert sheets[0].track == "brand_new_track"


def test_find_drawings_dirs_recurses(tmp_path):
    (tmp_path / "a" / "drawings").mkdir(parents=True)
    (tmp_path / "b" / "c" / "drawings").mkdir(parents=True)
    found = find_drawings_dirs(tmp_path)
    assert len(found) == 2


def test_list_payload_files(tmp_path):
    store = tmp_path / "payloads"
    store.mkdir()
    (store / "blake3:abc").write_bytes(b"{}")
    assert len(list_payload_files(store)) == 1
    assert list_payload_files(tmp_path / "nope") == ()


def test_find_trace_files(tmp_path):
    regolith_dir = tmp_path / ".regolith" / "payloads"
    regolith_dir.mkdir(parents=True)
    (regolith_dir / "opt_trace_abc.json").write_text("{}")
    found = find_trace_files(tmp_path)
    assert len(found) == 1


def test_read_json_pretty_prints(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"b":1,"a":2}')
    pretty = read_json(path)
    assert pretty.index('"a"') < pretty.index('"b"')  # sort_keys


def test_read_json_falls_back_to_raw_on_bad_json(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("not json at all")
    assert read_json(path) == "not json at all"
