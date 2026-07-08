"""The fixture wire-protocol solver executable (WO-20 conformance).

A stand-in for a non-Python solver binary: reads the schema-versioned
request envelope from stdin, writes ONE canned ``SolverResponse`` JSON
document to stdout, and logs to stderr (the adapter bridges it). The
first argv argument selects a misbehavior mode so the adapter's failure
arms are each testable:

    ok         well-formed response (the default)
    garbage    unparseable stdout
    hang       never answers (exercises the timeout arm)
    exit2      exits nonzero after reading the request (the kill arm)
    bad-schema well-formed JSON with a wrong schema_version

Run only as a subprocess by the test suite; deliberately dependency-free
(stdlib only) like a real out-of-tree solver wrapper would be.
"""

from __future__ import annotations

import json
import struct
import sys
import time

SOLVER_VERSION = "fixture-solver@1.0.0"


def _f64_to_bits(value: float) -> int:
    """Pack an f64 into its u64 bit pattern (the wire's exact-float form)."""
    return int(struct.unpack("<Q", struct.pack("<d", value))[0])


def main() -> int:
    """One request/response exchange, per the argv-selected mode."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
    print(f"fixture solver starting (mode={mode})", file=sys.stderr)

    if mode == "hang":
        time.sleep(600.0)
        return 0
    if mode == "garbage":
        sys.stdout.write("this is not a SolverResponse {")
        return 0

    envelope = json.load(sys.stdin)
    request = envelope["request"]
    print(f"claim_kind={request['claim_kind']}", file=sys.stderr)

    if mode == "exit2":
        print("fixture solver exploding on purpose", file=sys.stderr)
        return 2

    schema_version = 999999 if mode == "bad-schema" else int(envelope["schema_version"])
    # Canned physics: predict half the demanded limit with zero error --
    # always inside an upper-bound claim's margin, so the shared rule
    # discharges it.
    response = {
        "schema_version": schema_version,
        "value_bits": _f64_to_bits(float(request["limit"]) / 2.0),
        "eps_bits": _f64_to_bits(0.0),
        "coverage": {"axes": [], "fraction_bits": _f64_to_bits(1.0)},
        "solver_version": SOLVER_VERSION,
        "settings_digest": None,
        "domain_ok": True,
        "note": "canned fixture response",
    }
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
