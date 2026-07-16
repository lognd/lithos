use super::{
    codes, content_address, impl_edge, resolve_unit_suffix, AstNode, BTreeMap, Claim, ClaimForm,
    ConformanceEdge, Diagnostic, EntitySnapshots, Field, File, Given, Obligation, ParsedFile,
    RealizationEdge, SyntaxKind, SyntaxNode,
};

/// Build the EOPEN-15 demand-implication obligation for one
/// [`RealizationEdge`]: a `<workload> implies <intent>` claim keyed on
/// the enclosing system's snapshot. A rule-3 DERIVED edge additionally
/// carries `cause: derived(intent <name>)` in `given.loads` and its
/// hints, so the orchestrator/lockfile can surface the allocation
/// (cuprite/05 sec. 1; the intent's demands themselves are not
/// structurally available here -- `intents:` bodies are opaque islands,
/// WO-05 -- so no numeric copy happens in the core; the harness/lockfile
/// side threads the demand values, tracked in `docs/audit/TRIAGE.md`).
pub(crate) fn realization_obligation(
    edge: &RealizationEdge,
    snapshots: &EntitySnapshots,
) -> Obligation {
    let subject_ref = snapshots
        .scopes
        .get(&edge.system)
        .map(regolith_sem::EntityDb::snapshot_hash)
        .unwrap_or_default();
    let claim = Claim {
        name: Some(format!("realizes:{}:{}", edge.workload, edge.intent)),
        form: ClaimForm::Comparison {
            lhs: edge.workload.clone(),
            op: "implies".to_string(),
            rhs: edge.intent.clone(),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: if edge.derived {
            vec![format!("derived(intent {})", edge.intent)]
        } else {
            Vec::new()
        },
        model_pin: None,
    };
    let loads = if edge.derived {
        vec![format!("cause: derived(intent {})", edge.intent)]
    } else {
        Vec::new()
    };
    let obligation = Obligation {
        claim,
        subject_ref,
        given: Given {
            materials: Vec::new(),
            loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: if edge.derived {
            vec![format!("derived(intent {})", edge.intent)]
        } else {
            Vec::new()
        },
        sweep: None,
        payloads: vec![],
    };
    tracing::debug!(
        system = %edge.system,
        workload = %edge.workload,
        intent = %edge.intent,
        derived = edge.derived,
        hash = %obligation.content_hash(),
        "built realization demand-implication obligation (EOPEN-15 rules 2/3)"
    );
    obligation
}

/// Build the INV-13 conformance obligation for one impl/extern/import
/// [`ConformanceEdge`]: a `<upper> conforms <lower>` claim keyed on the
/// enclosing subject's snapshot (empty for a file-level `import`).
pub(crate) fn conformance_obligation(
    edge: &ConformanceEdge,
    snapshots: &EntitySnapshots,
    files: &[ParsedFile],
    diagnostics: &mut Vec<Diagnostic>,
) -> Obligation {
    // D213 (answers ESC-1): a file-level `import` edge has no enclosing
    // declaration scope (`edge.subject` is empty), so the snapshot lookup
    // yields an EMPTY hash -- which left the import-conformance obligation
    // both unwaivable (nothing to match) and undischargeable. An import
    // IS a declaration, so it gets a REAL subject_ref: the content address
    // of the imported path. The verdict is unchanged (still genuinely
    // indeterminate per D195.3 -- no scalar window on a module edge); only
    // the addressability changes, so `waive import(<pkg>)` can now name it.
    let subject_ref = if edge.kind == "import" {
        content_address("regolith.lower.import", &edge.upper).expect(
            "an import path is a plain String with no non-finite floats; \
             a hash failure here is an upstream compiler bug",
        )
    } else {
        snapshots
            .scopes
            .get(&edge.subject)
            .map(regolith_sem::EntityDb::snapshot_hash)
            .unwrap_or_default()
    };
    let claim = Claim {
        name: Some(format!("{}:{}", edge.kind, edge.upper)),
        form: ClaimForm::Comparison {
            lhs: edge.upper.clone(),
            op: "conforms".to_string(),
            rhs: edge.lower.clone(),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };
    // BE-6/INV-13: when BOTH the upper contract and the lower realization
    // carry a resolved leading comparator bound (`q: <= 20` vs `q: <= 14`),
    // thread the two refinement windows into `given.loads` so the
    // orchestrator can lower the conformance obligation into a real
    // `DischargeRequest` (the harness conformance model, AD-1). D195
    // (WO-92): when only the SPEC side resolves -- a literal promise, or
    // a parametric promise (`power: <= watts`) closed by the impl
    // header's generic pin (`<watts=50W>`) -- the sense + spec bound +
    // field name are still threaded so the orchestrator can defer with
    // the TEACHING `conformance_impl_bound_missing` reason; an
    // `impl_bound` is NEVER fabricated from the pin (a `50 <= 50`
    // discharge would be vacuous and mask real indeterminacy). Absent a
    // scalar bound on either side the windows are simply not carried and
    // the orchestrator defers the obligation honestly -- no invented window.
    let loads = match conformance_windows(edge, files, diagnostics) {
        Some(ConformanceWindow::Both {
            sense,
            spec,
            imp,
            field,
        }) => vec![
            format!("conformance_sense: {sense}"),
            format!("spec_bound: {spec}"),
            format!("impl_bound: {imp}"),
            format!("conformance_field: {field}"),
        ],
        Some(ConformanceWindow::SpecOnly { sense, spec, field }) => vec![
            format!("conformance_sense: {sense}"),
            format!("spec_bound: {spec}"),
            format!("conformance_field: {field}"),
        ],
        None => Vec::new(),
    };
    let obligation = Obligation {
        claim,
        subject_ref,
        given: Given {
            materials: Vec::new(),
            loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads: vec![],
    };
    tracing::debug!(
        kind = %edge.kind,
        upper = %edge.upper,
        lower = %edge.lower,
        hash = %obligation.content_hash(),
        "built conformance obligation (INV-13)"
    );
    obligation
}

/// The refinement window an `impl` conformance edge carries (D195):
/// both sides resolved (dischargeable), or the spec side only (the
/// teaching-deferral shape -- the impl owes a bound).
pub(crate) enum ConformanceWindow {
    /// Both the promised and the realized bound resolved, same sense --
    /// the harness conformance model can discharge this (WO-26 D104).
    Both {
        sense: String,
        spec: f64,
        imp: f64,
        field: String,
    },
    /// Only the spec side resolved (a literal promise, or a parametric
    /// promise closed by the impl header's generic pin); the impl body
    /// declares no same-named bound. NEVER discharged -- carried so the
    /// orchestrator's deferral can teach the two honest paths (D195).
    SpecOnly {
        sense: String,
        spec: f64,
        field: String,
    },
}

/// Extract the refinement window for an `impl` conformance edge,
/// matching the upper contract's promised comparator-bound fields (the
/// interface named by `edge.upper`) against the lower realization's
/// (the impl body's) same-named fields (WO-26 D104: field NAME is the
/// identity, per the WO-12 contract IR's existing source-level keying
/// -- names are already unique per interface, L1-checked). Returns
/// `None` for import/extern/select edges, or when the interface
/// declares no comparator-bound field at all.
///
/// The spec side of a promise resolves two ways (D195): a literal bound
/// (`q: <= 20`), or a parametric bound (`power: <= watts`) closed by the
/// matching impl header's generic pin (`impl HeaterDrive<watts=50W>`)
/// -- the pin resolves the SPEC side only, never the impl side (a
/// fabricated `impl_bound = 50W` would discharge `50 <= 50` vacuously,
/// masking real indeterminacy -- the INV-13/26 violation D195 forbids).
/// For each resolved promise with a same-named impl field whose sense
/// agrees (`q: <= 20` refined by `q: <= 14`), the FIRST such match
/// (source order) is returned as [`ConformanceWindow::Both`]; failing
/// any Both match, the first resolved promise with NO same-named impl
/// field is returned as [`ConformanceWindow::SpecOnly`] so the
/// orchestrator can defer teaching what the impl owes.
///
/// A promised name with NO same-named impl field pushes a constructive
/// [`codes::PROMISED_BOUND_UNMATCHED`] diagnostic naming both sides --
/// but ONLY when the impl body realizes at least one OTHER comparator-
/// bound field, i.e. it looks like an attempted refinement whose name
/// drifted from the promise. An impl that carries NO comparator-bound
/// fields at all is not diagnosed: the corpus's `FittingPort.leak`
/// promise (espresso_machine/fittings.hema) is never locally refined by
/// any implementing part -- it is consumed by the flownet leak-budget
/// chain instead (fluorite/02 sec. 6), a legitimate promise-without-
/// local-refinement shape D104's text did not anticipate. A sense
/// DISagreement between two same-named fields is likewise not an error
/// AND not a SpecOnly window -- the impl DID declare a bound (teaching
/// it to declare one would be wrong); that pair is simply not a
/// refinement window, and the obligation still defers honestly with the
/// blanket reason rather than the compiler inventing a verdict
/// (INV-13/26).
pub(crate) fn conformance_windows(
    edge: &ConformanceEdge,
    files: &[ParsedFile],
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<ConformanceWindow> {
    if edge.kind != "impl" {
        return None;
    }
    let spec_fields = interface_promised_bounds(&edge.upper, files);
    if spec_fields.is_empty() {
        return None;
    }
    let impl_nodes = matching_impl_nodes(edge, files);
    let impl_fields = impl_bound_fields(&impl_nodes);
    let pins = impl_generic_pins(&impl_nodes);
    let mut both = None;
    let mut spec_only = None;
    let mut sense_disagreement = false;
    let any_impl_bound_field = !impl_fields.is_empty();
    for (name, (spec_sense, promised)) in &spec_fields {
        // Resolve the spec side: literal, or parametric via the impl
        // header's generic pin. An unresolvable spec side (no pin, or a
        // pin whose value is not a leading quantity) contributes nothing
        // -- never a guessed bound.
        let spec_bound = match promised {
            PromisedBound::Literal(value) => Some(*value),
            PromisedBound::Param(ident) => pins.get(ident).and_then(|pin| {
                let resolved = leading_magnitude(&resolve_unit_suffix(pin));
                if resolved.is_none() {
                    tracing::debug!(
                        interface = %edge.upper,
                        field = %name,
                        param = %ident,
                        pin = %pin,
                        "generic pin does not resolve to a quantity; no spec-side bound"
                    );
                }
                resolved
            }),
        };
        let Some(spec_bound) = spec_bound else {
            continue;
        };
        if let Some((impl_sense, impl_bound)) = impl_fields.get(name) {
            if spec_sense == impl_sense {
                if both.is_none() {
                    both = Some(ConformanceWindow::Both {
                        sense: spec_sense.clone(),
                        spec: spec_bound,
                        imp: *impl_bound,
                        field: name.clone(),
                    });
                }
            } else {
                sense_disagreement = true;
            }
        } else {
            // WO-26 D104 nuance the corpus surfaced (espresso_machine's
            // `FittingPort.leak` promise, realized nowhere in the impl
            // body -- it is consumed by the flownet budget chain
            // instead, fluorite/02 sec. 6): a promised name is only a
            // constructive diagnostic when the impl body realizes NO
            // comparator-bound fields at all yet still binds this
            // edge, i.e. it looks like an attempted refinement that
            // typo'd the name. An impl that legitimately carries
            // OTHER bound fields (or none, because its promises are
            // consumed elsewhere in the promise chain) is not an
            // error -- the obligation simply has no Both window for
            // THIS name; the resolved spec side is still carried as
            // SpecOnly so the deferral can teach (D195).
            if any_impl_bound_field {
                diagnostics.push(Diagnostic::error(
                    codes::PROMISED_BOUND_UNMATCHED,
                    format!(
                        "interface `{}` promises bound field `{name}`, but the \
                         impl for `{}` declares no matching `{name}:` field \
                         (it declares other bound fields, so this looks like \
                         a name mismatch rather than a promise consumed \
                         elsewhere)",
                        edge.upper, edge.lower
                    ),
                ));
            }
            if spec_only.is_none() {
                spec_only = Some(ConformanceWindow::SpecOnly {
                    sense: spec_sense.clone(),
                    spec: spec_bound,
                    field: name.clone(),
                });
            }
        }
    }
    if both.is_none() && spec_only.is_none() && sense_disagreement {
        tracing::debug!(
            interface = %edge.upper,
            lower = %edge.lower,
            "promised/impl bounds disagree in sense; no refinement window (honest defer)"
        );
    }
    both.or(spec_only)
}

/// A promise's spec-side bound expression: a literal magnitude, or a
/// reference to a generic parameter the impl header's pin closes (D195,
/// `power: <= watts` against `impl HeaterDrive<watts=50W>`).
pub(crate) enum PromisedBound {
    Literal(f64),
    Param(String),
}

/// The leading numeric magnitude of `text` (`50W` -> 50, `-3.5 mm` ->
/// -3.5); `None` when `text` does not open with a number. The unit
/// suffix is NOT interpreted here -- callers that need SI-base values
/// run [`resolve_unit_suffix`] first.
pub(crate) fn leading_magnitude(text: &str) -> Option<f64> {
    let number: String = text
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+')
        .collect();
    number.parse().ok()
}

/// Parse a leading one-sided comparator bound (`<= 20`, `>= 6`, `< 3`)
/// off a field's value text into `(sense, magnitude)`; `sense` is
/// `"upper"` for `<`/`<=` and `"lower"` for `>`/`>=`. `None` when the
/// text is not a leading comparator over a bare number.
pub(crate) fn bound_from_value_text(text: &str) -> Option<(String, f64)> {
    if let Some((sense, PromisedBound::Literal(magnitude))) = promised_bound_from_value_text(text) {
        return Some((sense, magnitude));
    }
    None
}

/// Parse a leading one-sided comparator bound off a field's value text
/// into `(sense, bound-expression)`: a bare number is
/// [`PromisedBound::Literal`], a bare identifier (`<= watts`) is
/// [`PromisedBound::Param`] awaiting the impl header's generic pin
/// (D195). `None` when the text is neither shape -- a compound
/// expression (`<= watts * 1.1`) is honestly not extracted rather than
/// half-parsed.
pub(crate) fn promised_bound_from_value_text(text: &str) -> Option<(String, PromisedBound)> {
    let trimmed = text.trim();
    let (sense, rest) = if let Some(rest) = trimmed.strip_prefix("<=") {
        ("upper", rest)
    } else if let Some(rest) = trimmed.strip_prefix(">=") {
        ("lower", rest)
    } else if let Some(rest) = trimmed.strip_prefix('<') {
        ("upper", rest)
    } else if let Some(rest) = trimmed.strip_prefix('>') {
        ("lower", rest)
    } else {
        return None;
    };
    if let Some(magnitude) = leading_magnitude(rest) {
        return Some((sense.to_string(), PromisedBound::Literal(magnitude)));
    }
    let ident = rest.trim();
    let is_ident = !ident.is_empty()
        && ident
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && ident.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
    if is_ident {
        return Some((sense.to_string(), PromisedBound::Param(ident.to_string())));
    }
    None
}

/// Every comparator-bound field anywhere under `node` (interface decl
/// body or impl body), keyed by its field NAME (WO-26 D104 -- name is
/// the promised-bound identity; source order, first bound per name
/// wins if a name somehow repeats).
pub(crate) fn collect_bound_fields(node: &SyntaxNode) -> Vec<(String, (String, f64))> {
    let mut out = Vec::new();
    for descendant in node.descendants() {
        if let Some(field) = Field::cast(descendant) {
            if let Some(value) = field.value() {
                if let Some(bound) = bound_from_value_text(&value.text().to_string()) {
                    out.push((field.name(), bound));
                }
            }
        }
    }
    out
}

/// The upper contract's promised bounds: every comparator-bound field
/// (literal or parametric, D195) of the `interface <name>` declaration,
/// by name, in source order.
pub(crate) fn interface_promised_bounds(
    name: &str,
    files: &[ParsedFile],
) -> Vec<(String, (String, PromisedBound))> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw)
                && decl.name().as_deref() == Some(name)
            {
                let mut fields = Vec::new();
                for descendant in decl.syntax().descendants() {
                    if let Some(field) = Field::cast(descendant) {
                        if let Some(value) = field.value() {
                            if let Some(bound) =
                                promised_bound_from_value_text(&value.text().to_string())
                            {
                                fields.push((field.name(), bound));
                            }
                        }
                    }
                }
                if !fields.is_empty() {
                    return fields;
                }
            }
        }
    }
    Vec::new()
}

/// Every impl node (top-level `impl` [`Decl`] or in-body `ImplStmt`)
/// whose extracted edge matches `edge`, in file/source order. Duplicate
/// edges (two `impl HeaterDrive<...> for self` instantiations in one
/// board) all appear; consumers take the first node that carries what
/// they need, the same first-wins convention D104 set.
pub(crate) fn matching_impl_nodes(edge: &ConformanceEdge, files: &[ParsedFile]) -> Vec<SyntaxNode> {
    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let decl_name = decl.name().unwrap_or_default();
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw)
                && impl_edge(decl.syntax(), &decl_name).as_ref() == Some(edge)
            {
                out.push(decl.syntax().clone());
            }
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt
                    && impl_edge(&node, &decl_name).as_ref() == Some(edge)
                {
                    out.push(node);
                }
            }
        }
    }
    out
}

/// The lower realization's declared bounds: every comparator-bound
/// field of the first matching impl node that declares any, keyed by
/// name (the D104 first-wins convention over [`matching_impl_nodes`]).
pub(crate) fn impl_bound_fields(impl_nodes: &[SyntaxNode]) -> BTreeMap<String, (String, f64)> {
    impl_nodes
        .iter()
        .map(collect_bound_fields)
        .find(|fields| !fields.is_empty())
        .map(Vec::into_iter)
        .map(Iterator::collect)
        .unwrap_or_default()
}

/// The `<name=value, ...>` generic-argument pins of the first matching
/// impl node that carries any (`impl HeaterDrive<watts=50W> for self`
/// -> `{watts: "50W"}`). Bare positional arguments (`<M5, ...>`) carry
/// no name to pin and are skipped. Text-level, single-header-line scan
/// (the module's convention): the pin list is read off the node's first
/// source line, between the first `<` and its matching `>` at bracket
/// depth 0, split at top-level commas.
pub(crate) fn impl_generic_pins(impl_nodes: &[SyntaxNode]) -> BTreeMap<String, String> {
    for node in impl_nodes {
        let text = node.text().to_string();
        let header = text.lines().next().unwrap_or_default();
        let Some(open) = header.find('<') else {
            continue;
        };
        let bytes = header.as_bytes();
        let mut depth = 0i32;
        let mut close = None;
        for (i, &b) in bytes.iter().enumerate().skip(open + 1) {
            match b {
                b'(' | b'[' => depth += 1,
                b')' | b']' => depth -= 1,
                b'>' if depth == 0 => {
                    close = Some(i);
                    break;
                }
                _ => {}
            }
        }
        let Some(close) = close else {
            continue;
        };
        let inside = &header[open + 1..close];
        // Split at top-level commas (a pinned value may itself carry a
        // call with commas, e.g. `pattern=grid(2, 2)`).
        let mut pins = BTreeMap::new();
        let mut depth = 0i32;
        let mut start = 0usize;
        let mut parts = Vec::new();
        for (i, &b) in inside.as_bytes().iter().enumerate() {
            match b {
                b'(' | b'[' => depth += 1,
                b')' | b']' => depth -= 1,
                b',' if depth == 0 => {
                    parts.push(&inside[start..i]);
                    start = i + 1;
                }
                _ => {}
            }
        }
        parts.push(&inside[start..]);
        for part in parts {
            if let Some((name, value)) = part.split_once('=') {
                pins.insert(name.trim().to_string(), value.trim().to_string());
            }
        }
        if !pins.is_empty() {
            tracing::debug!(pins = ?pins, "extracted impl-header generic pins (D195)");
            return pins;
        }
    }
    BTreeMap::new()
}
