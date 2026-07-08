"""The ONE subprocess adapter wrapping non-Python solvers (WO-20/AD-19).

Design: `docs/implementation/design/20-solver-abstraction.md` sec. D-C. A
non-Python solver is a normal :class:`regolith.harness.model.Model`
whose physics runs out of process: the adapter serializes the
:class:`DischargeRequest` to schema-versioned JSON on the child's
stdin, reads ONE ``SolverResponse`` JSON document from its stdout, and
maps it into the shared margin rule. stderr is logs (bridged to this
module's logger); exit code 0 covers ALL computed outcomes including a
violated claim. Every infrastructure failure arm is an
:data:`regolith.harness.errors.AdapterError` VALUE the registry maps to
the explicit ``harness.adapter_error`` INDETERMINATE evidence -- never
a pass, never an exception. This wire protocol is deliberately the
Phase E harness-as-separate-process seam and the future remote
transport: one protocol, three deployments.
"""

from __future__ import annotations

import json
import math
import subprocess

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith._schema import SCHEMA_VERSION
from regolith._schema.models import SolverResponse
from regolith.harness.errors import (
    ADAPTER_ERROR_ID,
    AdapterError,
    HarnessError,
    MalformedResponse,
    NonzeroExit,
    SchemaVersionMismatch,
    SpawnFailed,
    Timeout,
)
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.quantity import bits_to_f64
from regolith.harness.signature import ModelSignature
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Re-exported beside the adapter for discoverability; defined in
# `regolith.harness.errors` beside the failure arms it marks.
__all__ = [
    "ADAPTER_ERROR_ID",
    "SolverSpec",
    "SubprocessSolverModel",
    "solve_via_subprocess",
]


class SolverSpec(BaseModel):
    """The declaration wiring one external solver executable into the registry.

    The wrapper executable named by ``argv`` owns translating the wire
    format to its solver's native input (mesh files, SPICE decks);
    regolith knows only the schema (design doc D-C). The validity
    domain rides on ``signature`` (its ``domain`` tags), like every
    in-process model.
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    signature: ModelSignature
    version: str
    cost: int = 1
    deterministic: bool = True
    timeout_s: float = 30.0


def _log_stderr(argv: tuple[str, ...], stderr: bytes) -> None:
    """Bridge the child's stderr to logging, line by line (D-C: stderr is logs)."""
    for line in stderr.decode("ascii", errors="replace").splitlines():
        if line:
            _log.info("solver %s: %s", argv[0], line)


def solve_via_subprocess(
    spec: SolverSpec, request: DischargeRequest
) -> Result[SolverResponse, AdapterError]:
    """Run one wire-protocol exchange with the solver executable.

    Request envelope ``{"schema_version": N, "request": <DischargeRequest>}``
    on stdin; ONE ``SolverResponse`` JSON document expected on stdout;
    stderr bridged to logging; wall-clock ``timeout_s`` enforced. Every
    failure arm is an explicit :data:`AdapterError` value.
    """
    envelope = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "request": request.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    _log.debug("spawning solver %s (timeout=%gs)", spec.argv, spec.timeout_s)
    try:
        completed = subprocess.run(
            list(spec.argv),
            input=envelope.encode("ascii"),
            capture_output=True,
            timeout=spec.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _log_stderr(spec.argv, exc.stderr or b"")
        _log.warning("solver %s timed out after %gs", spec.argv, spec.timeout_s)
        return Err(Timeout(argv=spec.argv, timeout_s=spec.timeout_s))
    except OSError as exc:
        _log.warning("solver %s failed to spawn: %s", spec.argv, exc)
        return Err(SpawnFailed(argv=spec.argv, message=str(exc)))

    _log_stderr(spec.argv, completed.stderr)
    if completed.returncode != 0:
        _log.warning("solver %s exited nonzero (%d)", spec.argv, completed.returncode)
        return Err(
            NonzeroExit(
                argv=spec.argv,
                returncode=completed.returncode,
                message="exit 0 covers all computed outcomes; "
                "nonzero is infrastructure",
            )
        )
    try:
        response = SolverResponse.model_validate_json(completed.stdout)
    except ValidationError as exc:
        _log.warning("solver %s stdout is not a SolverResponse: %s", spec.argv, exc)
        return Err(MalformedResponse(argv=spec.argv, message=str(exc)))
    if response.schema_version != SCHEMA_VERSION:
        _log.warning(
            "solver %s spoke schema_version %d, expected %d",
            spec.argv,
            response.schema_version,
            SCHEMA_VERSION,
        )
        return Err(
            SchemaVersionMismatch(
                argv=spec.argv,
                expected=SCHEMA_VERSION,
                got=response.schema_version,
            )
        )
    _log.debug(
        "solver %s answered (solver_version=%s domain_ok=%s)",
        spec.argv,
        response.solver_version,
        response.domain_ok,
    )
    return Ok(response)


class SubprocessSolverModel(Model):
    """A registry model whose worst-corner estimate runs out of process.

    Shares the ONE discharge path (:meth:`Model.discharge`): the wire
    response maps to a :class:`Prediction` whose ``solver_version`` /
    ``settings_digest`` reach the evidence hash (AD-19/INV-10); every
    adapter failure surfaces as an ``Err`` the registry turns into
    ``harness.adapter_error`` indeterminate evidence.
    """

    def __init__(self, spec: SolverSpec) -> None:
        """Wrap the solver executable declared by ``spec``."""
        self._spec = spec

    @property
    def spec(self) -> SolverSpec:
        """The wiring declaration this model runs."""
        return self._spec

    @property
    def signature(self) -> ModelSignature:
        """The claim kind, sense, and inputs the solver matches."""
        return self._spec.signature

    @property
    def version(self) -> str:
        """The wrapper's declared version (part of ``model_id``)."""
        return self._spec.version

    @property
    def cost(self) -> int:
        """The declared relative discharge cost (best-path search input)."""
        return self._spec.cost

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """One wire exchange, mapped into the shared prediction shape."""
        solved = solve_via_subprocess(self._spec, request)
        if solved.is_err:
            return Err(solved.danger_err)
        response = solved.danger_ok
        value = bits_to_f64(response.value_bits)
        eps = bits_to_f64(response.eps_bits)
        coverage = bits_to_f64(response.coverage.fraction_bits)
        # Non-finite bits must never reach the margin rule: NaN compares
        # false and would masquerade as `violated` (a verdict!) instead
        # of an infrastructure failure.
        if not all(math.isfinite(v) for v in (value, eps, coverage)):
            _log.warning("solver %s returned non-finite bits", self._spec.argv)
            return Err(
                MalformedResponse(
                    argv=self._spec.argv,
                    message="non-finite value/eps/coverage bits in response",
                )
            )
        # INV-10: a non-deterministic solver MUST fold its settings/seed
        # digest, or two differing runs would collide on one hash.
        if not self._spec.deterministic and response.settings_digest is None:
            _log.warning(
                "non-deterministic solver %s omitted settings_digest", self._spec.argv
            )
            return Err(
                MalformedResponse(
                    argv=self._spec.argv,
                    message="non-deterministic solver returned no "
                    "settings_digest (INV-10)",
                )
            )
        return Ok(
            Prediction(
                value=value,
                eps=eps,
                coverage=coverage,
                in_domain=response.domain_ok,
                solver_version=response.solver_version,
                settings_digest=response.settings_digest,
            )
        )
