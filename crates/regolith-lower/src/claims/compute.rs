use super::{
    codes, BTreeMap, Claim, ClaimForm, CoverageAxis, CoverageDomain, CoverageMethod, Decl,
    Diagnostic, FieldDatum, Given, Obligation,
};

/// WO-33 D98: build one producer [`Obligation`] (`ClaimForm::Compute`)
/// and one [`FieldDatum`] ledger entry (appended to `field_datums`) per
/// `compute` claim in `decl`, across every `require` group. Returns the
/// declared name -> producer-obligation map plus the name -> `over`
/// text map ([`check_compute_field_cycles`]'s dependency scan), both
/// keyed for [`push_require_obligations`]'s projection-head resolution.
pub(crate) fn collect_compute_producers(
    decl: &Decl,
    decl_name: &str,
    subject_ref: &str,
    given: &Given,
    field_datums: &mut Vec<FieldDatum>,
) -> (BTreeMap<String, Obligation>, BTreeMap<String, String>) {
    let mut compute_producers: BTreeMap<String, Obligation> = BTreeMap::new();
    let mut compute_over_text: BTreeMap<String, String> = BTreeMap::new();
    for group in decl.claims() {
        for cfield in group.compute_claims() {
            let name = cfield.name();
            if name.is_empty() {
                continue;
            }
            let predicate = cfield.predicate_text();
            let (quantity_kind, over_text, axis) = parse_compute_domain(&predicate);
            let claim = Claim {
                name: Some(name.clone()),
                form: ClaimForm::Compute {
                    quantity_kind: quantity_kind.clone(),
                    over: over_text.clone(),
                },
                forall: Vec::new(),
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: Vec::new(),
                model_pin: None,
            };
            let obligation = Obligation {
                claim,
                subject_ref: subject_ref.to_string(),
                given: given.clone(),
                hints: Vec::new(),
                sweep: None,
                payloads: Vec::new(),
            };
            tracing::debug!(
                decl = %decl_name,
                field = %name,
                hash = %obligation.content_hash(),
                "built obligation from compute claim (WO-33 D98)"
            );
            field_datums.push(FieldDatum {
                name: name.clone(),
                quantity_kind,
                axis,
                payload: None,
            });
            compute_over_text.insert(name.clone(), over_text);
            compute_producers.insert(name, obligation);
        }
    }
    (compute_producers, compute_over_text)
}

/// WO-33 D98: split a `compute` claim's predicate text
/// (`<quantity kind> over <index domain>`) into `(quantity_kind,
/// over_text, axis)`. `over_text` is kept verbatim (the harness half
/// interprets it); `axis` is the DECLARED `CoverageAxis` for the
/// `FieldDatum` ledger entry, with `method: Undischarged` -- no model
/// has resolved it yet (this WO's honest interim, see the module doc's
/// non-goals). A `<var> in [lo, hi]` domain is a continuous interval
/// axis named `<var>`; anything else (a zone-set reference, e.g.
/// `liner.zones`) is an enumerated axis with the reference itself as
/// its one (unexpanded) value -- the actual zone membership is a
/// semantic fact this text-only pass does not resolve.
pub(crate) fn parse_compute_domain(predicate: &str) -> (String, String, CoverageAxis) {
    let (quantity_kind, over_text) = match predicate.split_once(" over ") {
        Some((q, o)) => (q.trim().to_string(), o.trim().to_string()),
        None => (predicate.trim().to_string(), String::new()),
    };

    let axis = if let Some((var, rest)) = over_text.split_once(" in ") {
        CoverageAxis {
            axis: var.trim().to_string(),
            domain: CoverageDomain::Interval(rest.trim().to_string()),
            method: CoverageMethod::Undischarged,
        }
    } else {
        CoverageAxis {
            axis: over_text.clone(),
            domain: CoverageDomain::Values {
                values: vec![over_text.clone()],
            },
            method: CoverageMethod::Undischarged,
        }
    };

    (quantity_kind, over_text, axis)
}

/// True iff `word` occurs in `haystack` as a whole identifier (not a
/// substring of a longer one): neither the character before nor after
/// the match is alphanumeric, `_`, or `.` (so `wall_T` does not match
/// inside `wall_Total`, and a dotted path is never partially matched).
/// Shared by the projection-head extraction and the compute-cycle scan.
pub(crate) fn contains_word(haystack: &str, word: &str) -> bool {
    if word.is_empty() {
        return false;
    }
    let mut search_from = 0usize;
    while let Some(rel) = haystack[search_from..].find(word) {
        let idx = search_from + rel;
        let before_ok = haystack[..idx]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_' && c != '.');
        let after = &haystack[idx + word.len()..];
        let after_ok = after
            .chars()
            .next()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_' && c != '.');
        if before_ok && after_ok {
            return true;
        }
        search_from = idx + word.len();
    }
    false
}

/// WO-33 D98: extract every projection-head field reference from a
/// predicate (`max(name)`, `min(name)`, `slope(name, ...)`, or a
/// leading `<name> at ...` form), in source order. This is a
/// deliberately narrow, text-only recognizer -- it does not parse a
/// general call expression -- matching the same "kept as text" stance
/// as the rest of this pass (`full_predicate_text`, `resolve_unit_suffix`).
///
/// Coordinator-verified E0303 misfire fix (the D194-family unambiguity
/// rule: a call lhs is a claim FORM, never a projection): a head must be
/// the projection KEYWORD itself, not the tail of a longer call name
/// (`info.fmax(`, `elec.min(` -- anything alphanumeric/`_`/`.` right
/// before it means a different callee), and the extracted name must be a
/// genuine bare/dotted `<subject>.<field>` identifier -- a call
/// expression argument (`v(store.cells.any)`) is a claim form's input,
/// and slicing into it produced the mangled `v(store.cells.any` E0303.
pub(crate) fn extract_projection_heads(predicate: &str) -> Vec<String> {
    let mut refs = Vec::new();
    for head in ["max(", "min(", "slope("] {
        let mut search_from = 0usize;
        while let Some(rel) = predicate[search_from..].find(head) {
            let match_start = search_from + rel;
            let start = match_start + head.len();
            let arg_end = predicate[start..]
                .find([',', ')'])
                .map_or(predicate.len(), |i| start + i);
            let name = predicate[start..arg_end].trim();
            let head_is_word = predicate[..match_start]
                .chars()
                .next_back()
                .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_' && c != '.');
            let name_is_field_ref = !name.is_empty()
                && name
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.');
            if head_is_word && name_is_field_ref {
                refs.push(name.to_string());
            }
            search_from = arg_end.max(start);
        }
    }
    // `<name> at zone(...)` / `<name> at <var>(...)`: the leading
    // dotted identifier before a top-level " at " qualifier.
    if let Some(at_idx) = predicate.find(" at ") {
        let lead = predicate[..at_idx].trim();
        if !lead.is_empty()
            && lead
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
        {
            refs.push(lead.to_string());
        }
    }
    refs
}

/// WO-33 D98 deliverable 3: fold `predicate`'s projection-head field
/// references into `given.refs` (as `(name, "field:<content_hash>")`
/// pairs, the promise-chain reference), diagnosing any reference to a
/// field NOT in `compute_producers` as [`codes::UNRESOLVED_FIELD_REFERENCE`]
/// rather than passing the raw name through silently.
pub(crate) fn with_field_refs(
    given: &Given,
    decl_name: &str,
    subject: &str,
    predicate: &str,
    compute_producers: &BTreeMap<String, Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
) -> Given {
    let mut out = given.clone();
    for name in extract_projection_heads(predicate) {
        if let Some(producer) = compute_producers.get(&name) {
            out.refs
                .push((name, format!("field:{}", producer.content_hash())));
        } else {
            tracing::debug!(
                decl = %decl_name,
                subject = %subject,
                field = %name,
                "compute-field projection names an undeclared field"
            );
            diagnostics.push(Diagnostic::error(
                codes::UNRESOLVED_FIELD_REFERENCE,
                format!(
                    "`{subject}` projects field `{name}`, but `{decl_name}` \
                     declares no `compute {name}: ...` claim"
                ),
            ));
        }
    }
    out
}

/// WO-33 D98: detect a cycle in the compute-field promise DAG within
/// one decl -- a `compute` claim whose `over` text (directly or
/// transitively) references another compute field that, in turn,
/// depends back on it. Standard white/gray/black DFS; on the first
/// back-edge found, names the full chain in one diagnostic (never a
/// panic/infinite loop, and never more than one diagnostic per decl --
/// fixing the first reported cycle is enough to re-run the check).
pub(crate) fn check_compute_field_cycles(
    decl_name: &str,
    over_text: &BTreeMap<String, String>,
    compute_producers: &BTreeMap<String, Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let names: Vec<&String> = compute_producers.keys().collect();
    let neighbors = |n: &str| -> Vec<String> {
        let Some(text) = over_text.get(n) else {
            return Vec::new();
        };
        names
            .iter()
            .filter(|other| other.as_str() != n && contains_word(text, other))
            .map(|s| (*s).clone())
            .collect()
    };

    let mut state: BTreeMap<String, u8> = BTreeMap::new(); // 0=white,1=gray,2=black
    for start in &names {
        if state.get(start.as_str()).copied().unwrap_or(0) != 0 {
            continue;
        }
        let mut stack: Vec<(String, usize)> = vec![((*start).clone(), 0)];
        let mut path: Vec<String> = vec![(*start).clone()];
        state.insert((*start).clone(), 1);
        while let Some((node, idx)) = stack.pop() {
            let succ = neighbors(&node);
            if idx < succ.len() {
                let next = succ[idx].clone();
                stack.push((node.clone(), idx + 1));
                match state.get(&next).copied().unwrap_or(0) {
                    0 => {
                        state.insert(next.clone(), 1);
                        path.push(next.clone());
                        stack.push((next, 0));
                    }
                    1 => {
                        // Back edge: a cycle from `next` to `next` through `path`.
                        let cycle_start = path.iter().position(|p| p == &next).unwrap_or(0);
                        let mut chain: Vec<String> = path[cycle_start..].to_vec();
                        chain.push(next.clone());
                        diagnostics.push(Diagnostic::error(
                            codes::COMPUTE_FIELD_CYCLE,
                            format!(
                                "compute-field cycle in `{decl_name}`: {}",
                                chain.join(" -> ")
                            ),
                        ));
                        return;
                    }
                    _ => {}
                }
            } else {
                state.insert(node.clone(), 2);
                if path.last() == Some(&node) {
                    path.pop();
                }
            }
        }
    }
}
