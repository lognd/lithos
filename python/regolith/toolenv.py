"""The ONE external-tool registry (owner directive, optional-tool posture).

Every optional external binary the toolchain may shell out to (KiCad,
HDL simulators, SPICE, FEA meshers/solvers) is described exactly ONCE
here: its canonical name, how to locate it (`shutil.which`, cached),
how to probe its version, what capability tier it unlocks (human
phrasing, for diagnostics and `regolith doctor`), and per-platform
install guidance. Install-hint strings live ONLY in this module --
no call site may hard-code an apt/conda incantation.

Posture (owner directive): a design that does NOT need a tool must
never see its absence (honest skip/indeterminate, the existing WO-24/
35 `ToolUnavailable` discipline); a design that DOES need a tool gets
a loud, teaching diagnostic -- tool name, why this design needs it,
and exact install guidance -- never a bare traceback and never a
silent pass. Call sites ask this module WHAT to say; they never
compose the message themselves (no duplication of hint text).
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

WhichFn = Callable[[str], str | None]


class InstallHint(BaseModel):
    """Per-platform install guidance for one tool (teaching text)."""

    model_config = ConfigDict(frozen=True)

    apt: str | None = None
    conda: str | None = None
    note: str | None = None

    def render(self) -> str:
        """One human-readable install block, apt then conda then a caveat note."""
        lines: list[str] = []
        if self.apt is not None:
            lines.append(f"apt: {self.apt}")
        if self.conda is not None:
            lines.append(f"conda-forge: {self.conda}")
        if self.note is not None:
            lines.append(f"note: {self.note}")
        return "; ".join(lines) if lines else "no install guidance recorded"


class ToolSpec(BaseModel):
    """One registered external tool: identity, capability, install text."""

    model_config = ConfigDict(frozen=True)

    name: str
    binary: str
    capability: str
    version_argv: tuple[str, ...] = ()
    install: InstallHint = InstallHint()


class ToolStatus(BaseModel):
    """The resolved state of one tool at doctor/resolve time."""

    model_config = ConfigDict(frozen=True)

    spec: ToolSpec
    path: str | None
    version: str | None

    @property
    def available(self) -> bool:
        """Whether the binary was located on PATH."""
        return self.path is not None

    def teaching_message(self, *, needed_for: str) -> str:
        """A loud, constructive diagnostic for a design that NEEDS this tool.

        Names the tool, why THIS design needs it, and exact install
        guidance -- the one format every required-tool error uses
        (never a bare traceback, never a silent pass).
        """
        return (
            f"{self.spec.name} is required for {needed_for} "
            f"({self.spec.capability}) but is not installed/reachable. "
            f"Install it: {self.spec.install.render()}"
        )


# The full catalog (owner directive: verilator, ghdl, ngspice, kicad-cli,
# ccx, gmsh, plus the pack solvers a design may declare). Registered here
# even where lithos has no call site yet (e.g. no HDL/SPICE/FEA realizer
# lands in THIS repo as of this change) so `regolith doctor` reports the
# whole optional-tool surface up front and a future call site never
# re-derives install text.
_CATALOG: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="kicad-cli",
        binary="kicad-cli",
        capability="elec layout tier for cuprite designs "
        "(placement/routing/DRC/export)",
        version_argv=("kicad-cli", "version"),
        install=InstallHint(
            apt="sudo apt install kicad",
            conda="conda install -c conda-forge kicad",
            note="pcbnew (the python API) additionally needs "
            "`make kicad-link` to link the system KiCad install into "
            "the venv -- kicad-cli alone is not enough for the real-tool "
            "gate in regolith.realizer.elec.kicad.real_kicad_available().",
        ),
    ),
    ToolSpec(
        name="verilator",
        binary="verilator",
        capability="HDL sim-tier evidence for cuprite digital designs",
        version_argv=("verilator", "--version"),
        install=InstallHint(
            apt="sudo apt install verilator",
            conda="conda install -c conda-forge verilator",
        ),
    ),
    ToolSpec(
        name="ghdl",
        binary="ghdl",
        capability="VHDL sim-tier evidence for cuprite digital designs",
        version_argv=("ghdl", "--version"),
        install=InstallHint(
            apt="sudo apt install ghdl",
            conda="conda install -c conda-forge ghdl",
        ),
    ),
    ToolSpec(
        name="ngspice",
        binary="ngspice",
        capability="SPICE simulation tier for cuprite analog/power designs",
        version_argv=("ngspice", "-v"),
        install=InstallHint(
            apt="sudo apt install ngspice",
            conda="conda install -c conda-forge ngspice",
            note="on KiCad-PPA hosts dpkg may report 'trying to "
            "overwrite .../ngspice/analog.cm' (libngspice-kicad ships "
            "the same XSPICE code models); fix: sudo apt install "
            'ngspice -o Dpkg::Options::="--force-overwrite"; the CLI '
            "v36 code models then shadow the lib's v43 copies -- undo "
            "with sudo apt install --reinstall libngspice-kicad.",
        ),
    ),
    ToolSpec(
        name="ccx",
        binary="ccx",
        capability="FEA solve tier (CalculiX) for hematite/feldspar stress claims",
        version_argv=("ccx", "-v"),
        install=InstallHint(
            apt="sudo apt install calculix-ccx",
            conda="conda install -c conda-forge calculix",
            note="calculix-ccx has NO OCCT dependency; if apt refuses "
            "it, it was almost certainly batched in one transaction "
            "with gmsh -- install it alone.",
        ),
    ),
    ToolSpec(
        name="gmsh",
        binary="gmsh",
        capability="FEA meshing tier for hematite/feldspar geometry-to-mesh",
        version_argv=("gmsh", "--version"),
        install=InstallHint(
            apt="sudo apt install gmsh",
            conda="micromamba create -n gmsh -c conda-forge gmsh",
            note="on a KiCad-10-PPA host apt gmsh is unwinnable (jammy "
            "gmsh needs OCCT 7.5; the PPA pins libocct-*-7.6, which "
            "Breaks 7.5); on arm64 there is also NO pip wheel and NO "
            "upstream binary -- use conda-forge (micromamba) and "
            "symlink the gmsh binary into /usr/local/bin or "
            "~/.local/bin for global visibility; on x86_64 the "
            "upstream Linux64 tarball is an alternative.",
        ),
    ),
)

_TOOLS_BY_NAME: dict[str, ToolSpec] = {t.name: t for t in _CATALOG}

# Cache: resolved path per tool name, populated by `resolve()`. Cleared by
# `clear_cache()` for tests that inject a different `which_fn` mid-run.
_PATH_CACHE: dict[str, str | None] = {}


def catalog() -> tuple[ToolSpec, ...]:
    """Every registered tool spec, in declaration order."""
    return _CATALOG


def spec_for(name: str) -> ToolSpec | None:
    """The registered spec for ``name``, or ``None`` if not catalogued."""
    return _TOOLS_BY_NAME.get(name)


def clear_cache() -> None:
    """Drop the cached `which()` resolutions (test isolation)."""
    _PATH_CACHE.clear()


def _probe_version(
    argv: tuple[str, ...],
    runner: Callable[..., subprocess.CompletedProcess[bytes]],
) -> str | None:
    """Run a tool's version probe; ``None`` on any spawn/parse failure."""
    if not argv:
        return None
    try:
        completed = runner(list(argv), capture_output=True, timeout=5.0, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log.debug("toolenv: version probe %s failed: %s", argv, exc)
        return None
    text = (completed.stdout or b"").decode("ascii", errors="replace").strip()
    if not text:
        text = (completed.stderr or b"").decode("ascii", errors="replace").strip()
    first_line = text.splitlines()[0] if text else ""
    return first_line or None


def resolve(
    name: str,
    *,
    which_fn: WhichFn = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    probe_version: bool = True,
    use_cache: bool = True,
) -> ToolStatus:
    """Resolve one catalogued tool's live status (path + version, cached).

    Cached on ``name`` across calls within a process (per owner
    directive: "which() resolution (cached)"); pass ``use_cache=False``
    to force a fresh probe (doctor's default, so the report reflects
    the CURRENT host rather than a stale first-call result).
    """
    spec = spec_for(name)
    if spec is None:
        raise KeyError(f"toolenv: {name!r} is not a registered tool")

    if use_cache and name in _PATH_CACHE:
        path = _PATH_CACHE[name]
    else:
        path = which_fn(spec.binary)
        if use_cache:
            _PATH_CACHE[name] = path
        _log.debug(
            "toolenv: resolved %s -> %s", spec.binary, path if path else "MISSING"
        )

    version = None
    if path is not None and probe_version:
        version = _probe_version(spec.version_argv, runner)
        _log.debug("toolenv: %s version=%s", spec.binary, version)

    return ToolStatus(spec=spec, path=path, version=version)


def resolve_all(
    *,
    which_fn: WhichFn = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    probe_version: bool = True,
    use_cache: bool = True,
) -> tuple[ToolStatus, ...]:
    """`resolve()` every catalogued tool, in catalog order (doctor's feed)."""
    return tuple(
        resolve(
            t.name,
            which_fn=which_fn,
            runner=runner,
            probe_version=probe_version,
            use_cache=use_cache,
        )
        for t in _CATALOG
    )
