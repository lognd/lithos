"""Run every WO-108 proof-pack demo (`make demos` / `make demos-strict`).

Each demo's `run()` drives the real pipeline, emits its artifacts +
manifest + PROOF.md, and returns True iff its surface is LIVE (its
machinery is merged). The runner:

* `make demos`         -- runs every demo; fails only if a LIVE demo
  errors. Not-live (probe-gated) demos print their honest gap and do
  NOT fail the run (the standing "run what is proven" bar).
* `make demos-strict`  -- additionally fails if ANY demo is not live
  (the release-completeness bar: every surface must be proven).

A demo that raises is always a failure in both modes (a live surface
that broke). The runner prints one status row per demo.
"""

from __future__ import annotations

import argparse
import importlib
import sys

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Ordered: the five surfaces (WO-108 sec. "The surfaces") then the
# fleet showcase. Each names its module under `demos.`.
DEMOS = (
    "demo1_select_ebi_decode",
    "demo2_continuous_printer",
    "demo3_removal_ribbed_panel",
    "demo4_section_search",
    "demo5_bounded_slot",
    "demo6_fleet_showcase",
)


def main(argv: list[str] | None = None) -> int:
    """Run all demos; return a process exit code (0 green)."""
    parser = argparse.ArgumentParser(description="Run the WO-108 proof-pack demos.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any demo's surface is not live (release-completeness bar).",
    )
    args = parser.parse_args(argv)

    results: list[tuple[str, str]] = []
    errored = False
    not_live = False
    for name in DEMOS:
        module = importlib.import_module(f"demos.{name}")
        try:
            live = module.run()
        except Exception as exc:  # a live surface that broke: always a failure
            _log.exception("demo %s raised", name)
            results.append((name, f"ERROR: {exc}"))
            errored = True
            continue
        if live:
            results.append((name, "live"))
        else:
            results.append((name, "not-live (honest gap)"))
            not_live = True

    print("\nWO-108 proof packs:")
    for name, status in results:
        print(f"  {name:32} {status}")

    if errored:
        print("\ndemos: FAILED (a live demo raised)")
        return 1
    if args.strict and not_live:
        print("\ndemos-strict: FAILED (a surface is not yet live)")
        return 1
    live_count = sum(1 for _, s in results if s == "live")
    print(f"\ndemos: OK ({live_count}/{len(DEMOS)} live)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
