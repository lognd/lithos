use super::{
    elaborate_frames, full_predicate_text, resolve_unit_suffix, sweep_domain_from_ast, AstNode,
    BTreeMap, Claim, ClaimForm, Field, File, Given, Obligation, ParsedFile, PayloadRef,
    SweepDomain, SyntaxKind,
};

/// The 03-lowering sec. 5 claim forms that carry a `frame` [`PayloadRef`]
/// (WO-48 deliverable 4, exactly the table rows this slice covers --
/// `civil.travel_distance`/`exit_capacity`/`dead_end` are discharged
/// statically at L2 with no frame involved, and code-pack `rule`
/// demands are the WO-28 engine's own obligation shape; neither belongs
/// here).
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const FRAME_CLAIM_FORMS: [&str; 6] = [
    "civil.utilization(",
    "mech.deflection(",
    "civil.story_drift(",
    "civil.bearing_pressure(",
    "mech.first_mode(",
    // WO-85/D194: declared embedment depth vs required (the
    // `civil.bearing_pressure` reaction-based closed-form pattern).
    "civil.embedment(",
];

/// Elaborate every file's structure(s) into a [`FramePayload`] and
/// lower each frame-referencing require claim (calcite/03 sec. 5) into
/// an obligation carrying a `kind: frame` [`PayloadRef`]. One structure
/// per file in v1 (mirrors `push_fluid_obligations`'s "one flownet per
/// file" simplification -- every calcite corpus design declares exactly
/// one `structure`), so a file's frame-referencing require lines
/// resolve to its own structure's frame. Returns every elaborated frame
/// (WO-48 deliverable 3: `LowerOutput.frames`/`BuildPayload.frames`
/// emission reads this instead of calling `elaborate_frames` a second
/// time, AD-22's one-producer rule applied within a single crate).
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_calcite_frame_obligations(
    out: &mut Vec<Obligation>,
    files: &[ParsedFile],
) -> Vec<crate::frame_lower::ElaboratedFrame> {
    let report = elaborate_frames(files);
    let mut frames_by_name: BTreeMap<&str, &regolith_oblig::FramePayload> = BTreeMap::new();
    for frame in &report.frames {
        frames_by_name.insert(frame.name.as_str(), &frame.payload);
    }

    // WO-85/D194: the `civil.embedment` bound resolver's site-datum
    // index, built once across the WHOLE project's files (`site` decls
    // typically live in `site.calx`, the claims in `frame.calx` -- the
    // same cross-file relationship `frame_lower`'s grid/level
    // aggregation already honors).
    let all_files: Vec<File> = files
        .iter()
        .filter_map(|pf| File::cast(pf.parse.syntax()))
        .collect();
    let site_index = site_quantities(&all_files);
    // WO-96 bearing close-out: the parallel interval-datum index (the
    // `civil.bearing_pressure` bound resolver's `site.soil.bearing`
    // capacity ranges), built over the same whole-project file set.
    let site_interval_index = site_interval_quantities(&all_files);

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        // v1: at most one structure per file (see the doc comment
        // above); a file with none has no subject for its frame claims.
        let Some(structure_name) = file.structures().into_iter().next().and_then(|s| s.name())
        else {
            continue;
        };
        let Some(payload) = frames_by_name.get(structure_name.as_str()) else {
            continue;
        };
        // Site-datum resolution scope: the claim's OWN file wins (a
        // multi-design directory -- examples/tracks/calcite -- carries
        // one site per design file, and pole_barn's `frost_depth` must
        // never collide with bus_shelter's); the project-wide index is
        // the fallback for the ordinary `site.calx` + `frame.calx`
        // split, where the claim's file declares no site of its own.
        let local_index = site_quantities(std::slice::from_ref(&file));
        let mut effective_index = site_index.clone();
        effective_index.extend(local_index);
        let local_intervals = site_interval_quantities(std::slice::from_ref(&file));
        let mut effective_intervals = site_interval_index.clone();
        effective_intervals.extend(local_intervals);

        for req in file.fluid_requires() {
            // WO-68: `all_claims()` reaches claims nested inside a
            // `forall combo in ...:` block (calcite/02 sec. 9's
            // `strength:` sweep is exactly this shape) -- previously
            // invisible here, the live footbridge repro (4 obligations,
            // zero `strength`).
            for (line, sweep) in req.all_claims() {
                let sweep_domain = sweep.as_ref().and_then(sweep_domain_from_ast);
                push_frame_obligation(
                    out,
                    &structure_name,
                    payload,
                    &line,
                    sweep_domain.as_ref(),
                    &effective_index,
                    &effective_intervals,
                );
            }
        }
    }

    report.frames
}

/// Every `site` declaration's point-quantity fields across the
/// project, keyed by LEAF field name (`frost_depth` -> `"1.2m"`) --
/// the `civil.embedment` bound resolver's lookup table (WO-85/D194).
/// A leaf name declared twice with DIFFERENT value text maps to `None`
/// (ambiguous: never guessed, the claim's bound stays symbolic and
/// defers downstream by name); interval-valued fields (`bearing:
/// [120kPa, 170kPa]`) are not point quantities and are simply absent.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn site_quantities(files: &[File]) -> BTreeMap<String, Option<String>> {
    let mut index: BTreeMap<String, Option<String>> = BTreeMap::new();
    for file in files {
        for site in file.sites() {
            for field in site.syntax().descendants().filter_map(Field::cast) {
                let Some(value) = field.value() else {
                    continue;
                };
                if value.kind() != SyntaxKind::QuantityLit {
                    continue;
                }
                let text = value.text().to_string().trim().to_string();
                match index.entry(field.name()) {
                    std::collections::btree_map::Entry::Vacant(v) => {
                        v.insert(Some(text));
                    }
                    std::collections::btree_map::Entry::Occupied(mut o) => {
                        if o.get().as_deref() != Some(text.as_str()) {
                            tracing::info!(
                                field = %field.name(),
                                "site datum declared twice with different values; \
                                 embedment bound resolution marks it ambiguous"
                            );
                            o.insert(None);
                        }
                    }
                }
            }
        }
    }
    index
}

/// Every `site` declaration's INTERVAL-valued fields across the project,
/// keyed by LEAF field name (`bearing` -> `("120kPa", "170kPa")`) -- the
/// `civil.bearing_pressure` bound resolver's lookup table (WO-96 bearing
/// close-out). A `by test`/`by catalog` provenance clause after the
/// bracket is dropped (only the two endpoints matter). A leaf declared
/// twice with DIFFERENT endpoints maps to `None` (ambiguous: never
/// guessed, the claim's bound stays symbolic and defers downstream by
/// name); point-quantity fields are handled by [`site_quantities`].
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn site_interval_quantities(
    files: &[File],
) -> BTreeMap<String, Option<(String, String)>> {
    let mut index: BTreeMap<String, Option<(String, String)>> = BTreeMap::new();
    for file in files {
        for site in file.sites() {
            for field in site.syntax().descendants().filter_map(Field::cast) {
                let Some(value) = field.value() else {
                    continue;
                };
                if value.kind() != SyntaxKind::IntervalExpr {
                    continue;
                }
                let text = value.text().to_string();
                let Some(endpoints) = interval_endpoints(&text) else {
                    continue;
                };
                match index.entry(field.name()) {
                    std::collections::btree_map::Entry::Vacant(v) => {
                        v.insert(Some(endpoints));
                    }
                    std::collections::btree_map::Entry::Occupied(mut o) => {
                        if o.get().as_ref() != Some(&endpoints) {
                            tracing::info!(
                                field = %field.name(),
                                "site interval datum declared twice with different \
                                 endpoints; bearing bound resolution marks it ambiguous"
                            );
                            o.insert(None);
                        }
                    }
                }
            }
        }
    }
    index
}

/// The two endpoint texts of a `[lo, hi]` interval literal (`"[120kPa,
/// 170kPa]"` -> `("120kPa", "170kPa")`), trimmed. `None` when the text
/// is not a two-endpoint bracket (a `{a, b}` discrete set or a malformed
/// literal is not a numeric interval this resolver substitutes).
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn interval_endpoints(text: &str) -> Option<(String, String)> {
    let inner = text.trim().strip_prefix('[')?;
    let close = inner.find(']')?;
    let (lo, hi) = inner[..close].split_once(',')?;
    Some((lo.trim().to_string(), hi.trim().to_string()))
}

/// Resolve a civil predicate's trailing dotted site-datum bound to its
/// declared quantity text, matching by the path's LEAF segment against
/// the project's `site` decls. Two datum shapes:
///
/// - POINT (WO-85/D194, `civil.embedment`): `>= site.frost_depth` ->
///   `>= 1.2m` from [`site_quantities`].
/// - INTERVAL (WO-96 bearing close-out, `civil.bearing_pressure`): `<=
///   site.soil.bearing`/`<= ShopFloor.soil.bearing` -> the CONSERVATIVE
///   endpoint of the tested-capacity interval (`[150kPa, 210kPa]` ->
///   `150kPa` for a `<=` allowable, `210kPa` for a `>=` demand) from
///   [`site_interval_quantities`]. Picking the tightest endpoint by
///   comparator sense keeps the discharged verdict on the safe side of
///   the measured range (never the optimistic end).
///
/// The bound's dotted path may be prefixed either by the literal `site.`
/// (the ordinary `site.calx` split) or by the site's declared NAME
/// (`ShopFloor.soil.bearing`, hydro_press's in-file site) -- the leaf is
/// the stable key either way. Returns the predicate unchanged when the
/// bound is not a dotted reference or the leaf is unknown/ambiguous --
/// the claim then defers downstream with its symbolic bound intact
/// (honest, never guessed).
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn resolve_embedment_site_bound(
    predicate: &str,
    site_index: &BTreeMap<String, Option<String>>,
    site_intervals: &BTreeMap<String, Option<(String, String)>>,
) -> String {
    let Some(cmp_idx) = predicate.find(">=").or_else(|| predicate.find("<=")) else {
        return predicate.to_string();
    };
    let op = &predicate[cmp_idx..cmp_idx + 2];
    let head = &predicate[..cmp_idx + 2];
    let bound = predicate[cmp_idx + 2..].trim();
    let path: String = bound
        .chars()
        .take_while(|c| c.is_alphanumeric() || *c == '.' || *c == '_')
        .collect();
    // A bare quantity bound (`<= 150kPa`) or non-reference is left alone.
    if path.is_empty() || !path.contains('.') {
        return predicate.to_string();
    }
    let Some(leaf) = path.rsplit('.').next().filter(|l| !l.is_empty()) else {
        return predicate.to_string();
    };
    let tail = &bound[path.len()..];
    // Point datum (embedment) takes precedence; then the interval datum
    // (bearing). A leaf in neither index leaves the bound symbolic.
    if let Some(entry) = site_index.get(leaf) {
        return if let Some(quantity) = entry {
            tracing::debug!(
                leaf = %leaf,
                quantity = %quantity,
                "civil bound resolved from point site datum"
            );
            format!("{head} {quantity}{tail}")
        } else {
            tracing::info!(leaf = %leaf, "point site datum ambiguous; left symbolic");
            predicate.to_string()
        };
    }
    match site_intervals.get(leaf) {
        Some(Some((lo, hi))) => {
            let endpoint = if op == ">=" { hi } else { lo };
            tracing::debug!(
                leaf = %leaf,
                endpoint = %endpoint,
                op = %op,
                "civil bound resolved to conservative endpoint of site interval datum"
            );
            format!("{head} {endpoint}{tail}")
        }
        Some(None) => {
            tracing::info!(leaf = %leaf, "interval site datum ambiguous; left symbolic");
            predicate.to_string()
        }
        None => {
            tracing::info!(leaf = %leaf, "site datum not found; left symbolic");
            predicate.to_string()
        }
    }
}

/// Lower one calcite `require` claim [`Field`] line into obligation(s)
/// carrying the frame's content-addressed [`PayloadRef`], when its
/// predicate is one of the [`FRAME_CLAIM_FORMS`] (calcite/03 sec. 5).
/// Any other predicate in the same group (egress claims, code-pack
/// `rule` demands, ...) is skipped, not misfiled as a frame obligation.
///
/// WO-85/D194 ruling 3: a `<X>.members.all` group subject is SUGAR for
/// a per-member sweep -- it EXPANDS here into one obligation per
/// payload member, the member pinned in both the claim name
/// (`strength[G1]`) and the rewritten predicate subject
/// (`<X>.members.G1`), exactly the WO-68 forall-combo precedent. A
/// group with one indeterminate member thereby yields N-1 real
/// verdicts plus one honest per-member deferral downstream, never a
/// wholesale defer and never a fabricated aggregate pass. A
/// `civil.embedment` bound naming a `site.<datum>` path resolves to
/// its declared quantity ([`resolve_embedment_site_bound`]).
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_frame_obligation(
    out: &mut Vec<Obligation>,
    structure_name: &str,
    payload: &regolith_oblig::FramePayload,
    line: &Field,
    sweep: Option<&SweepDomain>,
    site_index: &BTreeMap<String, Option<String>>,
    site_intervals: &BTreeMap<String, Option<(String, String)>>,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);
    if !FRAME_CLAIM_FORMS
        .iter()
        .any(|form| predicate.contains(form))
    {
        return;
    }
    // Both the embedment (point-datum) and bearing-pressure (interval-
    // datum) claim forms carry a site-datum comparator bound the
    // resolver literalizes; every other frame claim keeps its predicate.
    let predicate = if predicate.contains("civil.embedment(")
        || predicate.contains("civil.bearing_pressure(")
    {
        resolve_embedment_site_bound(&predicate, site_index, site_intervals)
    } else {
        predicate
    };

    let digest = match payload.content_digest() {
        Ok(digest) => digest,
        Err(source) => {
            tracing::warn!(
                structure = %structure_name,
                error = ?source,
                "frame payload digest failed, dropping structural obligation"
            );
            return;
        }
    };

    // The (name, predicate) instances this claim line lowers to: the
    // line itself, or its per-member expansion (D194 ruling 3). An
    // aggregate over an empty member list degrades to the unexpanded
    // single obligation (it defers downstream naming the empty frame
    // -- honest, and E0208's territory at check time).
    let group_marker = ".members.all";
    let instances: Vec<(String, String)> =
        if predicate.contains(group_marker) && !payload.members.is_empty() {
            payload
                .members
                .iter()
                .map(|member| {
                    (
                        format!("{subject}[{id}]", id = member.id),
                        predicate.replacen(group_marker, &format!(".members.{}", member.id), 1),
                    )
                })
                .collect()
        } else {
            vec![(subject.clone(), predicate.clone())]
        };
    let expanded = instances.len() > 1;

    for (instance_name, instance_predicate) in instances {
        let claim = Claim {
            name: Some(instance_name.clone()),
            form: ClaimForm::Comparison {
                lhs: instance_name.clone(),
                op: "require".to_string(),
                rhs: resolve_unit_suffix(&instance_predicate),
            },
            forall: Vec::new(),
            sf: None,
            scatter_factor: None,
            trust_floor: None,
            hints: Vec::new(),
            model_pin: None,
        };
        let payload_ref = PayloadRef {
            kind: "frame".to_string(),
            digest: digest.clone(),
            origin: structure_name.to_string(),
        };
        let obligation = Obligation {
            claim,
            // The frame's own content-addressed digest is this
            // obligation's subject identity (INV-1: a mutated frame
            // topology/section/load must hash to a different obligation)
            // -- calcite has no single `EntityDb` snapshot to key on the
            // way hematite/cuprite decls do (the fluorite precedent,
            // verbatim). Per-member expansion instances stay distinct
            // through their claim name + rewritten predicate.
            subject_ref: digest.clone(),
            given: Given {
                materials: Vec::new(),
                loads: Vec::new(),
                backing: Vec::new(),
                refs: Vec::new(),
            },
            hints: Vec::new(),
            // WO-68: a claim nested inside a `forall combo in ...:` block
            // (calcite/02 sec. 9's strength sweep) keys its obligation with
            // the declared combination-set domain, per INV-1.
            sweep: sweep.cloned(),
            payloads: vec![payload_ref],
        };
        tracing::debug!(
            structure = %structure_name,
            subject = %instance_name,
            expanded,
            hash = %obligation.content_hash(),
            "built calcite structural obligation with frame payload ref"
        );
        out.push(obligation);
    }
}
