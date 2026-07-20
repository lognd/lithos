use super::build_obligations;
use crate::checks::run_checks;
use crate::contracts::build_contract_ir;
use crate::entities::build_entities;
use crate::output::ParsedFile;
use camino::Utf8PathBuf;

fn parsed(src: &str) -> Vec<ParsedFile> {
    let path = Utf8PathBuf::from("t.hema");
    vec![ParsedFile {
        path: path.clone(),
        parse: regolith_syntax::parse(src, &path),
    }]
}

fn obligations(src: &str) -> Vec<super::Obligation> {
    let files = parsed(src);
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
}

/// The full [`ObligationSet`] (diagnostics included), with an
/// optional realized-geometry input for the decl named `subject`
/// (WO-69: proves the `geometry.realized` `PayloadRef` only appears
/// when the build actually supplied one).
fn plan_obligation_set(src: &str, realized_geometry_for: Option<&str>) -> super::ObligationSet {
    let files = parsed(src);
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let mut realized_inputs = crate::realized_input::RealizedInputs::new();
    if let Some(subject) = realized_geometry_for {
        realized_inputs.insert(
            "blake3:plantarget".to_string(),
            crate::realized_input::RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: subject.to_string(),
                bytes: vec![1, 2, 3],
            },
        );
    }
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs)
}

/// A calcite `.calx` source's obligations (WO-68 regression
/// coverage): calcite's top-level `require` group rides the same
/// `File::fluid_requires`/`push_calcite_frame_obligations` path as
/// fluorite, so this is the live footbridge-repro shape end to end.
fn calx_obligations(src: &str) -> Vec<super::Obligation> {
    let path = Utf8PathBuf::from("t.calx");
    let files = vec![ParsedFile {
        path: path.clone(),
        parse: regolith_syntax::parse(src, &path),
    }];
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
}

/// A fluid claim over a self-contained flownet (WO-32 deliverable
/// 4a): the `require` group is NOT a plain `Decl` (fluorite's
/// `File::fluid_requires`), so this exercises the dedicated
/// `push_fluid_obligations` pass end to end.
fn fluid_obligations(src: &str) -> Vec<super::Obligation> {
    let path = Utf8PathBuf::from("t.fluo");
    let files = vec![ParsedFile {
        path: path.clone(),
        parse: regolith_syntax::parse(src, &path),
    }];
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
}

/// Same as [`fluid_obligations`] but returns the full [`ObligationSet`]
/// (WO-32 deliverable 5: E0203 assertions need the diagnostics too).
fn fluid_obligation_set(src: &str) -> super::ObligationSet {
    let path = Utf8PathBuf::from("t.fluo");
    let files = vec![ParsedFile {
        path: path.clone(),
        parse: regolith_syntax::parse(src, &path),
    }];
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs)
}

const FLUID_SRC: &str = "medium Water: liquid\n\
        \x20   props: registry(potable_water_nist)\n\
        flownet Loop(medium=Water):\n\
        \x20   reference: ambient(101kPa, 293K)\n\
        \x20   nodes: a, b\n\
        \x20   edges:\n\
        \x20       supply: Pipe(from=line.run) (a -> b)\n\
        require Margin:\n\
        \x20   dp: fluids.dp(a -> b) <= 40kPa\n";

#[test]
fn fluid_claim_lowers_to_an_obligation_with_a_flownet_payload_ref() {
    let obls = fluid_obligations(FLUID_SRC);
    assert_eq!(obls.len(), 1, "one fluid claim -> one obligation");
    let obl = &obls[0];
    assert_eq!(obl.payloads.len(), 1, "carries exactly one payload ref");
    let payload_ref = &obl.payloads[0];
    assert_eq!(payload_ref.kind, "flownet");
    assert!(!payload_ref.digest.is_empty(), "resolvable digest");
    assert_eq!(payload_ref.origin, "Loop");
    assert_eq!(obl.subject_ref, payload_ref.digest);
}

#[test]
fn fluid_claim_suffix_givens_thread_into_given_loads() {
    // WO-94 escalation 1: a `given <ident> = <expr>` suffix on a fluid
    // claim threads quantity-valued bindings into `given.loads` (the
    // translate call-kwargs fallback channel) and is stripped from the
    // comparison text, while a regime-selector given (`v3 = brew`)
    // stays dropped so the generic scalar path never hard-defers.
    let src = "medium Water: liquid\n\
            \x20   props: registry(potable_water_nist)\n\
            flownet Loop(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n\
            require Margin:\n\
            \x20   dp: fluids.dp(a -> b) <= 40kPa given T_group = 90degC, v3 = brew\n";
    let obls = fluid_obligations(src);
    assert_eq!(obls.len(), 1);
    let obl = &obls[0];
    assert_eq!(
        obl.given.loads,
        vec!["T_group: 90degC".to_string()],
        "quantity given threaded; regime selector `v3 = brew` dropped"
    );
    let super::ClaimForm::Comparison { lhs, rhs, .. } = &obl.claim.form else {
        panic!("comparison form");
    };
    assert_eq!(lhs, "fluids.dp(a -> b)", "given suffix stripped from LHS");
    assert_eq!(
        rhs, "40000Pa",
        "given suffix never pollutes the RHS bound (D256: unit token preserved)"
    );
}

#[test]
fn fluid_comparator_after_call_lowers_to_a_real_comparator_op() {
    // WO-92 deliverable 2: a fluid predicate whose comparator sits
    // after the `fluids.*(...)` call (`fluids.dp(a -> b) <= 40kPa`)
    // must lower with a REAL comparator op + the call as LHS, not the
    // opaque `op="require"` blob -- otherwise the translate-side
    // head-only `_split_comparator` cannot see the comparator and
    // defers `unsupported_op`. The `->` inside the call parens is at
    // bracket depth > 0, so it is not mistaken for a comparator.
    let obls = fluid_obligations(FLUID_SRC);
    let super::ClaimForm::Comparison { lhs, op, rhs } = &obls[0].claim.form else {
        panic!("fluid claim lowers to a Comparison form");
    };
    assert_eq!(op, "<=", "structural comparator recovered, not `require`");
    assert_eq!(lhs, "fluids.dp(a -> b)", "LHS is the whole call expression");
    assert_eq!(
        rhs, "40000Pa",
        "RHS is the unit-resolved bound (40kPa -> 40000 Pa, unit preserved D256)"
    );
    // Claim identity (the model-routing key) stays the field name.
    assert_eq!(obls[0].claim.name.as_deref(), Some("dp"));
}

#[test]
fn dp_claim_over_a_bare_pipe_does_not_trigger_e0203() {
    // WO-32 deliverable 5: E0203 governs transient/volume-budget
    // claims only (`fluids.volume_consumed`); an ordinary `dp` claim
    // over the same compliance-less edge is untouched.
    let set = fluid_obligation_set(FLUID_SRC);
    assert!(
        set.diagnostics
            .iter()
            .all(|d| d.code.to_string() != "E0203"),
        "{:?}",
        set.diagnostics
    );
}

const FLUID_VOLUME_BUDGET_NO_COMPLIANCE_SRC: &str = "medium HydOil: liquid\n\
        \x20   props: registry(iso_vg32_hydraulic)\n\
        flownet Rigid(medium=HydOil):\n\
        \x20   reference: ambient(101kPa, 293K)\n\
        \x20   nodes: a, b\n\
        \x20   edges:\n\
        \x20       pipe: Pipe(from=nowhere.run) (a -> b)\n\
        require Budget:\n\
        \x20   bad: fluids.volume_consumed([pipe], at=10MPa) < 1L\n";

#[test]
fn volume_consumed_over_an_edge_with_no_compliance_flags_e0203() {
    // WO-32 deliverable 5 (fluorite/03 sec. 1): `pipe` has neither a
    // `compliance=` record nor (this session's `AstFlownetInputs`,
    // WO-42's realized-geometry channel not yet wired to a real
    // wall record either) an extractable wall -- the claim is
    // undischargeable and must reject at compile time.
    let set = fluid_obligation_set(FLUID_VOLUME_BUDGET_NO_COMPLIANCE_SRC);
    let codes: Vec<String> = set.diagnostics.iter().map(|d| d.code.to_string()).collect();
    assert!(codes.contains(&"E0203".to_string()), "{codes:?}");
}

#[test]
fn volume_consumed_over_an_unknown_edge_id_is_not_this_checks_job() {
    // A claim naming an edge id absent from the flownet's edge list
    // is a different (undeclared-reference) problem; E0203 stays
    // silent rather than misreport it.
    let src = "medium Water: liquid\n\
            \x20   props: registry(potable_water_nist)\n\
            flownet Loop(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n\
            require Budget:\n\
            \x20   bad: fluids.volume_consumed([nope], at=10MPa) < 1L\n";
    let set = fluid_obligation_set(src);
    assert!(
        set.diagnostics
            .iter()
            .all(|d| d.code.to_string() != "E0203"),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn fluid_obligation_is_deterministic() {
    // AD-6: same source, same obligation content hash, twice.
    let a = &fluid_obligations(FLUID_SRC)[0];
    let b = &fluid_obligations(FLUID_SRC)[0];
    assert_eq!(a.content_hash(), b.content_hash());
}

#[test]
fn fluid_source_populates_the_flownets_emission_set() {
    // WO-32 deliverable 4b: `ObligationSet.flownets` is the seam
    // `LowerOutput.flownets`/`BuildPayload.flownets` reads -- it
    // must carry the same elaborated payload the obligation's
    // `PayloadRef.digest` names, without a second elaboration.
    let path = Utf8PathBuf::from("t.fluo");
    let files = vec![ParsedFile {
        path: path.clone(),
        parse: regolith_syntax::parse(FLUID_SRC, &path),
    }];
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let set = build_obligations(
        &files,
        &snaps,
        &checks,
        &graph,
        &crate::realized_input::RealizedInputs::new(),
    );
    assert_eq!(set.flownets.len(), 1, "one flownet elaborated");
    assert_eq!(set.flownets[0].name, "Loop");
    let obl = &set.obligations[0];
    let payload_ref = &obl.payloads[0];
    assert_eq!(
        set.flownets[0].payload.content_digest().unwrap(),
        payload_ref.digest,
        "the emitted flownet's digest matches the obligation's payload ref"
    );
}

#[test]
fn non_fluid_source_produces_no_fluid_obligation_noise() {
    // A plain hematite source has no `flownet`/`require fluids.*`
    // surface: `push_fluid_obligations` must contribute nothing.
    let src = "part p:\n    require R:\n        strength: >= 1\n";
    let obls = obligations(src);
    assert!(obls.iter().all(|o| o.payloads.is_empty()));
}

fn obligation_set(src: &str) -> super::ObligationSet {
    let files = parsed(src);
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    build_obligations(
        &files,
        &snaps,
        &checks,
        &graph,
        &crate::realized_input::RealizedInputs::new(),
    )
}

#[test]
fn compute_claim_produces_one_obligation_and_one_field_datum() {
    // WO-33 D98 deliverable 3: a zone-indexed `compute` claim lowers
    // to exactly one obligation (`ClaimForm::Compute`) plus one
    // `FieldDatum` ledger entry with a null (pre-discharge) payload.
    let src = "part liner:\n    require Thermal:\n        compute wall_T: thermo.wall_temperature over liner.zones\n";
    let set = obligation_set(src);
    assert_eq!(set.field_datums.len(), 1);
    let datum = &set.field_datums[0];
    assert_eq!(datum.name, "wall_T");
    assert_eq!(datum.quantity_kind, "thermo.wall_temperature");
    assert!(datum.payload.is_none(), "pre-discharge payload is null");
    assert_eq!(
        datum.axis.method,
        regolith_oblig::CoverageMethod::Undischarged
    );

    let compute_obls: Vec<_> = set
        .obligations
        .iter()
        .filter(|o| matches!(o.claim.form, super::ClaimForm::Compute { .. }))
        .collect();
    assert_eq!(compute_obls.len(), 1, "exactly one producer obligation");
    if let super::ClaimForm::Compute {
        quantity_kind,
        over,
    } = &compute_obls[0].claim.form
    {
        assert_eq!(quantity_kind, "thermo.wall_temperature");
        assert_eq!(over, "liner.zones");
    } else {
        unreachable!();
    }
}

#[test]
fn config_indexed_compute_claim_declares_an_interval_axis() {
    let src = "part susp:\n    require Kinematics:\n        compute camber: vehicle.camber over travel in [-80mm, 120mm]\n";
    let set = obligation_set(src);
    let datum = &set.field_datums[0];
    assert_eq!(datum.axis.axis, "travel");
    assert_eq!(
        datum.axis.domain,
        regolith_oblig::CoverageDomain::Interval("[-80mm, 120mm]".to_string())
    );
}

#[test]
fn projection_references_the_producing_field_by_digest_slot() {
    // Deliverable 3: a `max(wall_T) < 800K` claim's obligation gains
    // a `given.refs` entry pointing at the compute obligation's
    // content hash -- the promise-chain reference.
    let src = "part liner:\n    require Thermal:\n        compute wall_T: thermo.wall_temperature over liner.zones\n        tip_temp: max(wall_T) < 800K\n";
    let set = obligation_set(src);
    let producer = set
        .obligations
        .iter()
        .find(|o| matches!(o.claim.form, super::ClaimForm::Compute { .. }))
        .expect("producer obligation");
    let consumer = set
        .obligations
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("tip_temp"))
        .expect("consumer obligation");
    assert!(
        consumer.given.refs.contains(&(
            "wall_T".to_string(),
            format!("field:{}", producer.content_hash())
        )),
        "consumer given.refs: {:?}",
        consumer.given.refs
    );
    assert!(set.diagnostics.is_empty());
}

#[test]
fn projection_naming_an_undeclared_field_is_an_unresolved_reference() {
    let src = "part liner:\n    require Thermal:\n        tip_temp: max(wall_T) < 800K\n";
    let set = obligation_set(src);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::UNRESOLVED_FIELD_REFERENCE),
        "expected an unresolved-field-reference diagnostic: {:?}",
        set.diagnostics
    );
}

#[test]
fn call_form_arguments_are_never_projection_references() {
    // Coordinator-verified E0303 misfire (the live cubesat repro):
    // a claim whose lhs is a CALL EXPRESSION -- windowed
    // (`thermo.temperature(...) within [lo, hi]`) or scalar with a
    // longer callee that merely ENDS in a projection keyword
    // (`info.fmax(core_clk)`) or a dotted keyword-named callee with
    // a nested call argument (`elec.min(v(store.cells.any))`) --
    // must NOT have its argument misread as a computed-field
    // projection. None of these decls declares a `compute` claim,
    // so any E0303 here is the misfire.
    let src = "part p:\n    require Mixed:\n        \
                   batt_window: thermo.temperature(eps.store.cells) within [0degC, 45degC]\n        \
                   fmax: info.fmax(core_clk) >= 120MHz\n        \
                   never_flat: forall op in {a, b}: elec.min(v(store.cells.any)) > 3.0V\n";
    let set = obligation_set(src);
    assert!(
        !set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::UNRESOLVED_FIELD_REFERENCE),
        "call arguments misread as projections: {:?}",
        set.diagnostics
    );
}

#[test]
fn a_compute_compute_cycle_is_a_diagnostic_naming_the_chain() {
    // A sibling `compute` consuming another as a given, in a cycle,
    // must be a compile diagnostic naming the cycle -- never a panic
    // or an infinite loop.
    let src = "part susp:\n    require Kinematics:\n        compute mr: vehicle.motion_ratio over roll_stiffness\n        compute roll_stiffness: vehicle.roll_stiffness over mr\n";
    let set = obligation_set(src);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::COMPUTE_FIELD_CYCLE),
        "expected a compute-field cycle diagnostic: {:?}",
        set.diagnostics
    );
}

#[test]
fn given_captures_material_so_the_key_is_mutation_sensitive() {
    // BE-2/INV-1: two decls differing ONLY in material must hash to
    // different obligations (no shared cached evidence).
    let a = "part p:\n    material: AL7075_T6\n    require R:\n        strength: >= 1\n";
    let b = "part p:\n    material: TI64\n    require R:\n        strength: >= 1\n";
    let oa = &obligations(a)[0];
    let ob = &obligations(b)[0];
    assert!(
        !oa.given.materials.is_empty(),
        "material populated into given"
    );
    assert_ne!(
        oa.content_hash(),
        ob.content_hash(),
        "changing material must change the obligation key"
    );
}

#[test]
fn loads_block_is_threaded_into_given() {
    let src = "part p:\n    loads:\n        radial: derived\n    require R:\n        s: >= 1\n";
    let obl = &obligations(src)[0];
    assert!(
        obl.given.loads.iter().any(|l| l.contains("radial")),
        "loads block threaded into given: {:?}",
        obl.given.loads
    );
}

#[test]
fn an_impl_binding_emits_a_conformance_obligation() {
    // BE-6/INV-13: an in-body `impl X for Y:` yields a conformance
    // obligation.
    let src = "part p:\n    impl Seat for self:\n        x: 1\n";
    let obl = obligations(src);
    assert!(
        obl.iter().any(|o| matches!(
            &o.claim.form,
            super::ClaimForm::Comparison { op, .. } if op == "conforms"
        )),
        "expected a conformance obligation"
    );
}

#[test]
fn conformance_windows_match_promised_bounds_by_name_not_position() {
    // WO-26 D104: the impl's SECOND field, `y`, must be matched
    // against the interface's promised `y` bound -- not its FIRST
    // field `x` -- because matching is now by field NAME.
    let src = "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self:\n        x: <= 5\n        y: <= 14\n";
    let set = obligation_set(src);
    let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
    assert!(
        conforms.given.loads.iter().any(|l| l == "spec_bound: 20"),
        "expected the name-matched `y` promise (20), got {:?}",
        conforms.given.loads
    );
    assert!(
        conforms.given.loads.iter().any(|l| l == "impl_bound: 14"),
        "expected the name-matched `y` realization (14), got {:?}",
        conforms.given.loads
    );
    assert!(
        set.diagnostics.is_empty(),
        "every promised name matched; no diagnostic expected: {:?}",
        set.diagnostics
    );
}

#[test]
fn a_promised_bound_with_no_matching_impl_field_is_diagnosed() {
    // WO-26 D104: the interface promises `y`, but the impl only
    // realizes `x` -- a constructive diagnostic naming both sides,
    // not a silent defer.
    let src = "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self:\n        x: <= 5\n";
    let set = obligation_set(src);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::PROMISED_BOUND_UNMATCHED),
        "expected a PROMISED_BOUND_UNMATCHED diagnostic: {:?}",
        set.diagnostics
    );
}

#[test]
fn generic_pin_resolves_the_spec_side_only() {
    // D195 (WO-92): `impl Drive<watts=50W>` against the parametric
    // promise `power: <= watts` resolves the SPEC side (sense +
    // spec_bound + field name in given.loads) and NEVER fabricates
    // an impl_bound -- the impl body asserts nothing (`= todo!`),
    // and a fabricated 50 <= 50 would discharge vacuously.
    let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=50W> for self as d = todo!\n";
    let set = obligation_set(src);
    let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
    assert!(
        conforms
            .given
            .loads
            .iter()
            .any(|l| l == "conformance_sense: upper"),
        "sense carried: {:?}",
        conforms.given.loads
    );
    assert!(
        conforms.given.loads.iter().any(|l| l == "spec_bound: 50"),
        "pin-resolved spec bound (50W -> 50) carried: {:?}",
        conforms.given.loads
    );
    assert!(
        conforms
            .given
            .loads
            .iter()
            .any(|l| l == "conformance_field: power"),
        "field name carried for the teaching deferral: {:?}",
        conforms.given.loads
    );
    assert!(
        !conforms
            .given
            .loads
            .iter()
            .any(|l| l.starts_with("impl_bound:")),
        "NEVER a fabricated impl bound: {:?}",
        conforms.given.loads
    );
}

#[test]
fn unresolvable_generic_pin_emits_no_spec_bound() {
    // D195: a pin whose value is not a leading quantity (`watts=` a
    // bare identifier) cannot resolve the parametric promise -- no
    // window lines at all, the existing blanket deferral stands.
    let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=unknown_budget> for self as d = todo!\n";
    let set = obligation_set(src);
    let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
    assert!(
        conforms.given.loads.is_empty(),
        "unresolvable pin -> no window lines, never a guess: {:?}",
        conforms.given.loads
    );
}

#[test]
fn generic_pin_spec_side_with_impl_body_bound_is_a_full_window() {
    // D195 rule 2a: the impl side arrives via an explicit re-declared
    // bound in the impl BODY; combined with the pin-resolved spec
    // side this is a dischargeable Both window (spec 50, impl 45).
    let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=50W> for self as d:\n\
            \x20       power: <= 45\n";
    let set = obligation_set(src);
    let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
    assert!(
        conforms.given.loads.iter().any(|l| l == "spec_bound: 50"),
        "pin-resolved spec side: {:?}",
        conforms.given.loads
    );
    assert!(
        conforms.given.loads.iter().any(|l| l == "impl_bound: 45"),
        "impl-BODY-declared bound (never the pin): {:?}",
        conforms.given.loads
    );
}

#[test]
fn literal_promise_with_no_impl_bound_carries_the_spec_only_window() {
    // D195: a LITERAL promise the impl body never refines (the
    // FittingPort.leak shape) now carries sense + spec_bound + field
    // (no impl_bound) so translate can defer teaching what the impl
    // owes -- distinct from the nothing-scalar-to-compare shape.
    let src = "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self = todo!\n";
    let set = obligation_set(src);
    let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
    assert!(
        conforms.given.loads.iter().any(|l| l == "spec_bound: 20"),
        "{:?}",
        conforms.given.loads
    );
    assert!(
        conforms
            .given
            .loads
            .iter()
            .any(|l| l == "conformance_field: y"),
        "{:?}",
        conforms.given.loads
    );
    assert!(
        !conforms
            .given
            .loads
            .iter()
            .any(|l| l.starts_with("impl_bound:")),
        "{:?}",
        conforms.given.loads
    );
}

#[test]
fn a_poisoned_subject_emits_no_obligation() {
    let src = "part bad:\n    )\n    require R:\n        s: >= 1\npart good:\n    require R:\n        s: >= 1\n";
    let obl = obligations(src);
    // Exactly one require obligation (from `good`); `bad` is gated.
    let require_count = obl
        .iter()
        .filter(|o| {
            matches!(
                &o.claim.form,
                super::ClaimForm::Comparison { op, .. } if op == "require"
            )
        })
        .count();
    assert_eq!(require_count, 1, "poisoned subject `bad` must not obligate");
}

#[test]
fn realization_obligation_is_emitted_per_declared_edge() {
    let src = "system Sys:\n    intents:\n        decide: compute(law)\n    workloads:\n        att: loop(rate=4Hz) realizes decide\n";
    let obl = obligations(src);
    let realizes_obl = obl
        .iter()
        .find(
            |o| matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "implies"),
        )
        .expect("a realization obligation is emitted");
    match &realizes_obl.claim.form {
        super::ClaimForm::Comparison { lhs, rhs, .. } => {
            assert_eq!(lhs, "att");
            assert_eq!(rhs, "decide");
        }
        _ => unreachable!(),
    }
    assert!(
        realizes_obl.given.loads.is_empty(),
        "a declared edge carries no derived cause"
    );
    assert!(realizes_obl.hints.is_empty());
}

#[test]
fn derived_edge_tags_its_obligation_with_the_derived_cause() {
    let src = "system Sys:\n    intents:\n        decide: compute(law)\n";
    let obl = obligations(src);
    let derived_obl = obl
        .iter()
        .find(
            |o| matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "implies"),
        )
        .expect("a derived realization obligation is emitted");
    assert!(
        derived_obl
            .given
            .loads
            .iter()
            .any(|l| l == "cause: derived(intent decide)"),
        "derived cause tagged in given.loads: {:?}",
        derived_obl.given.loads
    );
    assert!(derived_obl
        .hints
        .iter()
        .any(|h| h == "derived(intent decide)"));
}

#[test]
fn unit_suffixed_bound_resolves_through_regolith_qty() {
    // WO-26 deliverable 1: `<= 0.2mm` and `>= 6800 N` resolve to SI
    // base numerals (meters, newtons) instead of the naive leading
    // digits, so the orchestrator's numeric parse sees the RIGHT
    // magnitude, not a unit-blind literal.
    let src = "part p:\n    require R:\n        sag: <= 0.2mm\n        preload: >= 6800 N\n";
    let obl = obligations(src);
    let bounds: Vec<String> = obl
        .iter()
        .map(|o| match &o.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => rhs.clone(),
            _ => String::new(),
        })
        .collect();
    assert!(
        bounds.iter().any(|b| b == "<= 0.0002m"),
        "0.2mm resolved to meters, unit preserved (D256): {bounds:?}"
    );
    assert!(
        bounds.iter().any(|b| b == ">= 6800N"),
        "6800 N resolved (N is already SI base), unit preserved (D256): {bounds:?}"
    );
}

#[test]
fn unresolvable_suffix_passes_through_unchanged() {
    // A non-unit suffix (`dB`) is left exactly as written -- never an
    // invented conversion (INV-24/26 honesty).
    let src = "part p:\n    require R:\n        margin: >= 6dB\n";
    let obl = &obligations(src)[0];
    match &obl.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert_eq!(rhs, ">= 6dB", "unrecognized unit left untouched");
        }
        _ => unreachable!(),
    }
}

#[test]
fn temperature_offset_unit_resolves_through_its_additive_offset() {
    // `degC` is an offset unit (regolith/02 sec. 1): 85 degC resolves
    // to its Kelvin SI-base value (358.15), not a bare 85.
    let src = "part p:\n    require R:\n        junction: <= 85degC\n";
    let obl = &obligations(src)[0];
    match &obl.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert_eq!(
                rhs, "<= 358.15K",
                "degC resolved via its additive offset, unit preserved (D256)"
            );
        }
        _ => unreachable!(),
    }
}

#[test]
fn within_lo_hi_window_splits_into_two_bound_obligations() {
    // WO-26 deliverable 2: a `within [lo, hi]` demanded window becomes
    // two one-sided obligations over the same subject, each carrying
    // its own resolved bound -- the orchestrator's existing scalar
    // path then lowers each to a real DischargeRequest (no more
    // `unsupported_op` deferral for a within-windowed claim).
    let src = "part p:\n    require Thermal:\n        batt_window: thermo.temperature(eps.store.cells)\n                         within [0degC, 45degC] forall op\n";
    let obl = obligations(src);
    let named: Vec<(String, String, String, String)> = obl
        .iter()
        .filter_map(|o| match &o.claim.form {
            super::ClaimForm::Comparison { lhs, op, rhs } => Some((
                o.claim.name.clone().unwrap_or_default(),
                lhs.clone(),
                op.clone(),
                rhs.clone(),
            )),
            _ => None,
        })
        .collect();
    assert_eq!(named.len(), 2, "exactly two halves emitted: {named:?}");
    let lo = named
        .iter()
        .find(|(name, ..)| name == "batt_window.lo")
        .expect("lo half present");
    assert_eq!(lo.2, ">=");
    assert_eq!(
        lo.3, "273.15K",
        "0degC resolved to Kelvin, unit preserved (D256)"
    );
    let hi = named
        .iter()
        .find(|(name, ..)| name == "batt_window.hi")
        .expect("hi half present");
    assert_eq!(hi.2, "<=");
    assert_eq!(
        hi.3, "318.15K",
        "45degC resolved to Kelvin, unit preserved (D256)"
    );
    // batt_window residual: each half's LHS is the full call
    // expression, NOT the bare `batt_window` label, so translate's
    // `_match_call_lhs` can route it to `thermo.junction_temperature`.
    assert_eq!(lo.1, "thermo.temperature(eps.store.cells)");
    assert_eq!(hi.1, "thermo.temperature(eps.store.cells)");
}

#[test]
fn peak_with_during_window_lowers_to_a_typed_reduction() {
    // D102: a REDUCTION form with a `during` window and a trailing
    // comparator constructs `ClaimForm::Peak` (op/rhs typed, not an
    // opaque Comparison blob).
    let src = "part p:\n    require Structural:\n        grms_ok: peak(mech.stress.von_mises, during boundary.load_spectrum) < 200MPa\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Peak {
            signal,
            window,
            op,
            rhs,
        } => {
            assert_eq!(signal, "mech.stress.von_mises");
            assert_eq!(
                *window,
                super::Window::During("boundary.load_spectrum".to_string())
            );
            assert_eq!(op, "<");
            assert_eq!(
                rhs, "200000000Pa",
                "MPa resolved to Pa, unit preserved (D256)"
            );
        }
        other => panic!("expected ClaimForm::Peak, got {other:?}"),
    }
}

#[test]
fn peak_with_within_after_window_lowers_to_a_typed_reduction() {
    let src = "part p:\n    require Drive:\n        coil_ok: peak(v(mv_f), within 5ms after mv_f.close) < 45V\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Peak { window, op, .. } => {
            assert_eq!(
                *window,
                super::Window::WithinAfter {
                    duration: "0.005s".to_string(),
                    event: "mv_f.close".to_string(),
                },
                "5ms duration resolved to seconds, unit preserved (D256)"
            );
            assert_eq!(op, "<");
        }
        other => panic!("expected ClaimForm::Peak, got {other:?}"),
    }
}

#[test]
fn peak_with_at_location_tag_is_left_untyped() {
    // A spatial `at=` tag is not a D102 temporal window; the claim
    // stays the pre-existing untyped `Comparison` (an honest,
    // recorded scope narrowing, not a silent guess).
    let src = "part p:\n    require Structural:\n        shell: peak(mech.stress.von_mises, at=welded.tank.shell) < material.sigma_y\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    assert!(matches!(
        obl[0].claim.form,
        super::ClaimForm::Comparison { .. }
    ));
}

#[test]
fn rms_with_band_lowers_to_a_typed_reduction() {
    let src =
        "part p:\n    require Noise:\n        floor: rms(v(out), band=[100kHz, 10MHz]) < 20mV\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Rms {
            signal,
            band,
            op,
            rhs,
        } => {
            assert_eq!(signal, "v(out)");
            assert_eq!(band, "[100kHz, 10MHz]");
            assert_eq!(op, "<");
            assert_eq!(
                rhs, "0.02V",
                "20mV resolved to volts, unit preserved (D256)"
            );
        }
        other => panic!("expected ClaimForm::Rms, got {other:?}"),
    }
}

#[test]
fn peak_reduction_with_no_trailing_comparator_is_a_compile_diagnostic() {
    let src = "part p:\n    require Structural:\n        bad: peak(mech.stress.von_mises, during boundary.load_spectrum)\n";
    let set = obligation_set(src);
    assert!(
        set.obligations.is_empty(),
        "no obligation for a diagnosed claim"
    );
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::TEMPORAL_REDUCTION_MISSING_COMPARATOR),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn settles_lowers_to_a_typed_containment() {
    let src = "part p:\n    require Regulation:\n        transient: settles(v(out), to=+-2%, within 500us after load_step)\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Settles {
            signal,
            tol,
            window,
        } => {
            assert_eq!(signal, "v(out)");
            assert_eq!(tol, "+-2%");
            assert_eq!(
                *window,
                super::Window::WithinAfter {
                    duration: "0.0005s".to_string(),
                    event: "load_step".to_string(),
                },
                "500us duration resolved to seconds, unit preserved (D256)"
            );
        }
        other => panic!("expected ClaimForm::Settles, got {other:?}"),
    }
}

#[test]
fn settles_with_trailing_comparator_is_a_compile_diagnostic() {
    let src = "part p:\n    require Regulation:\n        bad: settles(v(out), to=+-2%, within 500us after load_step) < 1\n";
    let set = obligation_set(src);
    assert!(set.obligations.is_empty());
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn stays_within_with_no_window_lowers_to_a_typed_containment() {
    let src = "part p:\n    require Survival:\n        mask_ok: stays_within(emissions, mask=fcc_part90_mask(25kHz))\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::StaysWithin {
            signal,
            mask,
            window,
        } => {
            assert_eq!(signal, "emissions");
            assert_eq!(mask, "fcc_part90_mask(25kHz)");
            assert_eq!(*window, None);
        }
        other => panic!("expected ClaimForm::StaysWithin, got {other:?}"),
    }
}

#[test]
fn stays_within_with_a_window_lowers_to_a_typed_containment() {
    // WO-54 rider: `ClaimForm::StaysWithin` now carries a `window`
    // field, so the dune-buggy/buck-converter windowed corpus
    // shape types through instead of falling back to Comparison.
    let src = "part p:\n    require Survival:\n        landing: stays_within(mech.load(frame.pickups.all), mask=dune_jump_srs, during event(jump_landing))\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::StaysWithin {
            signal,
            mask,
            window,
        } => {
            assert_eq!(signal, "mech.load(frame.pickups.all)");
            assert_eq!(mask, "dune_jump_srs");
            assert_eq!(
                *window,
                Some(super::Window::During("event(jump_landing)".to_string()))
            );
        }
        other => panic!("expected ClaimForm::StaysWithin, got {other:?}"),
    }
}

#[test]
fn stays_within_floor_mask_units_resolve_but_named_masks_stay_verbatim() {
    // WO-112 Class 3 (F131 item 1a): an inline `floor(...)` scalar
    // mask resolves its unit suffixes at lowering (`5.0V - 150mV`
    // -> `5 - 0.15`), so the orchestrator reads the level without
    // re-implementing units; a NAMED mask reference is hash-pinned
    // text and is never rewritten (the prior two tests pin that).
    let src = "part p:\n    require Rails:\n        sag: stays_within(v(out), mask=floor(5.0V - 150mV), within 500us after load_step)\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::StaysWithin { mask, window, .. } => {
            assert_eq!(
                mask, "floor(5V - 0.15V)",
                "unit preserved on both operands (D256)"
            );
            assert!(window.is_some());
        }
        other => panic!("expected ClaimForm::StaysWithin, got {other:?}"),
    }
}

#[test]
fn overshoot_lowers_to_a_typed_reduction() {
    let src =
        "part p:\n    require Transient:\n        os: overshoot(v(out), after load_step) < 5%\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Overshoot {
            signal,
            event,
            op,
            rhs,
        } => {
            assert_eq!(signal, "v(out)");
            assert_eq!(event, "load_step");
            assert_eq!(op, "<");
            assert_eq!(rhs, "5%", "a bare % suffix is not a regolith-qty unit");
        }
        other => panic!("expected ClaimForm::Overshoot, got {other:?}"),
    }
}

#[test]
fn forall_interval_prefix_lowers_into_the_sweep_slot() {
    // D105a: the buck-efficiency shape -- an interval sweep prefix
    // becomes the obligation's SweepDomain; the remainder lowers as
    // an ordinary (here general-comparison) claim.
    let src = "part p:\n    require Efficiency:\n        eta: forall i(out) in [0.2A, i_max]: elec.power(out) / elec.power(vin) >= 85%\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    let sweep = obl[0].sweep.as_ref().expect("sweep populated");
    assert_eq!(sweep.axis, "i(out)");
    assert_eq!(
        sweep.domain, "[0.2A, i_max]",
        "0.2A resolved to amperes, unit preserved (D256)"
    );
    match &obl[0].claim.form {
        super::ClaimForm::Comparison { lhs, op, rhs } => {
            assert_eq!(lhs, "elec.power(out) / elec.power(vin)");
            assert_eq!(op, ">=");
            assert_eq!(rhs, "85%");
        }
        other => panic!("expected general Comparison, got {other:?}"),
    }
}

#[test]
fn forall_discrete_prefix_lowers_into_the_sweep_slot() {
    let src = "part p:\n    require Modes:\n        ok: forall m in {run, idle}: thermo.temperature(core) <= 85degC\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    let sweep = obl[0].sweep.as_ref().expect("sweep populated");
    assert_eq!(sweep.axis, "m");
    assert_eq!(sweep.domain, "{run, idle}");
}

#[test]
fn mid_expression_comparator_splits_into_a_general_comparison() {
    // D103: `expr <op> bound` with the comparator mid-expression
    // becomes a real Comparison (lhs kept, bound unit-resolved),
    // not the opaque op="require" blob.
    let src = "part p:\n    require Thermal:\n        fet_t: thermo.temperature(sw.fet.junction) < 110degC\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Comparison { lhs, op, rhs } => {
            assert_eq!(lhs, "thermo.temperature(sw.fet.junction)");
            assert_eq!(op, "<");
            assert_eq!(
                rhs, "383.15K",
                "110degC resolved to Kelvin, unit preserved (D256)"
            );
        }
        other => panic!("expected general Comparison, got {other:?}"),
    }
}

/// WO-80 deliverable 2 (regolith/12 sec. 2 rung 5): a claim's
/// trailing `, model=<ident>` pin lowers into `Claim::model_pin`
/// AND never re-enters the comparison rhs -- WO-76's audit finding
/// (the pin text used to be swallowed whole into the rhs) is fixed.
#[test]
fn model_pin_lowers_into_the_claim_and_never_into_rhs() {
    let src = "part gear:\n    \
                   require Mesh:\n        \
                   contact: mech.contact_stress(mesh) < 1400 MPa, sf=1.2, model=fea_contact\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    assert_eq!(obl[0].claim.model_pin.as_deref(), Some("fea_contact"));
    match &obl[0].claim.form {
        super::ClaimForm::Comparison { lhs, op, rhs } => {
            assert_eq!(lhs, "mech.contact_stress(mesh)");
            assert_eq!(op, "<");
            assert!(
                !rhs.contains("model"),
                "model= must not leak into rhs: {rhs:?}"
            );
            assert!(
                rhs.contains("sf=1.2"),
                "sf= is unaffected (still opaque, WO-80 scope is model= only): {rhs:?}"
            );
        }
        other => panic!("expected general Comparison, got {other:?}"),
    }
}

/// A claim line with no `model=` attribute lowers with
/// `model_pin: None` (the un-pinned baseline).
#[test]
fn no_model_attr_lowers_with_no_model_pin() {
    let src = "part gear:\n    \
                   require Life:\n        \
                   bearings: mech.l10_life([b]) >= design_life\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    assert_eq!(obl[0].claim.model_pin, None);
}

#[test]
fn leading_comparator_claims_keep_the_existing_opaque_path() {
    // A `subject: >= 200` line has no lhs expression; the existing
    // op="require" path (whose comparator the orchestrator
    // recovers) must stay byte-identical.
    let src = "part p:\n    require Strength:\n        yield: >= 200\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1);
    match &obl[0].claim.form {
        super::ClaimForm::Comparison { op, rhs, .. } => {
            assert_eq!(op, "require");
            assert_eq!(rhs, ">= 200");
        }
        other => panic!("expected opaque Comparison, got {other:?}"),
    }
}

#[test]
fn two_top_level_comparators_are_a_compile_diagnostic() {
    let src = "part p:\n    require Bad:\n        chained: a.x < b.y < 10\n";
    let set = obligation_set(src);
    assert!(set.obligations.is_empty());
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::GENERAL_COMPARISON_MULTIPLE_COMPARATORS),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn cost_claim_threads_subject_profile_and_bom_into_given() {
    // WO-54 deliverable 1: `mfg.cost(<subject>, profile=<name>)`
    // threads `cost_subject`/`cost_profile` plus the decl's
    // `parts:` BOM into `given.loads` (the conformance-windows
    // precedent), so the orchestrator reads structured fields.
    let src = "part p:\n    parts:\n        panel: vendor(sqd_qo142m200)\n        \
                   brk: vendor(sqd_qo120)\n    require Cost:\n        \
                   bom: mfg.cost(p, profile=construction) <= 6000\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1, "{obl:?}");
    let loads = &obl[0].given.loads;
    assert!(loads.iter().any(|l| l == "cost_subject: p"), "{loads:?}");
    assert!(
        loads.iter().any(|l| l == "cost_profile: construction"),
        "{loads:?}"
    );
    assert!(
        loads
            .iter()
            .any(|l| l == "cost_bom.panel: vendor(sqd_qo142m200)"),
        "{loads:?}"
    );
    assert!(
        loads.iter().any(|l| l == "cost_bom.brk: vendor(sqd_qo120)"),
        "{loads:?}"
    );
}

#[test]
fn cost_claim_without_profile_threads_subject_only() {
    // The `profile=` argument is optional (the manifest default
    // profile applies, toolchain/27 sec. 1.2): no `cost_profile`
    // line is invented for its absence.
    let src = "part p:\n    require Cost:\n        bom: mfg.cost(p) <= 100\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1, "{obl:?}");
    let loads = &obl[0].given.loads;
    assert!(loads.iter().any(|l| l == "cost_subject: p"), "{loads:?}");
    assert!(
        !loads.iter().any(|l| l.starts_with("cost_profile:")),
        "{loads:?}"
    );
}

#[test]
fn malformed_cost_claim_arguments_are_a_compile_diagnostic() {
    // E0438 (WO-54): an unknown keyword argument is rejected at
    // compile time naming the offender, never silently deferred.
    let src = "part p:\n    require Cost:\n        \
                   bom: mfg.cost(p, quantity=5) <= 100\n";
    let set = obligation_set(src);
    assert!(set.obligations.is_empty(), "{:?}", set.obligations);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::COST_CLAIM_MALFORMED),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn top_level_cost_claim_lowers_with_threaded_given() {
    // WO-54: a cost claim in a TOP-LEVEL require group (the
    // calcite program.calx shape) lowers through the dedicated
    // pass -- the frame/fluid passes skip non-frame/non-fluids
    // predicates, so without it the claim would silently vanish.
    let src = "require Budgeting:\n    \
                   construction: mfg.cost(all, profile=construction) <= 850000\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1, "{obl:?}");
    let loads = &obl[0].given.loads;
    assert!(loads.iter().any(|l| l == "cost_subject: all"), "{loads:?}");
    assert!(
        loads.iter().any(|l| l == "cost_profile: construction"),
        "{loads:?}"
    );
}

#[test]
fn top_level_malformed_cost_claim_is_a_compile_diagnostic() {
    let src = "require Budgeting:\n    bad: mfg.cost(all, extra=1) <= 10\n";
    let set = obligation_set(src);
    assert!(set.obligations.is_empty(), "{:?}", set.obligations);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::COST_CLAIM_MALFORMED),
        "{:?}",
        set.diagnostics
    );
}

#[test]
fn forall_sweep_block_nested_named_claim_emits_an_obligation() {
    // WO-68: the emission bug's minimal repro -- a `forall <var> in
    // <domain>:` BLOCK (header on its own line, no inline
    // predicate) whose nested body is a NAMED claim
    // (`strength: ...`). Before the fix, this named claim was
    // swallowed whole into an `OpaqueIsland` by the parser and
    // never reached this pass at all (zero obligations from it,
    // silently). `demo` mirrors the decl-level (hematite/cuprite)
    // `RequireClaim` shape `push_require_obligations` lowers.
    let src = "part p:\n    require Strength:\n        \
                   forall combo in std.pack.family:\n            \
                   strength: p.stress(under=combo) <= 100MPa\n        \
                   plain: p.mass <= 5kg\n";
    let obl = obligations(src);
    let strength = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("strength"))
        .unwrap_or_else(|| panic!("no `strength` obligation among {obl:?}"));
    let sweep = strength.sweep.as_ref().expect("sweep domain present");
    assert_eq!(sweep.axis, "combo");
    assert_eq!(sweep.domain, "std.pack.family");
    // The sibling DIRECT claim (not nested in any sweep) still
    // lowers exactly as before -- the fix only ADDS reachability
    // for the nested form, it does not change direct-claim lowering.
    assert!(
        obl.iter().any(|o| o.claim.name.as_deref() == Some("plain")),
        "{obl:?}"
    );
}

#[test]
fn multiline_bracketed_claim_captures_the_whole_predicate() {
    // WO-90 deliverable 1: a claim whose call expression wraps onto a
    // second physical line INSIDE the open paren must capture whole
    // -- before the layout fix the arg list truncated at the interior
    // newline and the trailing comparator (`< 25mm`) was lost, so the
    // claim mis-lowered to the opaque `require` form with a truncated
    // RHS. Now the comparator is visible and the claim lowers to a
    // real `<` comparison.
    let src = "part p:\n    require Structural:\n        \
                   tip: mech.deflection(cut.blank,\n                      \
                   under=envelope(Mount)) < 25mm\n";
    let obl = obligations(src);
    let tip = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("tip"))
        .unwrap_or_else(|| panic!("no `tip` obligation among {obl:?}"));
    match &tip.claim.form {
        super::ClaimForm::Comparison { lhs, op, rhs } => {
            assert_eq!(op, "<", "the wrapped comparator must survive: {tip:?}");
            assert!(
                lhs.contains("under=envelope(Mount)"),
                "the continuation line must be captured in the LHS: {lhs:?}"
            );
            assert_eq!(
                rhs, "0.025m",
                "25mm resolved to metres on the RHS, unit preserved (D256): {rhs:?}"
            );
        }
        other => panic!("expected a `<` comparison, got {other:?}"),
    }
}

#[test]
fn bare_plural_forall_domain_is_e0450() {
    // WO-90 deliverable 2: a `forall <var> in boards:` sweep whose
    // domain is a BARE PLURAL naming no declared domain covers zero
    // points -- a vacuous pass. It must trip the constructive E0450
    // diagnostic, once for the block.
    let src = "part p:\n    require Boards:\n        \
                   forall b in boards:\n            \
                   ok: b.stress <= 100MPa\n";
    let set = obligation_set(src);
    let hits: Vec<_> = set
        .diagnostics
        .iter()
        .filter(|d| d.code == regolith_diag::codes::FORALL_DOMAIN_UNDECLARED)
        .collect();
    assert_eq!(
        hits.len(),
        1,
        "exactly one E0450 per block: {:?}",
        set.diagnostics
    );
    assert!(
        hits[0].message.contains("boards"),
        "message names the undeclared domain: {}",
        hits[0].message
    );
}

// frob:tests crates/regolith-lower/src/claims/require.rs::is_undeclared_bare_plural_domain kind="unit"
#[test]
fn declared_forall_domains_are_not_e0450() {
    // WO-90 deliverable 2 / acceptance: every DECLARED domain form
    // stays legal -- a discrete set, an interval, a dotted pack ref,
    // a `registry(...)` family, and a `.members.all` collection must
    // NOT trip E0450 (WO-68's forms stay green).
    for domain in [
        "{trail, race}",
        "[0rpm, 6000rpm]",
        "std.pack.family",
        "registry(std.civil.aisc.strength)",
        "Bridge.members.all",
    ] {
        assert!(
            !super::require::is_undeclared_bare_plural_domain(domain),
            "declared domain wrongly flagged: {domain}"
        );
    }
    // And the trap forms ARE flagged.
    assert!(super::require::is_undeclared_bare_plural_domain("boards"));
    assert!(super::require::is_undeclared_bare_plural_domain(
        "assemblies"
    ));
}

#[test]
fn explicitly_empty_declared_domain_is_not_e0450() {
    // WO-90 deliverable 2: an explicitly EMPTY declared domain (an
    // empty discrete set) is a legal, honest zero-obligation sweep,
    // NOT the bare-plural trap.
    assert!(!super::require::is_undeclared_bare_plural_domain("{}"));
    assert!(!super::require::is_undeclared_bare_plural_domain("[]"));
    // A missing/blank domain (malformed header, parser-degraded) is
    // also not this diagnostic's concern.
    assert!(!super::require::is_undeclared_bare_plural_domain(""));
}

#[test]
fn forall_sweep_block_over_calcite_frame_claims_flips_the_live_repro() {
    // WO-68 acceptance: the exact live repro named in the WO/D181
    // (footbridge `compiler.check` emitting 4 obligations, zero
    // `strength`) -- reusing `frame_lower`'s own `FOOTBRIDGE_SRC`
    // shape inline (this module has no access to that private
    // const) so a regression here is caught at the obligation
    // layer, not just the frame-payload layer.
    let src = "import std.civil (Pinned, Bearing)\n\
site Greenway:\n\
\x20   boundary:\n\
\x20       wind_speed: [0m/s, 43m/s] by catalog(asce7_fig26)\n\
grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: free\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   forall combo in std.civil.aisc.strength:\n\
\x20       strength: civil.utilization(Bridge.members.all, under=combo) <= 1.0\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";
    let obl = calx_obligations(src);
    // WO-85/D194 ruling 3: the `.members.all` group subject expands
    // per member at lowering -- the one-member footbridge repro's
    // `strength` claim now lands as `strength[G1]` with the member
    // pinned in the predicate subject.
    assert!(
        obl.iter()
            .any(|o| o.claim.name.as_deref() == Some("strength[G1]")),
        "strength[G1] obligation missing: {obl:?}"
    );
    let strength = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("strength[G1]"))
        .unwrap();
    let sweep = strength.sweep.as_ref().expect("sweep domain present");
    assert_eq!(sweep.axis, "combo");
    assert_eq!(sweep.domain, "std.civil.aisc.strength");
    match &strength.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert!(rhs.contains("Bridge.members.G1"), "{rhs}");
            assert!(!rhs.contains(".members.all"), "{rhs}");
        }
        other => panic!("unexpected claim form {other:?}"),
    }
    assert!(
        obl.iter()
            .any(|o| o.claim.name.as_deref() == Some("bearing")),
        "{obl:?}"
    );
}

#[test]
fn members_all_group_expands_one_obligation_per_member() {
    // WO-85/D194 ruling 3: a mixed-role group subject (beam + slab)
    // yields one obligation per member, each pinned by name and
    // predicate, sharing the sweep and the frame payload ref --
    // so one indeterminate member can no longer defer the group
    // wholesale downstream.
    let src = "grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
member Deck: slab\n\
\x20   section: registry(comp_deck_140mm)\n\
\x20   material: registry(concrete_c30)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1, Deck\n\
\x20   transfers:\n\
\x20       d_g1: Bearing(tributary=10.8m2) (Deck -> G1)\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   pedestrian: 4.1kPa on [Deck] by catalog(aashto_ped)\n\
require Structure:\n\
\x20   forall combo in std.civil.aisc.strength:\n\
\x20       strength: civil.utilization(Bridge.members.all, under=combo) <= 1.0\n";
    let obl = calx_obligations(src);
    let strength: Vec<_> = obl
        .iter()
        .filter(|o| {
            o.claim
                .name
                .as_deref()
                .is_some_and(|n| n.starts_with("strength["))
        })
        .collect();
    assert_eq!(strength.len(), 2, "{obl:?}");
    let names: Vec<_> = strength
        .iter()
        .filter_map(|o| o.claim.name.as_deref())
        .collect();
    assert!(names.contains(&"strength[G1]"), "{names:?}");
    assert!(names.contains(&"strength[Deck]"), "{names:?}");
    // Every instance keeps the sweep and the frame payload ref, and
    // the two instances hash distinctly (INV-1).
    for o in &strength {
        assert!(o.sweep.is_some());
        assert!(o.payloads.iter().any(|p| p.kind == "frame"));
    }
    assert_ne!(strength[0].content_hash(), strength[1].content_hash());
}

#[test]
fn embedment_claim_lowers_with_site_bound_resolved() {
    // WO-85/D194 ruling 4: `civil.embedment(P1) >= site.frost_depth`
    // lowers as a frame obligation with the site datum's declared
    // quantity substituted into the bound (leaf-name match against
    // the project's `site` decls; `frost_depth` nests under
    // `boundary:` in the corpus spelling).
    let src = "import std.civil (EmbeddedPost)\n\
site Township:\n\
\x20   boundary:\n\
\x20       frost_depth: 1.2m by catalog(county_gis)\n\
grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
    let obl = calx_obligations(src);
    let frost = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("frost"))
        .unwrap_or_else(|| panic!("no frost obligation among {obl:?}"));
    assert!(frost.payloads.iter().any(|p| p.kind == "frame"));
    match &frost.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert!(
                rhs.contains(">= 1.2") && !rhs.contains("site.frost_depth"),
                "{rhs}"
            );
        }
        other => panic!("unexpected claim form {other:?}"),
    }
}

#[test]
fn embedment_site_bound_prefers_the_claims_own_file() {
    // WO-85: a multi-design directory (examples/tracks/calcite)
    // declares one site per design file with COLLIDING leaf names
    // (three different `frost_depth`s) -- the claim's own file's
    // datum wins; the project-wide index is only the fallback for
    // the site.calx/frame.calx split.
    let barn = "site Township:\n\
\x20   boundary:\n\
\x20       frost_depth: 1.2m by catalog(county_gis)\n\
grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
    let other = "site Elsewhere:\n\
\x20   boundary:\n\
\x20       frost_depth: 0.9m by catalog(county_gis)\n";
    let files: Vec<ParsedFile> = [("barn.calx", barn), ("other.calx", other)]
        .into_iter()
        .map(|(path, src)| {
            let path = Utf8PathBuf::from(path);
            ParsedFile {
                path: path.clone(),
                parse: regolith_syntax::parse(src, &path),
            }
        })
        .collect();
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    let obl = build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
    let frost = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("frost"))
        .unwrap_or_else(|| panic!("no frost obligation among {obl:?}"));
    match &frost.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert!(rhs.contains(">= 1.2"), "own file's 1.2m must win: {rhs}");
        }
        other => panic!("unexpected claim form {other:?}"),
    }
}

#[test]
fn embedment_unknown_site_datum_stays_symbolic() {
    // An unresolvable site path is left verbatim (the claim defers
    // downstream with an honest unresolved bound), never guessed.
    let src = "grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
    let obl = calx_obligations(src);
    let frost = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("frost"))
        .unwrap();
    match &frost.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert!(rhs.contains("site.frost_depth"), "{rhs}");
        }
        other => panic!("unexpected claim form {other:?}"),
    }
}

#[test]
fn bearing_claim_lowers_with_interval_site_bound_resolved() {
    // WO-96 bearing close-out: `civil.bearing_pressure(F) <=
    // site.soil.bearing` literalizes the interval capacity datum to
    // its CONSERVATIVE (lower) endpoint for a `<=` allowable, and the
    // BasePlate `bearing=` area threads onto the transfer's tributary
    // field. A `ShopFloor.`-prefixed (site-name) path resolves the
    // same way as a `site.`-prefixed one.
    let src = "import std.civil (Moment, BasePlate)\n\
site ShopFloor:\n\
\x20   soil:\n\
\x20       bearing: [100kPa, 150kPa] by test(slab_typ)\n\
grid legs: L spacing 0.7m\n\
level base: 0m\n\
level head: 1.4m\n\
member Col_L: column\n\
\x20   section: registry(hss127x127x8)\n\
\x20   material: registry(astm_a500c)\n\
\x20   from (L, base) to (L, head)\n\
structure Frame:\n\
\x20   support: F_L: footing\n\
\x20   members: Col_L\n\
\x20   transfers:\n\
\x20       col_l_f: BasePlate(anchors=registry(a), bearing=1.0m2) (Col_L -> F_L)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing_l: civil.bearing_pressure(F_L) <= ShopFloor.soil.bearing\n";
    let obl = calx_obligations(src);
    let bearing = obl
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("bearing_l"))
        .unwrap_or_else(|| panic!("no bearing_l obligation among {obl:?}"));
    assert!(bearing.payloads.iter().any(|p| p.kind == "frame"));
    match &bearing.claim.form {
        super::ClaimForm::Comparison { rhs, .. } => {
            assert!(
                rhs.contains("100000") && !rhs.contains("soil.bearing"),
                "conservative lo endpoint (100kPa) substituted, not the \
                     symbolic bound: {rhs}"
            );
            assert!(
                !rhs.contains("150000"),
                "the hi endpoint (150kPa) is NOT used for a <= allowable: {rhs}"
            );
        }
        other => panic!("unexpected claim form {other:?}"),
    }
}

#[test]
fn cost_claim_forall_profile_prefix_carries_a_discrete_sweep() {
    // D95/D105a: `forall profile in {a, b}:` is ONE obligation
    // whose `sweep` carries the discrete profile domain -- the
    // per-profile axis points are the orchestrator/estimator's
    // to expand (toolchain/27 sec. 1.1).
    let src = "part p:\n    require Cost:\n        \
                   sweep: forall profile in {prototype, construction}: \
                   mfg.cost(p) <= 100\n";
    let obl = obligations(src);
    assert_eq!(obl.len(), 1, "{obl:?}");
    let sweep = obl[0].sweep.as_ref().expect("sweep domain present");
    assert_eq!(sweep.axis, "profile");
    assert_eq!(sweep.domain, "{prototype, construction}");
    assert!(
        obl[0].given.loads.iter().any(|l| l == "cost_subject: p"),
        "{:?}",
        obl[0].given.loads
    );
}

#[test]
fn link_budget_refs_resolve_through_the_parsed_declarations() {
    // D103 end-to-end (Rust half): a Kestrel-shaped general
    // comparison resolves every two-segment entity-field reference
    // into given.refs -- a promise bound (`pa_out`), plain values
    // (`path_loss`/`sensitivity`), and a bound field (`gain`).
    let src = "part Radio:\n    require Rf:\n        pa_out: elec.power(rf_conn) >= 30dBm during op = downlink\n\
                   part Dish:\n    gain: >= 12dBi\n\
                   part Station:\n    sensitivity: -110dBm\n    path_loss: 140dB\n\
                   system Sat:\n    parts:\n        comms: Radio\n        ant: Dish\n        gs: Station\n    require Link:\n        margin: comms.pa_out + ant.gain - gs.path_loss >= gs.sensitivity + 6dB during op = downlink\n";
    let obls = obligations(src);
    let margin = obls
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("margin"))
        .expect("margin obligation");
    let refs: std::collections::BTreeMap<_, _> = margin.given.refs.iter().cloned().collect();
    assert_eq!(refs.get("comms.pa_out").map(String::as_str), Some("30dBm"));
    assert_eq!(refs.get("ant.gain").map(String::as_str), Some("12dBi"));
    assert_eq!(refs.get("gs.path_loss").map(String::as_str), Some("140dB"));
    assert_eq!(
        refs.get("gs.sensitivity").map(String::as_str),
        Some("-110dBm")
    );
    match &margin.claim.form {
        super::ClaimForm::Comparison { op, .. } => assert_eq!(op, ">="),
        other => panic!("expected general Comparison, got {other:?}"),
    }
}

/// Obligations lowered from TWO files together (a calcite `.calx`
/// paired with a cuprite `.cupr`) -- WO-136's own shape: an
/// entity-field reference crossing the domain boundary needs both
/// files parsed into the SAME `ObligationSet` pass, unlike every other
/// helper above (single file, single language).
fn xdomain_obligations(calx_src: &str, cupr_src: &str) -> Vec<super::Obligation> {
    let calx_path = Utf8PathBuf::from("t.calx");
    let cupr_path = Utf8PathBuf::from("t.cupr");
    let files = vec![
        ParsedFile {
            path: calx_path.clone(),
            parse: regolith_syntax::parse(calx_src, &calx_path),
        },
        ParsedFile {
            path: cupr_path.clone(),
            parse: regolith_syntax::parse(cupr_src, &cupr_path),
        },
    ];
    let snaps = build_entities(&files);
    let checks = run_checks(&files, &snaps);
    let graph = build_contract_ir(&files, &snaps);
    let realized_inputs = crate::realized_input::RealizedInputs::new();
    build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
}

#[test]
fn working_clearance_ref_resolves_across_the_calcite_cuprite_boundary() {
    // WO-136 (D249/AD-42): `resolve_entity_ref`'s calcite fallback
    // (`find_calcite_space_syntax`) -- a `space`'s declared field is
    // NOT a `Decl` (calcite.rs reads spaces through their own
    // `file.spaces()` accessor), so without the fallback this
    // cross-domain reference could never resolve at all. This is the
    // Rust-half proof; the Python-half end-to-end proof (real
    // discharge) lives in `tests/orchestrator/test_orchestrator.py`'s
    // `test_working_clearance_discharges_end_to_end_via_build`.
    let calx_src = "space ElectricalRoom:\n    area: 12m2\n    depth: 3.0m\n";
    let cupr_src = "part MainXfmr:\n    footprint_depth: 1.2m\n\
                     system SubstationRoom:\n    parts:\n        xfmr: MainXfmr\n\
                     \x20   require Siting:\n        front: elec.power.working_clearance(xfmr) \
                     >= ElectricalRoom.depth - xfmr.footprint_depth - 1.0m\n";
    let obls = xdomain_obligations(calx_src, cupr_src);
    let front = obls
        .iter()
        .find(|o| o.claim.name.as_deref() == Some("front"))
        .unwrap_or_else(|| panic!("no front obligation among {obls:?}"));
    let refs: std::collections::BTreeMap<_, _> = front.given.refs.iter().cloned().collect();
    assert_eq!(
        refs.get("ElectricalRoom.depth").map(String::as_str),
        Some("3.0m"),
        "the calcite space's field must resolve through the fallback: {refs:?}"
    );
    assert_eq!(
        refs.get("xfmr.footprint_depth").map(String::as_str),
        Some("1.2m")
    );
}

#[test]
fn an_unresolvable_ref_is_skipped_never_invented() {
    // The REAL Kestrel posture: `antenna.gain` names nothing the
    // source declares; the ref simply does not enter given.refs
    // (the orchestrator defers naming it).
    let src =
        "system Sat:\n    require Link:\n        margin: comms.pa_out + antenna.gain >= 6dB\n";
    let obls = obligations(src);
    let margin = &obls[0];
    assert!(
        margin.given.refs.is_empty(),
        "nothing resolvable -> no refs: {:?}",
        margin.given.refs
    );
}

// -- WO-69: plan: linkage lowering -----------------------------------

const PLAN_SRC: &str = "part p:\n    plan: extern(\"op10.nc\", gcode_fanuc) machine=std.machines.haas_vf2, tooling=std.tooling.endmill_6mm, resolution=0.05mm\n";

#[test]
fn plan_field_emits_exactly_five_cam_obligations_keyed_distinctly() {
    let set = plan_obligation_set(PLAN_SRC, None);
    assert!(set.diagnostics.is_empty(), "diags: {:?}", set.diagnostics);
    let kinds: Vec<&str> = set
        .obligations
        .iter()
        .map(|o| o.claim.name.as_deref().unwrap_or(""))
        .collect();
    assert_eq!(
        kinds,
        vec![
            "cam.parse",
            "cam.envelope",
            "cam.collision_coarse",
            "cam.removal",
            "cam.coverage",
        ],
        "exactly five, keyed by their cam.* claim kind, in source order"
    );
    let hashes: std::collections::BTreeSet<String> = set
        .obligations
        .iter()
        .map(super::Obligation::content_hash)
        .collect();
    assert_eq!(hashes.len(), 5, "INV-1: all five key distinctly");
}

#[test]
fn plan_obligations_carry_plan_ref_dialect_and_kwargs_in_given() {
    let set = plan_obligation_set(PLAN_SRC, None);
    let parse = &set.obligations[0];
    assert!(parse.given.loads.contains(&"plan_ref: op10.nc".to_string()));
    assert!(parse
        .given
        .loads
        .contains(&"plan_dialect: gcode_fanuc".to_string()));
    assert!(parse
        .given
        .loads
        .contains(&"cam_machine_ref: std.machines.haas_vf2".to_string()));
    assert!(parse
        .given
        .loads
        .contains(&"cam_tooling_ref: std.tooling.endmill_6mm".to_string()));
    assert!(parse
        .given
        .loads
        .contains(&"resolution_mm: 0.05mm".to_string()));
    assert!(parse
        .payloads
        .iter()
        .any(|p| p.kind == "plan" && p.origin == "op10.nc"));
}

const HDL_EXTERN_SRC: &str = "block PcIncrement:\n    ports:\n        pc_in: digital(in, width=64)\n        pc_next: digital(out, width=64)\nimpl PcIncrement by extern(\"pc_incr.v\", verilog2001) as rtl\n";

#[test]
fn hdl_extern_edge_emits_one_hdl_build_obligation_carrying_ref_and_regime() {
    // WO-89: an `impl ... by extern("ref", <hdl dialect>)` edge forms
    // its ordinary INV-13 conformance obligation PLUS one hdl.build
    // obligation routed (orchestrator-side) to the std.hdl pack.
    let set = plan_obligation_set(HDL_EXTERN_SRC, None);
    let hdl: Vec<&super::Obligation> = set
        .obligations
        .iter()
        .filter(|o| o.claim.name.as_deref() == Some("hdl.build"))
        .collect();
    assert_eq!(hdl.len(), 1, "exactly one hdl.build obligation");
    let loads = &hdl[0].given.loads;
    assert!(
        loads.contains(&"hdl_src_ref: pc_incr.v".to_string()),
        "{loads:?}"
    );
    assert!(
        loads.contains(&"hdl_regime: verilog2001".to_string()),
        "{loads:?}"
    );
    // The conformance obligation is still emitted (unchanged).
    assert!(set
        .obligations
        .iter()
        .any(|o| o.claim.name.as_deref() == Some("extern:PcIncrement")));
}

#[test]
fn non_hdl_extern_dialect_emits_no_hdl_obligation() {
    // A bare extern with no dialect, or a non-HDL format, forms NO
    // hdl.* obligation -- honest silence (KNOWN_HDL_REGIMES gate).
    let src = "block B:\n    ports:\n        x: digital(in)\nimpl B by extern(\"b.blob\", zipfile) as r\n";
    let set = plan_obligation_set(src, None);
    assert!(
        !set.obligations
            .iter()
            .any(|o| o.claim.name.as_deref() == Some("hdl.build")),
        "a non-HDL dialect must not form an hdl.build obligation"
    );
}

#[test]
fn plan_obligations_gain_a_geometry_realized_payload_when_target_supplied() {
    let with_target = plan_obligation_set(PLAN_SRC, Some("p"));
    for o in &with_target.obligations {
        assert!(
            o.payloads.iter().any(|p| p.kind == "geometry.realized"
                && p.origin == "p"
                && p.digest == "blake3:plantarget"),
            "obligation {:?} missing its target geometry ref",
            o.claim.name
        );
    }
    let without_target = plan_obligation_set(PLAN_SRC, None);
    for o in &without_target.obligations {
        assert!(
            !o.payloads.iter().any(|p| p.kind == "geometry.realized"),
            "no realized input supplied for this build -> no fabricated digest"
        );
    }
}

#[test]
fn removing_the_plan_field_removes_all_five_obligations() {
    let with_plan = obligations(PLAN_SRC);
    assert_eq!(with_plan.len(), 5);
    let without_plan = obligations("part p:\n    material: AISI_304\n");
    assert!(
        without_plan.is_empty(),
        "a plain part with no plan: field emits no cam.* obligations: {without_plan:?}"
    );
}

#[test]
fn plan_clause_missing_ref_is_e0449_and_emits_no_obligations() {
    let src = "part p:\n    plan: extern(gcode_fanuc)\n";
    let set = plan_obligation_set(src, None);
    assert!(set.obligations.is_empty());
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::PLAN_CLAUSE_MALFORMED),
        "diags: {:?}",
        set.diagnostics
    );
}

#[test]
fn plan_clause_unknown_dialect_is_e0449_and_emits_no_obligations() {
    let src = "part p:\n    plan: extern(\"op10.nc\", not_a_dialect)\n";
    let set = plan_obligation_set(src, None);
    assert!(set.obligations.is_empty());
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::PLAN_CLAUSE_MALFORMED),
        "diags: {:?}",
        set.diagnostics
    );
}

// ---- WO-78: `elec.impedance(...) within [lo, hi]` lowering ----

#[test]
fn impedance_window_splits_preserving_call_text() {
    let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(clk, role=microstrip, \
                   stackup=jlc04161h_7628, layer=outer, w=0.28mm) \
                   within [45ohm, 55ohm]\n";
    let obs = obligations(src);
    assert_eq!(obs.len(), 2, "obligations: {obs:?}");
    let (lo, hi) = (&obs[0], &obs[1]);
    assert_eq!(lo.claim.name.as_deref(), Some("clk_z0.lo"));
    assert_eq!(hi.claim.name.as_deref(), Some("clk_z0.hi"));
    for (ob, op, rhs) in [(lo, ">=", "45ohm"), (hi, "<=", "55ohm")] {
        let super::ClaimForm::Comparison {
            lhs,
            op: got_op,
            rhs: got_rhs,
        } = &ob.claim.form
        else {
            panic!("expected Comparison, got {:?}", ob.claim.form);
        };
        assert!(
            lhs.starts_with("elec.impedance(clk"),
            "lhs must preserve the call: {lhs}"
        );
        // The kwarg's unit suffix resolves like every other bound
        // (`0.28mm` -> `0.00028m`) and the unit token is preserved
        // (D256, the mainboard_mx `refclk_z0.lo` exemplar).
        assert!(lhs.contains("w=0.00028m"), "lhs: {lhs}");
        assert_eq!(got_op, op);
        assert_eq!(got_rhs, rhs);
    }
}

#[test]
fn impedance_window_with_no_net_is_e0452_and_emits_no_obligations() {
    let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(role=microstrip) within [45ohm, 55ohm]\n";
    let set = plan_obligation_set(src, None);
    assert!(set.obligations.is_empty(), "{:?}", set.obligations);
    assert!(
        set.diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::SI_IMPEDANCE_MALFORMED),
        "diags: {:?}",
        set.diagnostics
    );
}

#[test]
fn impedance_with_plain_comparator_falls_through_to_general_comparison() {
    let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(clk, role=microstrip, w=0.28mm) <= 60ohm\n";
    let obs = obligations(src);
    assert_eq!(obs.len(), 1, "obligations: {obs:?}");
    let super::ClaimForm::Comparison { lhs, op, .. } = &obs[0].claim.form else {
        panic!("expected Comparison, got {:?}", obs[0].claim.form);
    };
    assert!(lhs.starts_with("elec.impedance(clk"), "lhs: {lhs}");
    assert_eq!(op, "<=");
}

// T-0065 (F-WO137-2): a bare `require <Group>:` claim group nested
// directly in a `power <name>:` net's body must attach obligations
// exactly like one nested in a `system`/`part`/`board` decl -- the
// pre-fix repro (`regolith check`) reported obligations=0 for this
// exact shape.
#[test]
fn power_net_nested_require_group_attaches_obligations() {
    let src = "power PlantMain:\n\
               \x20   sources: Svc\n\
               \x20   require Checks:\n\
               \x20       v: >= 1\n";
    let obs = obligations(src);
    assert_eq!(obs.len(), 1, "obligations: {obs:?}");
    let super::ClaimForm::Comparison { lhs, op, rhs } = &obs[0].claim.form else {
        panic!("expected Comparison, got {:?}", obs[0].claim.form);
    };
    // "v: >= 1" is the pre-existing OPAQUE require-line shape (no
    // explicit lhs quantity expression before the comparator -- see
    // `non_fluid_source_produces_no_fluid_obligation_noise`'s identical
    // "strength: >= 1" form): `push_opaque_require_obligation` stamps
    // `op="require"` and folds the comparator+bound into `rhs` whole.
    // The point under test is that an obligation exists AT ALL for a
    // `power` net's own nested claim group (obligations=0 pre-fix),
    // not this particular predicate's internal shape.
    assert_eq!(lhs, "v");
    assert_eq!(op, "require");
    assert_eq!(rhs, ">= 1");
}

// T-0065 (F-WO137-2): a bare TOP-LEVEL `require <Group>:` claim group
// immediately following a `power <name>:` net (a dedented sibling
// statement, not nested in the net's body) also attached zero
// obligations pre-fix -- this one lowers through the top-level
// `File::fluid_requires` calcite-frame path (`push_calcite_frame_
// obligations`), which recognizes FRAME_CLAIM_FORMS predicates; a
// bare general-comparison predicate at true top level (no enclosing
// decl OR power net) is out of scope for T-0065 (its own finding
// text names ONLY the two `power`-adjacent shapes: nested and
// sibling-immediately-after) and stays a named non-goal here. This
// test instead proves the net's OWN nested claim group (the shape
// `power.cupr`'s `system PlantChecks:` workaround exists to route
// around) now attaches, which is T-0065's acceptance criterion.
#[test]
fn power_net_claims_do_not_leak_into_a_later_sibling_decls_obligations() {
    let src = "power PlantMain:\n\
               \x20   sources: Svc\n\
               \x20   require Checks:\n\
               \x20       v: >= 1\n\
               part P:\n\
               \x20   require Other:\n\
               \x20       w: >= 2\n";
    let obs = obligations(src);
    assert_eq!(obs.len(), 2, "obligations: {obs:?}");
    let names: Vec<_> = obs
        .iter()
        .map(|o| match &o.claim.form {
            super::ClaimForm::Comparison { lhs, .. } => lhs.as_str(),
            _ => "?",
        })
        .collect();
    assert!(names.contains(&"v"));
    assert!(names.contains(&"w"));
}
