"""WO-55 `regolith optimize` CLI: budget refusal, JSON round-trip, and
the lockfile `cause: optimize(...)` row (charter sec. 1.5/1.8)."""

from __future__ import annotations

import json
from pathlib import Path

from regolith._schema.models import OptimizationTrace
from regolith.cli.app import EXIT_CLEAN, EXIT_DIAGNOSTICS, EXIT_INTERNAL_ERROR, app
from typer.testing import CliRunner

runner = CliRunner()

_SPEC = {
    "domains": [
        {"subject": "vendor", "candidates": ["ti", "onsemi"]},
        {"subject": "package", "candidates": ["sot23", "bga"]},
    ],
    "costs": {
        "vendor": {"ti": 1.0, "onsemi": 0.5},
        "package": {"sot23": 0.2, "bga": 0.1},
    },
    "infeasible_prefixes": [{"vendor": "onsemi", "package": "bga"}],
    "objective": ["minimize"],
}


def _write_spec(tmp_path: Path) -> Path:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_SPEC))
    return spec_path


def test_optimize_refuses_without_a_budget(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    result = runner.invoke(app, ["optimize", str(tmp_path), "--spec", str(spec_path)])
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_optimize_json_round_trips_through_generated_schema(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    result = runner.invoke(
        app,
        [
            "optimize",
            str(tmp_path),
            "--spec",
            str(spec_path),
            "--budget-evals",
            "10",
            "--seed",
            "1",
            "--json",
        ],
    )
    assert result.exit_code == EXIT_CLEAN
    trace = OptimizationTrace.model_validate_json(
        result.stdout.strip().splitlines()[-1]
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None


def test_optimize_writes_lockfile_with_optimize_cause(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    result = runner.invoke(
        app,
        ["optimize", str(tmp_path), "--spec", str(spec_path), "--budget-evals", "10"],
    )
    assert result.exit_code == EXIT_CLEAN
    lockfile_text = (tmp_path / "regolith.lock").read_text()
    assert "cause: optimize(declared_objective, trace=" in lockfile_text


def test_optimize_infeasible_domain_is_a_diagnostic_not_a_crash(tmp_path: Path) -> None:
    spec = {
        "domains": [{"subject": "vendor", "candidates": ["onsemi"]}],
        "costs": {},
        "infeasible_prefixes": [{"vendor": "onsemi"}],
        "objective": ["minimize"],
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    result = runner.invoke(
        app,
        ["optimize", str(tmp_path), "--spec", str(spec_path), "--budget-evals", "10"],
    )
    assert result.exit_code == EXIT_DIAGNOSTICS


def test_optimize_resume_reuses_a_prior_trace_digest(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    first = runner.invoke(
        app,
        [
            "optimize",
            str(tmp_path),
            "--spec",
            str(spec_path),
            "--budget-evals",
            "10",
            "--json",
        ],
    )
    assert first.exit_code == EXIT_CLEAN
    trace = OptimizationTrace.model_validate_json(first.stdout.strip().splitlines()[-1])
    digests = list((tmp_path / ".regolith" / "payloads").glob("*"))
    assert digests, "the trace must have been persisted to the payload store"

    resumed = runner.invoke(
        app,
        [
            "optimize",
            str(tmp_path),
            "--spec",
            str(spec_path),
            "--budget-evals",
            "10",
            "--resume",
            f"blake3:{digests[0].name}",
            "--json",
        ],
    )
    assert resumed.exit_code == EXIT_CLEAN
    resumed_trace = OptimizationTrace.model_validate_json(
        resumed.stdout.strip().splitlines()[-1]
    )
    assert resumed_trace.model_dump_json() == trace.model_dump_json()
