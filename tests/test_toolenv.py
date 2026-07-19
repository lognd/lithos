"""Tests for `regolith.toolenv`, the ONE external-tool registry.

Subprocess-free: `which_fn`/`runner` are always injected, never the
real `shutil.which`/`subprocess.run` (the host may or may not have
any of these tools -- these tests must pass either way).
"""

from __future__ import annotations

import subprocess

import pytest
from regolith import toolenv


def _fake_version_runner(stdout: bytes = b"v1.2.3\n"):
    def runner(argv, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=stdout, stderr=b""
        )

    return runner


def test_catalog_covers_the_owner_directive_tool_set() -> None:
    names = {spec.name for spec in toolenv.catalog()}
    # WO-126 (charter 40 sec. 3): sigrok-cli joins the catalog for the
    # bring-up harness pack's capture configs.
    assert names == {
        "kicad-cli",
        "verilator",
        "ghdl",
        "ngspice",
        "ccx",
        "gmsh",
        "sigrok-cli",
    }


def test_spec_for_unknown_tool_is_none() -> None:
    assert toolenv.spec_for("not-a-real-tool") is None


def test_resolve_missing_tool_has_no_path_or_version() -> None:
    status = toolenv.resolve("verilator", which_fn=lambda name: None, use_cache=False)
    assert not status.available
    assert status.path is None
    assert status.version is None


def test_resolve_present_tool_reports_path_and_version() -> None:
    status = toolenv.resolve(
        "ngspice",
        which_fn=lambda name: f"/usr/bin/{name}",
        runner=_fake_version_runner(b"ngspice-42\n"),
        use_cache=False,
    )
    assert status.available
    assert status.path == "/usr/bin/ngspice"
    assert status.version == "ngspice-42"


def test_resolve_unknown_tool_raises_key_error() -> None:
    with pytest.raises(KeyError):
        toolenv.resolve("not-a-real-tool", which_fn=lambda name: None)


# frob:tests python/regolith/toolenv.py::clear_cache
def test_resolve_caches_by_default() -> None:
    toolenv.clear_cache()
    calls: list[str] = []

    def counting_which(name: str) -> str | None:
        calls.append(name)
        return None

    toolenv.resolve("gmsh", which_fn=counting_which, probe_version=False)
    toolenv.resolve("gmsh", which_fn=counting_which, probe_version=False)
    assert len(calls) == 1
    toolenv.clear_cache()


def test_resolve_use_cache_false_always_reprobes() -> None:
    toolenv.clear_cache()
    calls: list[str] = []

    def counting_which(name: str) -> str | None:
        calls.append(name)
        return None

    toolenv.resolve(
        "ccx", which_fn=counting_which, probe_version=False, use_cache=False
    )
    toolenv.resolve(
        "ccx", which_fn=counting_which, probe_version=False, use_cache=False
    )
    assert len(calls) == 2


def test_resolve_all_returns_every_catalog_entry_in_order() -> None:
    statuses = toolenv.resolve_all(
        which_fn=lambda name: None, probe_version=False, use_cache=False
    )
    assert [s.spec.name for s in statuses] == [s.name for s in toolenv.catalog()]
    assert all(not s.available for s in statuses)


def test_version_probe_spawn_failure_is_none_not_raised() -> None:
    def raising_runner(argv, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    status = toolenv.resolve(
        "kicad-cli",
        which_fn=lambda name: "/usr/bin/kicad-cli",
        runner=raising_runner,
        use_cache=False,
    )
    assert status.available
    assert status.version is None


def test_teaching_message_names_tool_reason_and_install_hint() -> None:
    status = toolenv.resolve("gmsh", which_fn=lambda name: None, use_cache=False)
    message = status.teaching_message(needed_for="the FEA mesh tier")
    assert "gmsh" in message
    assert "the FEA mesh tier" in message
    assert "conda-forge" in message or "apt" in message


def test_install_hint_render_includes_arm64_note_for_gmsh() -> None:
    spec = toolenv.spec_for("gmsh")
    assert spec is not None
    rendered = spec.install.render()
    assert "conda-forge" in rendered
    assert "arm64" in rendered


def test_install_hint_render_includes_kicad_ppa_caveat_for_ngspice() -> None:
    spec = toolenv.spec_for("ngspice")
    assert spec is not None
    rendered = spec.install.render()
    assert "force-overwrite" in rendered


def test_guide_quotes_registry_capabilities() -> None:
    """docs/guide/18-external-tools.md must quote every registered
    tool's name and capability string VERBATIM (whitespace-normalized)
    -- the registry is authoritative, the guide may not drift."""
    from pathlib import Path

    guide_path = (
        Path(__file__).resolve().parents[1] / "docs" / "guide" / "18-external-tools.md"
    )
    guide = " ".join(guide_path.read_text().split())
    for spec in toolenv.catalog():
        assert spec.name in guide, f"guide is missing tool {spec.name}"
        capability = " ".join(spec.capability.split())
        assert capability in guide, (
            f"guide is missing {spec.name}'s registry capability wording: "
            f"{capability!r}"
        )
    assert "feldspar" in guide
    assert "regolith doctor" in guide
