"""Process population wave 2 (WO-170, D269 item 4): PCB fab/assembly +
perf-board hand assembly + elec-install practice families.

Six named process families, each a `ProcessRecord` + `DfmCheckSet` pair,
transcribed from `procres/pcb.md` (#93-97) and `procres/elec_install.md`
(#98-100) with provenance classes PRESERVED verbatim (no invented
citations). No `std.materials` catalog entry exists yet for FR-4/copper
conductor materials (T-0038 scope, not this WO's) -- every PCB-family
record's `materials` tuple is therefore left empty, named honestly in
its own provenance note rather than inventing a placeholder key.

`elec_install`'s three entries (#98-100) are the WO-170 body's named
special case: NOT re-researched this pass, but RESHAPED from std.power's
already-landed, already-cited WO-134/134B records (`harness/models/
power.py`) into this schema's contract -- every citation below is the
SAME NEC article/edition or IEEE standard std.power already carries,
reused verbatim, never re-derived. Per the WO-170 body, this family is
also a categorically different cost-model shape (design PRACTICE, not
fabrication): `cost_drivers`/`lead_class` say so explicitly rather than
forcing a fabrication-cost-driver shape onto it.

PCB fab/assembly's DFM checks are WRAPPED, not duplicated (WO-170
deliverable 3, NO DUPLICATION): `harness/models/dfm/checks.py` did not
previously source any PCB-specific constant, so the wave-2 checks below
are the first real callables for this family (no pre-existing hard-coded
constant to deduplicate against).
"""

from __future__ import annotations

from regolith.backends.quantity import DimensionedValue
from regolith.harness.models.dfm.process_records import (
    CostDriver,
    DfmCheckEntry,
    DfmCheckSet,
    MinFeature,
    ProcessRecord,
    ProvenanceNote,
    SizeLimit,
    SurfaceFinishEntry,
    ToleranceGrade,
)

_CHECKS = "regolith.harness.models.dfm.checks"

# --- 93. PCB fabrication ----------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PCB_FAB_RECORD = ProcessRecord(
    key="std.process/pcb_fab",
    name="PCB fabrication (etch/drill/plate, multilayer)",
    din_8580_class="ext.pcb",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="trace_width",
            min=DimensionedValue.of("0.05", "mm"),
            max=DimensionedValue.of("0.2", "mm"),
        ),
        SizeLimit(
            dimension="via_diameter",
            min=DimensionedValue.of("0.05", "mm"),
            max=DimensionedValue.of("0.3", "mm"),
        ),
        SizeLimit(
            dimension="board_thickness",
            min=DimensionedValue.of("0.4", "mm"),
            max=DimensionedValue.of("3.2", "mm"),
        ),
        SizeLimit(
            dimension="copper_weight",
            min=DimensionedValue.of("0.5", "oz"),
            max=DimensionedValue.of("3", "oz"),
        ),
    ),
    tolerance_grades=(
        ToleranceGrade(
            condition="standard (non-HDI) fab",
            achievable=DimensionedValue.of("0.1-0.2", "mm"),
        ),
        ToleranceGrade(
            condition="HDI fab",
            achievable=DimensionedValue.of("0.05-0.075", "mm"),
        ),
    ),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="annular ring (drill-registration tolerance)",
            value=DimensionedValue.of("declared per fab-house capability", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="NRE (photo-tooling/stencil), amortized fast",
            note="unit economics scale with layer count and panel "
            "utilization, not a per-part die (procres/pcb.md #93)",
        ),
        CostDriver(
            driver="setup",
            driver_class="lead-time days (standard) to hours (expedited)",
            note="cost per board drops sharply with panelization at "
            "production volume",
        ),
    ),
    lead_class="days (standard) to hours (expedited)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="trace width/spacing, via diameter, board thickness, "
            "and copper weight envelopes are uncited engineering-"
            "consensus ranges (procres/pcb.md #93); no std.materials "
            "catalog entry exists yet for FR-4/copper (T-0038 scope), "
            "so materials is left empty rather than an invented key",
        ),
        ProvenanceNote(
            posture="pd_gov",
            scope="tolerance_grades",
            detail="impedance-controlled trace geometry is modeled via "
            "cited closed-form models over (stackup, trace geometry) "
            "per charter 35/WO-78, confirmed landed (procres/pcb.md #93)",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_min_trace_space",
        f"{_CHECKS}:check_annular_ring",
        f"{_CHECKS}:check_via_drill_range",
        f"{_CHECKS}:check_copper_edge_clearance",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PCB_FAB_CHECKS = DfmCheckSet(
    family="pcb_fab",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_min_trace_space",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="trace width/spacing >= declared fab-house minimum "
                "is a fab-capability containment predicate (procres/"
                "pcb.md #93 DFM rule 1)",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_annular_ring",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="annular ring >= declared minimum is a drill-"
                "registration-tolerance containment predicate (procres/"
                "pcb.md #93 DFM rule 3)",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_via_drill_range",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="via diameter within declared mechanical-vs-laser "
                "drill-capability range (procres/pcb.md #93 DFM rule 2)",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_copper_edge_clearance",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="copper-to-edge clearance >= declared minimum "
                "(procres/pcb.md #93 DFM rule 6)",
            ),
        ),
    ),
)

# --- 94. SMT assembly (reflow) ------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
SMT_ASSEMBLY_RECORD = ProcessRecord(
    key="std.process/smt_assembly",
    name="SMT assembly (reflow)",
    din_8580_class="ext.pcb",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="placement_accuracy",
            min=DimensionedValue.of("0.05", "mm"),
            max=DimensionedValue.of("0.1", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="component package",
            value=DimensionedValue.of("01005/0201 (smallest passive)", "mm"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="NRE = stencil + programming",
            note="pick-and-place + reflow-oven cycle time dominated, low "
            "marginal cost at volume, strongly favors panelized "
            "production (procres/pcb.md #94)",
        ),
    ),
    lead_class="any volume, strongly favors panelized production",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="placement accuracy and reflow-profile figures (lead-"
            "free SAC305 peak ~245-250C typical) are uncited "
            "engineering-consensus values (procres/pcb.md #94)",
        ),
        ProvenanceNote(
            posture="gek",
            scope="dfm_check_ids",
            detail="this recon's earlier finding that the real-tier "
            "KiCad backend's DRC coverage is UNCONFIRMED means any "
            "assembly-stage DFM check here is gated on an upstream "
            "fab/route claim only partially verified -- named as a "
            "sequencing dependency, not resolved (procres/pcb.md #94 "
            "DFM rule 5)",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_reflow_thermal_compat",
        f"{_CHECKS}:check_placement_pad_spacing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
SMT_ASSEMBLY_CHECKS = DfmCheckSet(
    family="smt_assembly",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_reflow_thermal_compat",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="the lowest-tolerance component on the board gates "
                "the max reflow peak temperature, a board-level "
                "composition predicate (procres/pcb.md #94 DFM rule 3)",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_placement_pad_spacing",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="minimum pad-to-pad spacing for fine-pitch parts "
                ">= declared placement-accuracy + solder-bridge margin "
                "(procres/pcb.md #94 DFM rule 2)",
            ),
        ),
    ),
)

# --- 95. Through-hole assembly (wave solder) ----------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
THROUGH_HOLE_WAVE_SOLDER_RECORD = ProcessRecord(
    key="std.process/through_hole_wave_solder",
    name="Through-hole assembly (wave solder)",
    din_8580_class="ext.pcb",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="wave contact temperature",
            value=DimensionedValue.of("250-260", "C"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="fast per-board cycle, continuous wave process",
            note="lower per-joint cost than hand soldering at volume, "
            "higher tooling/line cost than reflow-only for pure-SMT "
            "boards (procres/pcb.md #95)",
        ),
    ),
    lead_class="mixed-technology or connector-heavy boards, mid-to-high "
    "volume",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="through-hole clearance, wave contact time/temperature, "
            "and mixed-technology sequencing figures are uncited "
            "engineering-consensus values (procres/pcb.md #95)",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_hole_lead_clearance",
        f"{_CHECKS}:check_process_sequencing",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
THROUGH_HOLE_WAVE_SOLDER_CHECKS = DfmCheckSet(
    family="through_hole_wave_solder",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_hole_lead_clearance",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="hole/lead-diameter clearance within a declared "
                "solderability window (procres/pcb.md #95 DFM rule 1)",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_process_sequencing",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="mixed-technology sequencing (reflow SMT first, "
                "then glue+wave through-hole) is a required process-chain "
                "order, reusing the wave-1 generic sequencing predicate "
                "(procres/pcb.md #95 DFM rule 3)",
            ),
        ),
    ),
)

# --- 96. Conformal coating ----------------------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONFORMAL_COATING_RECORD = ProcessRecord(
    key="std.process/conformal_coating",
    name="Conformal coating",
    din_8580_class="ext.pcb",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="coating_thickness",
            min=DimensionedValue.of("25", "um"),
            max=DimensionedValue.of("75", "um"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="low per-board cost (spray/dip); parylene batch "
            "process is slower/costlier but highest quality",
            note="required for harsh-environment (automotive, marine, "
            "industrial) electronics (procres/pcb.md #96)",
        ),
    ),
    lead_class="any volume",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="coating thickness ranges and method tradeoffs (spray/"
            "dip/brush/parylene vapor deposition) are uncited "
            "engineering-consensus values (procres/pcb.md #96)",
        ),
    ),
    dfm_check_ids=(f"{_CHECKS}:check_masked_area_declared",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONFORMAL_COATING_CHECKS = DfmCheckSet(
    family="conformal_coating",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_masked_area_declared",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="a masked-area list (connectors, test points, "
                "board edges, thermal-interface surfaces) is a required "
                "exclusion-zone predicate (procres/pcb.md #96 DFM rule 1)",
            ),
        ),
    ),
)

# --- 97. Perf-board / stripboard hand assembly --------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PERFBOARD_ASSEMBLY_RECORD = ProcessRecord(
    key="std.process/perfboard_assembly",
    name="Perf-board / stripboard hand assembly",
    din_8580_class="ext.pcb",
    materials=(),
    size_limits=(
        SizeLimit(
            dimension="hole_pitch",
            min=DimensionedValue.of("2.54", "mm"),
            max=DimensionedValue.of("2.54", "mm"),
        ),
    ),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(
        MinFeature(
            feature="jumper wire gauge",
            value=DimensionedValue.of("22-30", "AWG"),
        ),
    ),
    cost_drivers=(
        CostDriver(
            driver="tooling_amortization",
            driver_class="near-zero fixed tooling/NRE",
            note="off-the-shelf perf-board sheet, hand tools; HIGH "
            "per-board labor cost that does NOT amortize with volume -- "
            "the opposite economics of PCB fab (procres/pcb.md #97)",
        ),
    ),
    lead_class="one-off/prototype/hobbyist-scale builds ONLY, never a "
    "production process",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="0.1in hole pitch, catalog board sizes, and jumper "
            "wire gauge are uncited engineering-consensus/practical-"
            "fact values; no PD-GOV or REFUSE-class source applies -- "
            "this is a pure practical/mechanical-fact process with no "
            "regulated-standard content (procres/pcb.md #97). This "
            "recon's earlier gap survey confirmed ZERO prior "
            "representation of this process anywhere in lithos "
            "(D268 TARGET 3).",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_perfboard_grid_pitch",
        "regolith.realizer.elec.perfboard:check_no_shared_holes",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PERFBOARD_ASSEMBLY_CHECKS = DfmCheckSet(
    family="perfboard_assembly",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_perfboard_grid_pitch",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="every component's lead pitch must be an integer "
                "multiple of the 0.1in grid, or a declared breakout "
                "adapter is required -- the signature new DFM predicate "
                "this process needs (procres/pcb.md #97 DFM rule 1)",
            ),
        ),
        DfmCheckEntry(
            check_id="regolith.realizer.elec.perfboard:check_no_shared_holes",
            provenance=ProvenanceNote(
                posture="gek",
                scope="record",
                detail="no two components claim the same anchor hole, and "
                "no two different nets' bare jumper ends share a hole -- "
                "the real check WO-165 deliverable 5 landed "
                "(harness/realizer/elec/perfboard.py); this family's "
                "check-set composes with it directly rather than "
                "duplicating the duplicate-hole arithmetic",
            ),
        ),
    ),
)

# --- 98. Branch-circuit wiring practice ---------------------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
BRANCH_CIRCUIT_RECORD = ProcessRecord(
    key="std.process/branch_circuit_wiring",
    name="Branch-circuit wiring practice (NEC Ch.2/3-class)",
    din_8580_class="ext.elec_install",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="design-tool cost (software), NOT a fabrication "
            "cost",
            note="tooling amortization = the toolchain itself; lead-time "
            "class = as fast as the design tool computes; no batch-size "
            "sweet spot applies in the manufacturing sense -- a "
            "categorically different cost-model shape from every "
            "fabrication process in this dossier (procres/"
            "elec_install.md #98)",
        ),
    ),
    lead_class="as fast as the design tool computes (design practice, "
    "not a manufacturing lead time)",
    provenance=(
        ProvenanceNote(
            posture="pd_gov",
            scope="record",
            detail="conductor ampacity (NEC 310.16/310.15), demand-load "
            "(NEC Art. 220), voltage drop (IEEE Std 141-1993), grounding/"
            "bonding, and motor code-letter/locked-rotor (NEC 430.7(B)) "
            "are ALL already-landed, already-cited WO-134 std.power "
            "records -- reused here verbatim, not re-derived (procres/"
            "elec_install.md #98)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="dfm_check_ids",
            detail="any check requiring a specific breaker/fuse trip-"
            "curve value is a named refusal (D250 sec.3); breakers/"
            "fuses remain explicitly out of stdlib scope, confirmed "
            "still-refused as of WO-134's close-out",
            refused_source="manufacturer breaker/fuse trip-curve data "
            "(catalog content)",
            lift_condition="a licensed vendor breaker/fuse curve dataset "
            "is obtained and transcribed with in-row citation, or the "
            "D250 sec.3 gate is lifted by owner decision",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_ampacity_containment",
        f"{_CHECKS}:check_voltage_drop_limit",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
BRANCH_CIRCUIT_CHECKS = DfmCheckSet(
    family="branch_circuit_wiring",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_ampacity_containment",
            provenance=ProvenanceNote(
                posture="pd_gov",
                scope="record",
                detail="conductor ampacity (with 310.15 derating) >= "
                "declared branch-circuit load; NFPA 70 (NEC), 2023 ed., "
                "sec. 310.15(B)/(C), the same citation AmpacityModel "
                "carries in harness/models/power.py",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_voltage_drop_limit",
            provenance=ProvenanceNote(
                posture="pd_gov",
                scope="record",
                detail="voltage drop over the declared conductor run <= "
                "a declared percent-of-nominal threshold; IEEE Std "
                "141-1993 (IEEE Red Book), ch. 3, the same citation "
                "VoltageDropModel carries in harness/models/power.py",
            ),
        ),
    ),
)

# --- 99. Panel/service-equipment installation practice ------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
PANEL_SERVICE_RECORD = ProcessRecord(
    key="std.process/panel_service_installation",
    name="Panel/service-equipment installation practice",
    din_8580_class="ext.elec_install",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="design-tool cost (software), NOT a fabrication "
            "cost",
            note="same categorical note as branch-circuit wiring "
            "(procres/elec_install.md #99)",
        ),
    ),
    lead_class="as fast as the design tool computes (design practice)",
    provenance=(
        ProvenanceNote(
            posture="named_refusal",
            scope="record",
            detail="panel bus ampacity, main breaker/lugs rating, and "
            "branch slot count ALL require breaker/panel CATALOG "
            "content that is explicitly refused (D250 sec.3, confirmed "
            "still-refused as of WO-134's close-out) -- the clearest "
            "MISSING entry in the entire elec_install family: no "
            "panel-schedule stdlib records exist today (procres/"
            "elec_install.md #99)",
            refused_source="breaker/panel manufacturer catalog data "
            "(bus ampacity, breaker/lugs ratings, branch slot counts)",
            lift_condition="a licensed panel-manufacturer catalog "
            "(analogous to the already-obtained WO-134B Eaton Dry Type "
            "Transformer Catalogue) is obtained and transcribed with "
            "in-row citation",
        ),
        ProvenanceNote(
            posture="pd_gov",
            scope="transformer_loading",
            detail="transformer loading (if a step-down/service "
            "transformer is present) already has a discharged WO-134B "
            "record path (Eaton Dry Type Transformer Catalogue, owner-"
            "supplied real vendor data) -- confirmed real, the one "
            "piece of this entry that is NOT blocked (procres/"
            "elec_install.md #99)",
        ),
    ),
    dfm_check_ids=(f"{_CHECKS}:check_ampacity_containment",),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
PANEL_SERVICE_CHECKS = DfmCheckSet(
    family="panel_service_installation",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_ampacity_containment",
            provenance=ProvenanceNote(
                posture="named_refusal",
                scope="record",
                detail="panel bus ampacity >= declared connected+demand "
                "load could run today using WO-134-class demand-load "
                "machinery, but has no catalog panel record to check "
                "against -- a real, named BLOCKED state (procres/"
                "elec_install.md #99 DFM rule 1); this check-set entry "
                "reuses the branch-circuit ampacity callable, applied "
                "at the panel-bus level rather than the conductor level",
                refused_source="breaker/panel manufacturer catalog data "
                "(bus ampacity rating)",
                lift_condition="a licensed panel-manufacturer catalog is "
                "obtained and transcribed with in-row citation",
            ),
        ),
    ),
)

# --- 100. Conduit / raceway installation practice -----------------------

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONDUIT_RACEWAY_RECORD = ProcessRecord(
    key="std.process/conduit_raceway_installation",
    name="Conduit / raceway installation practice",
    din_8580_class="ext.elec_install",
    materials=(),
    size_limits=(),
    tolerance_grades=(),
    surface_finish=(),
    min_features=(),
    cost_drivers=(
        CostDriver(
            driver="setup",
            driver_class="design-tool cost (software), NOT a fabrication "
            "cost",
            note="same categorical note as branch-circuit wiring and "
            "panel/service installation (procres/elec_install.md #100)",
        ),
    ),
    lead_class="as fast as the design tool computes (design practice)",
    provenance=(
        ProvenanceNote(
            posture="gek",
            scope="record",
            detail="the QUALITATIVE existence of a fill-percentage rule "
            "and a bend-radius-as-a-multiple-of-diameter rule are safe "
            "GEK-tier engineering-consensus knowledge (procres/"
            "elec_install.md #100)",
        ),
        ProvenanceNote(
            posture="named_refusal",
            scope="dfm_check_ids",
            detail="NEC Ch.9 Table 1 verbatim fill percentages and NEC "
            "358.24 verbatim bend-radius tables are named refusals; "
            "exact numeric thresholds are declared caller parameters, "
            "never hard-coded here",
            refused_source="NFPA 70 (NEC) Ch.9 Table 1 (conduit fill "
            "percentages) and sec. 358.24 (bend-radius tables)",
            lift_condition="a licensed copy of NFPA 70 is obtained and "
            "the specific table rows are transcribed with in-row "
            "citation",
        ),
        ProvenanceNote(
            posture="gek",
            scope="support_spacing",
            detail="raceway support spacing crosses into calcite's "
            "structural-support-spacing domain; whether that machinery "
            "is currently wired for raceway-specific content is "
            "UNCONFIRMED per this recon pass, named rather than "
            "asserted either way (procres/elec_install.md #100)",
        ),
    ),
    dfm_check_ids=(
        f"{_CHECKS}:check_conduit_fill",
        f"{_CHECKS}:check_conduit_bend_radius",
    ),
)

# frob:doc docs/modules/py-harness.md#models-dfm-process
CONDUIT_RACEWAY_CHECKS = DfmCheckSet(
    family="conduit_raceway_installation",
    checks=(
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_conduit_fill",
            provenance=ProvenanceNote(
                posture="named_refusal",
                scope="record",
                detail="conductor-fill percentage <= a declared max fill "
                "(NEC Ch.9 Table 1-class); exact percentages/sizes are a "
                "named refusal, GEK-tier qualitative rule usable today "
                "(procres/elec_install.md #100 DFM rule 1)",
                refused_source="NFPA 70 (NEC) Ch.9 Table 1 verbatim fill "
                "percentages",
                lift_condition="a licensed copy of NFPA 70 is obtained "
                "and the table is transcribed with in-row citation",
            ),
        ),
        DfmCheckEntry(
            check_id=f"{_CHECKS}:check_conduit_bend_radius",
            provenance=ProvenanceNote(
                posture="named_refusal",
                scope="record",
                detail="bend radius >= declared minimum multiple of "
                "conduit/cable diameter (NEC 358.24-class); exact table "
                "values are a named refusal, GEK-tier multiple usable "
                "today (procres/elec_install.md #100 DFM rule 2)",
                refused_source="NFPA 70 (NEC) sec. 358.24 verbatim "
                "bend-radius tables",
                lift_condition="a licensed copy of NFPA 70 is obtained "
                "and the table is transcribed with in-row citation",
            ),
        ),
    ),
)

__all__ = [
    "BRANCH_CIRCUIT_CHECKS",
    "BRANCH_CIRCUIT_RECORD",
    "CONDUIT_RACEWAY_CHECKS",
    "CONDUIT_RACEWAY_RECORD",
    "CONFORMAL_COATING_CHECKS",
    "CONFORMAL_COATING_RECORD",
    "PANEL_SERVICE_CHECKS",
    "PANEL_SERVICE_RECORD",
    "PCB_FAB_CHECKS",
    "PCB_FAB_RECORD",
    "PERFBOARD_ASSEMBLY_CHECKS",
    "PERFBOARD_ASSEMBLY_RECORD",
    "SMT_ASSEMBLY_CHECKS",
    "SMT_ASSEMBLY_RECORD",
    "THROUGH_HOLE_WAVE_SOLDER_CHECKS",
    "THROUGH_HOLE_WAVE_SOLDER_RECORD",
]
