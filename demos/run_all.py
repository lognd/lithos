"""Run every proof-pack demo (`make demos` / `make demos-strict`).

Two generations, one runner: the WO-108 optimization proofs (demos
1-6) and the WO-115/D222 feature proofs (demos 7-16, one runnable
physical proof per user-facing artifact/feature family).

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

# Ordered: the five WO-108 optimization surfaces, the fleet showcase,
# then the WO-115/D222 feature proof packs (one per user-facing
# artifact/feature family). Each names its module under `demos.`.
# frob:doc docs/modules/demos.md#run-all
DEMOS = (
    "demo1_select_ebi_decode",
    "demo2_continuous_printer",
    "demo3_removal_ribbed_panel",
    "demo4_section_search",
    "demo5_bounded_slot",
    "demo6_fleet_showcase",
    "demo7_drawings_multiview",
    "demo8_bom_cost_schedule",
    "demo9_assembly_instructions",
    "demo10_three_d_glb_viewer",
    "demo11_board_gerbers",
    "demo12_firmware_hdl",
    "demo13_test_runner_cache",
    "demo14_preview_parity",
    "demo15_calc_audit",
    "demo16_doctor_config",
    "demo17_physical_bringup_pack",
)


# frob:doc docs/modules/demos.md#run-all
# frob:waive TEST001 reason="thin CLI wrapper; see tests/test_wo108_demos.py"
def main(argv: list[str] | None = None) -> int:
    """Run all demos; return a process exit code (0 green)."""
    parser = argparse.ArgumentParser(
        description="Run the WO-108 + WO-115 proof-pack demos."
    )
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

    print("\nproof packs (WO-108 optimization + WO-115 feature):")
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
