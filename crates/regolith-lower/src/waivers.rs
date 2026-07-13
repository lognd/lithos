//! Pass 5b: `waive ...:` blocks -> the waiver ledger + honesty checks.
//!
//! Regolith reference: `docs/spec/regolith/12-overrides-and-hints.md` sec.
//! 3 (the rung-7 `waive` construct) and `docs/spec/regolith/13` INV-2
//! (ladder safety) / INV-12 (waiver honesty). This pass runs AFTER
//! claim lowering so it can match each declared waiver against the
//! obligations the pipeline actually emitted.
//!
//! The two invariants are realized here structurally:
//!
//! * **INV-2 (ladder safety).** A waiver only ever produces a
//!   [`WaiverRecord`] -- an acceptance record referencing the matched
//!   obligations' content hashes. This pass NEVER touches the obligation
//!   or evidence set, so a waiver cannot convert `violated` into
//!   `discharged`; the worst it does is record an attributed, release-
//!   gated acceptance. An overreaching waiver (no mandatory `basis:`)
//!   is itself a diagnostic (`WAIVER_MISSING_BASIS`), not an acceptance.
//!   The re-keying half reduces to INV-1: a waiver keyed to a claim
//!   whose obligation was re-keyed (e.g. its material changed) no longer
//!   matches, so it becomes `Stale` -- a diagnostic, never a silent pass.
//! * **INV-12 (waiver honesty).** Every waiver is recorded in the
//!   ledger as waived-with-reason (its `basis` and match set); a waiver
//!   that matches a claim the pipeline emits obligations for yet accepts
//!   none is `Stale` (`STALE_WAIVER`). Rule-pack targets the static core
//!   cannot see (`dfm`/`drc`/`erc`) are recorded as `DeferredRulePack`
//!   -- release-gated, never falsely stale.

use regolith_diag::{codes, Diagnostic, LabeledSpan, Span};
use regolith_oblig::{LedgerEntry, Obligation, WaiveLedger, Waiver, WaiverKind, WaiverRecord};
use regolith_syntax::ast::{AstNode, File, WaiveBlock};

use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;

/// The waiver ledger and any honesty diagnostics from this pass.
#[derive(Debug, Clone, Default)]
pub struct WaiverReport {
    /// The build's waiver ledger (the INV-12 audit surface).
    pub ledger: WaiveLedger,
    /// Stale-waiver / missing-basis diagnostics (INV-2/INV-12).
    pub diagnostics: Vec<Diagnostic>,
}

/// Build the waiver ledger by matching every `waive ...:` block against
/// the emitted `obligations`, and collect the honesty diagnostics.
#[must_use]
pub fn build_ledger(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
    obligations: &[Obligation],
) -> WaiverReport {
    let span = tracing::info_span!("lower.waivers");
    let _enter = span.enter();

    let mut report = WaiverReport::default();

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };

        // Position 1 (historical): hema/cupr declaration bodies. Each
        // decl's waivers match obligations sharing the decl's entity
        // snapshot hash.
        for decl in file.decls() {
            let Some(decl_name) = decl.name() else {
                continue;
            };
            if decl_is_poisoned(&decl) {
                continue;
            }
            let subject_ref = snapshots
                .scopes
                .get(&decl_name)
                .map(regolith_sem::EntityDb::snapshot_hash)
                .unwrap_or_default();
            let scope = MatchScope::SubjectRef(subject_ref);
            for block in decl.waivers() {
                lower_one_waiver(
                    &pf.path,
                    decl.name().as_deref(),
                    &block,
                    &scope,
                    obligations,
                    &mut report,
                );
            }
        }

        // D214 (answers ESC-2): harvest is grammar-complete -- a `waive`
        // that PARSES yet is silently unharvested is a bug, never policy.
        // Calcite (and fluorite) top-level `require` groups are NOT plain
        // `Decl`s (they ride `File::fluid_requires`), so the loop above
        // never reached the waivers a designer authors inside a
        // `require Structure:` body. Their obligations key their
        // subject_ref on the frame/flownet payload digest (not an
        // EntityDb snapshot), so the match scope is the file's structure
        // name -- an obligation carrying a payload ref of that origin.
        // D215(c): a top-level `require` body's claims key their payload
        // ref on the origin of the structure OR flownet they describe, so
        // the scope is EVERY structure and flownet name declared in this
        // file. A pure fluorite flownet file (no `structure`) previously
        // fell back to an unmatched empty scope -- its require-body waivers
        // vanished; the flownet names now join the harvest/match scope
        // exactly as D214 added the frame origins.
        let file_origins: Vec<String> = file
            .structures()
            .into_iter()
            .filter_map(|s| s.name())
            .chain(file.flownets().into_iter().filter_map(|f| f.name()))
            .collect();
        for req in file.fluid_requires() {
            let scope = MatchScope::FrameOrigins(file_origins.clone());
            for block in req.syntax().descendants().filter_map(WaiveBlock::cast) {
                lower_one_waiver(&pf.path, None, &block, &scope, obligations, &mut report);
            }
        }

        // D214: calcite `structure` bodies. The grammar (grammar.ebnf
        // `structure-body = { transfers-block | field | ctor-stmt |
        // opaque-stmt }`) routes a `waive` line to `opaque-stmt`, so a
        // waive inside a structure body parses as an `OpaqueIsland`, NOT a
        // `WaiveBlock` node -- this descendants scan finds ZERO of them
        // today (verified against the layout pass). It is kept so the
        // harvest is correct-by-construction the day the grammar admits a
        // waive-block there; forcing that admission now would be the
        // grammar change D214 explicitly forbids. See this WO's close-out.
        for structure in file.structures() {
            let scope = MatchScope::FrameOrigins(vec![structure.name().unwrap_or_default()]);
            for block in structure
                .syntax()
                .descendants()
                .filter_map(WaiveBlock::cast)
            {
                lower_one_waiver(&pf.path, None, &block, &scope, obligations, &mut report);
            }
        }
    }

    // INV-12: surface every stale waiver as a diagnostic (kept in one
    // home on the ledger so the classification and the diagnostic can
    // never desync).
    report
        .diagnostics
        .extend(report.ledger.stale_waiver_diagnostics());

    tracing::info!(
        waivers = report.ledger.entries().len(),
        diagnostics = report.diagnostics.len(),
        "lower: waiver ledger built"
    );

    report
}

/// Lower a single `waive` block: validate its mandatory basis (INV-2
/// overreach guard), classify it against the obligation set (INV-12),
/// and record it. Never mutates `obligations` (INV-2 ladder safety).
fn lower_one_waiver(
    path: &camino::Utf8Path,
    decl_name: Option<&str>,
    block: &WaiveBlock,
    scope: &MatchScope,
    obligations: &[Obligation],
    report: &mut WaiverReport,
) {
    let target = block.target();

    // D117: the waive ladder cannot silence its own audit -- a `waive`
    // whose target spells a lint code (`Lxxxx`) is rejected outright,
    // before basis/matching, so it can never be recorded as an
    // acceptance (`[lints]` is the only channel that tunes a lint
    // code's severity).
    if let Some(code_text) = lint_code_shaped(&target) {
        let range = block.syntax().text_range();
        let span = Span::new(
            path.to_owned(),
            usize::from(range.start()),
            usize::from(range.end()),
        );
        report.diagnostics.push(
            Diagnostic::error(
                codes::WAIVE_NAMES_LINT_CODE,
                format!(
                    "`waive` cannot name lint code `{code_text}`; \
                     configure it in `magnetite.toml [lints]` instead"
                ),
            )
            .with_span(LabeledSpan::new(
                span,
                "lint codes are tuned by [lints], never waived",
            )),
        );
        tracing::debug!(target = %target, "rejected waive naming a lint code (D117)");
        return;
    }

    // INV-2 overreach: an unjustified concession (no mandatory `basis:`)
    // is rejected as a diagnostic, never recorded as an acceptance.
    let Some(basis) = block.basis().filter(|b| !b.is_empty()) else {
        let range = block.syntax().text_range();
        let span = Span::new(
            path.to_owned(),
            usize::from(range.start()),
            usize::from(range.end()),
        );
        report.diagnostics.push(
            Diagnostic::error(
                codes::WAIVER_MISSING_BASIS,
                format!("waiver `{target}` has no mandatory `basis:` clause"),
            )
            .with_span(LabeledSpan::new(
                span,
                "a waiver must state its basis (regolith/12 rule 2)",
            )),
        );
        tracing::debug!(target = %target, "rejected basis-less waiver (INV-2 overreach)");
        return;
    };

    let waiver = Waiver {
        target: target.clone(),
        scope: block.scope(),
        basis,
        evidence: block.evidence(),
        expires: block.expires(),
    };

    let (kind, matched) = classify(&target, block.scope().as_deref(), scope, obligations);
    tracing::debug!(
        decl = %decl_name.unwrap_or_default(),
        target = %target,
        kind = ?kind,
        matched = matched.len(),
        "recorded waiver"
    );
    // D105(d): `match_set` is the sorted entity-ref record for the
    // INV-12 growth diff. The diff PASS is the WO-26 remainder's job;
    // this WO lands only the schema field, so the authored match set
    // is derived from the evaluation-time `matched` hashes for now
    // (a faithful placeholder, never a guess -- WO-26 replaces this
    // with the true authored entity refs).
    let mut match_set = matched.clone();
    match_set.sort();
    report.ledger.record(LedgerEntry::Waived(WaiverRecord {
        waiver,
        kind,
        matched,
        match_set,
    }));
}

/// If `target` is exactly shaped like a lint code (`L` or `l` followed
/// by four ASCII digits, e.g. `L0801`/`l0801`), return its canonical
/// uppercase spelling (D117: `waive` cannot name one). A `Group.claim`
/// or rule-pack target never collides with this shape (both always
/// carry at least one `.`/`(` character).
fn lint_code_shaped(target: &str) -> Option<String> {
    let bytes = target.as_bytes();
    if bytes.len() != 5 {
        return None;
    }
    if !matches!(bytes[0], b'L' | b'l') {
        return None;
    }
    if !bytes[1..].iter().all(u8::is_ascii_digit) {
        return None;
    }
    Some(target.to_uppercase())
}

/// The default matching domain for a harvested `waive`, fixed by the
/// grammatical POSITION it was found in (D214: grammar-complete harvest).
/// A target with its OWN global identity (an `import(<pkg>)` module edge,
/// a rule-pack rule) overrides this scope in [`classify`].
enum MatchScope {
    /// A hema/cupr declaration body: obligations sharing the decl's
    /// entity-snapshot hash (the historical scope).
    SubjectRef(String),
    /// A calcite/fluorite top-level `require` (or `structure`) position:
    /// obligations carrying a payload ref of ANY of these origin names
    /// (frame/flownet obligations key their subject_ref on the
    /// frame/flownet payload digest, not an EntityDb snapshot, so the
    /// scope is the file's declared structure AND flownet names -- D215(c)
    /// adds the flownet origins so a pure `.fluo` file's require-body
    /// waive matches its own flownet claims).
    FrameOrigins(Vec<String>),
}

impl MatchScope {
    /// Whether `obligation` lies inside this scope's default matching
    /// domain (the claim/rule-pack arms filter on this).
    fn contains(&self, obligation: &Obligation) -> bool {
        match self {
            MatchScope::SubjectRef(hash) => obligation.subject_ref == *hash,
            MatchScope::FrameOrigins(names) => obligation
                .payloads
                .iter()
                .any(|p| names.contains(&p.origin)),
        }
    }
}

/// Classify a waiver `target` against the obligation set and collect the
/// content hashes it accepts. An `import(<pkg>)` target (D213) matches
/// the file-level import-conformance obligation whose claim name is
/// `import:<pkg>` -- a module edge is file-global (its subject_ref is the
/// import's own content address), so it matches regardless of the
/// enclosing position `scope`; one that matches nothing is `Stale`
/// (INV-12). A rule-pack target (`dfm(pack.rule)`/`drc(...)`/`erc(...)`)
/// matches the rule obligations the WO-28 engine lowers (their claim name
/// IS the waive-target spelling); one that matches nothing stays
/// `DeferredRulePack` -- release-gated, never falsely stale, because the
/// rule may live on a realized-fact tier the static core cannot see yet.
/// An `impl(<Interface>)` target (D215) matches the interface's
/// conformance-edge obligations -- those whose claim name is
/// `impl:<Interface>`, `extern:<Interface>`, or `select:<Interface>` (the
/// three realization kinds `contracts::impl_edge` lowers for one
/// interface binding; they all key on the enclosing subject's real
/// snapshot hash, unlike a bare import). Unscoped, it matches the
/// interface's edges wherever they appear in the declaring artifact
/// (the D213 import spelling generalized to a named interface); with an
/// `on <impl-site>` clause it narrows to the edges in the enclosing
/// declaration's scope. One that matches no edge is `Stale` (INV-12).
/// A `Group.claim` target matches obligations in `scope` whose claim name
/// is the target's trailing segment; a dotted window-half target
/// (`<Group>.<claim>.hi`/`.lo`, D215) matches the split window
/// obligation whose claim name is the trailing `<claim>.<half>` pair
/// (`push_within_window_obligations` names each half `<subject>.<half>`).
/// A claim target that matches nothing is `Stale` (INV-12).
fn classify(
    target: &str,
    on_scope: Option<&str>,
    scope: &MatchScope,
    obligations: &[Obligation],
) -> (WaiverKind, Vec<String>) {
    if let Some(pkg) = import_target_pkg(target) {
        let claim_name = format!("import:{pkg}");
        let matched: Vec<String> = obligations
            .iter()
            .filter(|o| o.claim.name.as_deref() == Some(claim_name.as_str()))
            .map(Obligation::content_hash)
            .collect();
        return if matched.is_empty() {
            (WaiverKind::Stale, Vec::new())
        } else {
            (WaiverKind::Matched, matched)
        };
    }

    if let Some(iface) = impl_target_iface(target) {
        // A scoped `on <impl-site>` narrows to the edges in the enclosing
        // declaration's scope; an unscoped waive covers the interface's
        // edges file-wide (the D213 import precedent, generalized).
        let scoped = on_scope.is_some();
        let matched: Vec<String> = obligations
            .iter()
            .filter(|o| conformance_edge_names_iface(o, iface) && (!scoped || scope.contains(o)))
            .map(Obligation::content_hash)
            .collect();
        return if matched.is_empty() {
            (WaiverKind::Stale, Vec::new())
        } else {
            (WaiverKind::Matched, matched)
        };
    }

    if is_rule_pack(target) {
        let matched: Vec<String> = obligations
            .iter()
            .filter(|o| scope.contains(o) && rule_target_matches(target, o))
            .map(Obligation::content_hash)
            .collect();
        if matched.is_empty() {
            return (WaiverKind::DeferredRulePack, Vec::new());
        }
        return (WaiverKind::Matched, matched);
    }

    let claim_name = claim_target_name(target);
    let matched: Vec<String> = obligations
        .iter()
        .filter(|o| scope.contains(o) && o.claim.name.as_deref() == Some(claim_name.as_str()))
        .map(Obligation::content_hash)
        .collect();

    if matched.is_empty() {
        (WaiverKind::Stale, Vec::new())
    } else {
        (WaiverKind::Matched, matched)
    }
}

/// If `target` is the D213 module-edge spelling `import(<pkg>)`, return
/// the inner package path (`import(std.mech)` -> `std.mech`). A
/// `Group.claim` or rule-pack target never collides with this shape (the
/// leading `import(` prefix is unique to a module-edge waiver).
fn import_target_pkg(target: &str) -> Option<&str> {
    target
        .strip_prefix("import(")
        .and_then(|rest| rest.strip_suffix(')'))
        .map(str::trim)
        .filter(|pkg| !pkg.is_empty())
}

/// If `target` is the D215 interface-edge spelling `impl(<Interface>)`,
/// return the inner interface name (`impl(SparCapMount)` ->
/// `SparCapMount`). An `import(<pkg>)`, `Group.claim`, or rule-pack
/// target never collides with this shape (the leading `impl(` prefix is
/// unique to an interface-edge waiver).
fn impl_target_iface(target: &str) -> Option<&str> {
    target
        .strip_prefix("impl(")
        .and_then(|rest| rest.strip_suffix(')'))
        .map(str::trim)
        .filter(|iface| !iface.is_empty())
}

/// Whether `obligation` is a conformance edge for interface `iface` --
/// any of the three realization kinds `contracts::impl_edge` lowers
/// (`impl:`/`extern:`/`select:`) whose interface name is `iface`. The
/// interface (not the realization mechanism) is what an `impl(<Interface>)`
/// waiver names, so all three kinds are accepted (D215).
fn conformance_edge_names_iface(obligation: &Obligation, iface: &str) -> bool {
    let Some(name) = obligation.claim.name.as_deref() else {
        return false;
    };
    ["impl:", "extern:", "select:"]
        .iter()
        .any(|kind| name.strip_prefix(kind) == Some(iface))
}

/// The claim name an ordinary (`Group.claim`) or window-half
/// (`<Group>.<claim>.hi`/`.lo`, D215) target matches against. A window
/// half's obligation is named `<subject>.<half>` by
/// `push_within_window_obligations`, so the trailing `<claim>.<half>`
/// pair is kept; every other claim target matches on its trailing
/// segment alone (the historical behavior).
fn claim_target_name(target: &str) -> String {
    let segs: Vec<&str> = target.rsplitn(3, '.').collect();
    let is_window_half = matches!(segs.first(), Some(&"hi" | &"lo"));
    if is_window_half && segs.len() >= 2 {
        format!("{}.{}", segs[1], segs[0])
    } else {
        segs.first().copied().unwrap_or(target).to_string()
    }
}

/// Whether a rule-pack waive target accepts an obligation: exact
/// claim-name match (`dfm(std.sheet_metal.min_bend_radius)`), or the
/// corpus's unqualified spelling (`dfm(min_bend_radius)`) matching a
/// claim of the same family whose qualified rule name ENDS with the
/// target's inner name (`.min_bend_radius`). Never a substring match.
fn rule_target_matches(target: &str, obligation: &Obligation) -> bool {
    let Some(claim_name) = obligation.claim.name.as_deref() else {
        return false;
    };
    if claim_name == target {
        return true;
    }
    let split = |s: &str| -> Option<(String, String)> {
        let (family, rest) = s.split_once('(')?;
        Some((family.to_string(), rest.strip_suffix(')')?.to_string()))
    };
    let (Some((t_family, t_inner)), Some((c_family, c_inner))) = (split(target), split(claim_name))
    else {
        return false;
    };
    t_family == c_family && (c_inner == t_inner || c_inner.ends_with(&format!(".{t_inner}")))
}

/// Whether a waiver target names a rule-pack rule (`dfm(...)`,
/// `drc(...)`, `erc(...)`).
fn is_rule_pack(target: &str) -> bool {
    ["dfm(", "drc(", "erc("]
        .iter()
        .any(|p| target.starts_with(p))
}

#[cfg(test)]
mod tests {
    use super::build_ledger;
    use crate::checks::run_checks;
    use crate::claims::build_obligations;
    use crate::contracts::build_contract_ir;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_oblig::{LedgerEntry, WaiverKind};

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn parsed_at(src: &str, name: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from(name);
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn obligations_of(files: &[ParsedFile]) -> Vec<regolith_oblig::Obligation> {
        let snaps = build_entities(files);
        let checks = run_checks(files, &snaps);
        let graph = build_contract_ir(files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        build_obligations(files, &snaps, &checks, &graph, &realized_inputs).obligations
    }

    fn report(src: &str) -> super::WaiverReport {
        report_at(src, "t.hema")
    }

    fn report_at(src: &str, name: &str) -> super::WaiverReport {
        let files = parsed_at(src, name);
        let snaps = build_entities(&files);
        let obl = obligations_of(&files);
        build_ledger(&files, &snaps, &obl)
    }

    // -- D213: import-conformance obligations are addressable ------------

    #[test]
    fn an_import_conformance_obligation_carries_a_real_subject_ref() {
        // ESC-1 regression: the file-level import edge no longer lowers an
        // EMPTY subject_ref (which made it unwaivable AND undischargeable).
        let files = parsed_at(
            "import std.mech (saw_stock)\npart p:\n    mass: 1kg\n",
            "t.hema",
        );
        let import_obl = obligations_of(&files)
            .into_iter()
            .find(|o| o.claim.name.as_deref() == Some("import:std.mech"))
            .expect("import edge lowered a conformance obligation");
        assert!(
            !import_obl.subject_ref.is_empty(),
            "the import obligation carries the import's content address (D213)"
        );
    }

    #[test]
    fn a_memo_backed_import_waiver_matches_and_is_a_listed_deviation() {
        let src = "import std.mech (saw_stock)\npart p:\n    mass: 1kg\n    \
                   waive import(std.mech) on self:\n        \
                   basis: \"module edge has no scalar window, D195.3/D213\"\n        \
                   by doc(memos/release-residuals.md)\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", r.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the import obligation");
        assert!(
            !rec.match_set.is_empty() && rec.match_set.iter().all(|h| !h.is_empty()),
            "INV-12: the match set records the real subject hashes"
        );
        assert!(
            !r.ledger.release_blocked(),
            "an evidence-carrying import waiver is a listed deviation, not a block"
        );
    }

    #[test]
    fn a_bare_import_waiver_matches_but_release_gates() {
        let src = "import std.mech (saw_stock)\npart p:\n    mass: 1kg\n    \
                   waive import(std.mech) on self:\n        basis: \"proto\"\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert!(
            r.ledger.release_blocked(),
            "an evidence-less waiver is release-gated (regolith/12 rule 3)"
        );
    }

    #[test]
    fn a_stale_import_waiver_errors() {
        let src = "import std.mech (saw_stock)\npart p:\n    mass: 1kg\n    \
                   waive import(std.nonexistent) on self:\n        basis: \"typo\"\n";
        let r = report(src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "an import target matching no import edge is stale (INV-12)"
        );
    }

    // -- D215(a): interface-edge (impl/extern/select) obligations -------

    /// A minimal hema part declaring an `impl <Interface> for self` --
    /// its conformance edge lowers an `impl:<Interface>` obligation with
    /// a REAL subject_ref (the enclosing part's snapshot, unlike a bare
    /// import). `tail` is appended to the part body (for the waive).
    fn impl_part(iface: &str, tail: &str) -> String {
        format!(
            "interface {iface}:\n    slot: bolt\npart p:\n    mass: 1kg\n    \
             impl {iface} for self as mount = todo!\n{tail}"
        )
    }

    #[test]
    fn an_impl_conformance_obligation_carries_a_real_subject_ref() {
        // D215(a) precondition: the interface edge keys on the enclosing
        // part's snapshot, so it is addressable AND scope-narrowable
        // (contrast the empty-subject import edge D213 had to fix).
        let files = parsed_at(&impl_part("SparCapMount", ""), "t.hema");
        let impl_obl = obligations_of(&files)
            .into_iter()
            .find(|o| o.claim.name.as_deref() == Some("impl:SparCapMount"))
            .expect("the impl edge lowered a conformance obligation");
        assert!(
            !impl_obl.subject_ref.is_empty(),
            "the impl obligation carries the enclosing part's snapshot (D215)"
        );
    }

    #[test]
    fn a_memo_backed_impl_waiver_matches_and_is_a_listed_deviation() {
        let src = impl_part(
            "SparCapMount",
            "    waive impl(SparCapMount):\n        \
             basis: \"interface edge has no scalar window, D195.3/D215\"\n        \
             by doc(memos/release-residuals.md)\n",
        );
        let r = report(&src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", r.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the impl obligation");
        assert!(
            !rec.match_set.is_empty() && rec.match_set.iter().all(|h| !h.is_empty()),
            "INV-12: the match set records the real subject hashes"
        );
        assert!(
            !r.ledger.release_blocked(),
            "an evidence-carrying impl waiver is a listed deviation, not a block"
        );
    }

    #[test]
    fn a_bare_impl_waiver_matches_but_release_gates() {
        let src = impl_part(
            "BoomMount",
            "    waive impl(BoomMount):\n        basis: \"proto\"\n",
        );
        let r = report(&src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert!(
            r.ledger.release_blocked(),
            "an evidence-less impl waiver is release-gated (regolith/12 rule 3)"
        );
    }

    #[test]
    fn a_stale_impl_waiver_errors() {
        let src = impl_part(
            "BoomMount",
            "    waive impl(NoSuchInterface):\n        basis: \"typo\"\n",
        );
        let r = report(&src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "an impl target matching no interface edge is stale (INV-12)"
        );
    }

    #[test]
    fn an_impl_waiver_matches_a_select_edge_by_interface() {
        // A `by select(...)` binding lowers a `select:<Interface>`
        // conformance edge; `impl(<Interface>)` names the INTERFACE, not
        // the realization kind, so it accepts the select edge too (D215).
        let src = "interface MotorClass:\n    slot: bolt\nboard b:\n    \
                   impl MotorClass by select(a, c)\n    \
                   waive impl(MotorClass):\n        basis: \"candidate list unresolved\"\n        \
                   by doc(memos/release-residuals.md)\n";
        let files = parsed_at(src, "t.cupr");
        let snaps = build_entities(&files);
        let obl = obligations_of(&files);
        assert!(
            obl.iter()
                .any(|o| o.claim.name.as_deref() == Some("select:MotorClass")),
            "the select binding lowered a select-kind conformance edge"
        );
        let r = build_ledger(&files, &snaps, &obl);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", r.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert!(
            !rec.matched.is_empty(),
            "impl(MotorClass) accepted the select:MotorClass edge"
        );
    }

    // -- D215(b): dotted window-half targets ----------------------------

    /// A part whose `require` group carries a `within [lo, hi]` window
    /// claim (`freq`), which lowers to two halves `freq.lo`/`freq.hi`.
    const WINDOW_PART: &str = "part p:\n    require Timing:\n        freq: within [50Hz, 400Hz]\n";

    #[test]
    fn a_window_claim_lowers_dotted_half_obligations() {
        let files = parsed(WINDOW_PART);
        let names: Vec<String> = obligations_of(&files)
            .into_iter()
            .filter_map(|o| o.claim.name)
            .collect();
        assert!(
            names.iter().any(|n| n == "freq.hi") && names.iter().any(|n| n == "freq.lo"),
            "a within-window claim splits into .lo/.hi halves: {names:?}"
        );
    }

    #[test]
    fn a_memo_backed_window_half_waiver_matches_and_is_listed() {
        let src = format!(
            "{WINDOW_PART}    waive Timing.freq.hi:\n        \
             basis: \"upper-band residual, WO ledger\"\n        \
             by doc(memos/release-residuals.md)\n"
        );
        let r = report(&src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", r.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted exactly the .hi half");
        assert!(
            !rec.match_set.is_empty() && rec.match_set.iter().all(|h| !h.is_empty()),
            "INV-12: the match set records the real half's hash"
        );
        assert!(
            !r.ledger.release_blocked(),
            "an evidence-carrying window-half waiver is a listed deviation"
        );
    }

    #[test]
    fn a_bare_window_half_waiver_release_gates() {
        let src = format!("{WINDOW_PART}    waive Timing.freq.lo:\n        basis: \"proto\"\n");
        let r = report(&src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert!(
            r.ledger.release_blocked(),
            "an evidence-less window-half waiver is release-gated"
        );
    }

    #[test]
    fn a_stale_window_half_waiver_errors() {
        let src = format!("{WINDOW_PART}    waive Timing.ghost.hi:\n        basis: \"typo\"\n");
        let r = report(&src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a window-half target matching no half is stale (INV-12)"
        );
    }

    // -- D215(c): flownet-file claims join harvest/match scope ----------

    /// A pure fluorite flownet file: a `flownet` plus a top-level
    /// `require` group whose claims key on the flownet origin. `tail` is
    /// spliced into the require body (the waive).
    fn fluo_file(require_tail: &str) -> String {
        format!(
            "import std.fluorite (Pipe)\n\
             medium Water: liquid\n\
             flownet Loop(medium=Water):\n\
             \x20\x20\x20\x20reference: ambient(101kPa, 293K)\n\
             \x20\x20\x20\x20nodes: src, dst\n\
             \x20\x20\x20\x20edges:\n\
             \x20\x20\x20\x20\x20\x20\x20\x20line: Pipe (src -> dst)\n\
             require Hydronics:\n\
             \x20\x20\x20\x20margin: fluids.dp(src -> dst) <= 45kPa\n\
             {require_tail}"
        )
    }

    #[test]
    fn a_flownet_file_require_waive_is_harvested_and_matches() {
        // D215(c): a `.fluo` file with NO structure previously fell into
        // an unmatched empty scope -- its require-body waivers vanished.
        // The flownet name now joins the match scope, so the waive is
        // harvested and matches the flownet claim by name.
        let src = fluo_file(
            "\x20\x20\x20\x20waive Hydronics.margin:\n\
             \x20\x20\x20\x20\x20\x20\x20\x20basis: \"no fluids.dp model registered, F126 residual\"\n\
             \x20\x20\x20\x20\x20\x20\x20\x20by doc(memos/release-residuals.md)\n",
        );
        let r = report_at(&src, "loop.fluo");
        assert_eq!(
            r.ledger.entries().len(),
            1,
            "the flownet-file require-body waive is harvested"
        );
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", r.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the margin obligation");
        assert!(
            !rec.match_set.is_empty() && rec.match_set.iter().all(|h| !h.is_empty()),
            "INV-12: the match set records the real flownet-claim hash"
        );
        assert!(
            !r.ledger.release_blocked(),
            "an evidence-carrying flownet-file waiver is a listed deviation"
        );
    }

    #[test]
    fn a_stale_flownet_file_waive_errors() {
        let src = fluo_file(
            "\x20\x20\x20\x20waive Hydronics.ghost:\n\
             \x20\x20\x20\x20\x20\x20\x20\x20basis: \"typo\"\n",
        );
        let r = report_at(&src, "loop.fluo");
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a flownet-file target matching no claim is stale (INV-12)"
        );
    }

    // -- D214: grammar-complete harvest ---------------------------------

    /// A minimal calcite frame file with one structure + a top-level
    /// `require` group; `tail` is spliced into the require body.
    fn calx_frame(require_tail: &str) -> String {
        format!(
            "grid width:  A, B spacing 3.0m\n\
             level ground: 0m\n\
             level eave:   3.0m\n\
             member G1: beam\n\
             \x20\x20\x20\x20section:  registry(sawn_150x150)\n\
             \x20\x20\x20\x20material: registry(spf_no1)\n\
             \x20\x20\x20\x20from (A, eave) to (B, eave)\n\
             structure Frame:\n\
             \x20\x20\x20\x20support: FA: footing, FB: footing\n\
             \x20\x20\x20\x20members: G1\n\
             require Structure:\n\
             \x20\x20\x20\x20deflect: mech.deflection(G1, under=std.civil.nds.service) <= G1.span / 240\n\
             {require_tail}"
        )
    }

    #[test]
    fn a_top_level_require_waive_is_harvested_and_matches_the_frame_claim() {
        // D214: a `waive` inside a calcite top-level `require Structure:`
        // body is NOT in a plain `Decl`; the grammar-complete harvest now
        // reaches it and matches the frame obligation by claim name.
        let src = calx_frame(
            "\x20\x20\x20\x20waive Structure.deflect on self:\n\
             \x20\x20\x20\x20\x20\x20\x20\x20basis: \"service-limit residual, WO-74 ledger\"\n\
             \x20\x20\x20\x20\x20\x20\x20\x20by doc(memos/release-residuals.md)\n",
        );
        let r = report_at(&src, "frame.calx");
        assert_eq!(
            r.ledger.entries().len(),
            1,
            "the require-body waive is harvested"
        );
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the deflect obligation");
        assert!(
            !r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a matched frame waive is not stale"
        );
    }

    #[test]
    fn a_structure_body_waive_parses_opaque_and_is_not_harvested_today() {
        // D214 recorded exclusion: `structure-body` grammar routes a waive
        // line to `opaque-stmt`, so it parses as an OpaqueIsland, NOT a
        // WaiveBlock -- the harvest finds ZERO waive nodes there today
        // (this is the precise behavior D214's close-out documents; NOT a
        // grammar change).
        let src = "grid width:  A, B spacing 3.0m\n\
                   level ground: 0m\n\
                   level eave:   3.0m\n\
                   member G1: beam\n\
                   \x20\x20\x20\x20section:  registry(sawn_150x150)\n\
                   \x20\x20\x20\x20material: registry(spf_no1)\n\
                   \x20\x20\x20\x20from (A, eave) to (B, eave)\n\
                   structure Frame:\n\
                   \x20\x20\x20\x20support: FA: footing\n\
                   \x20\x20\x20\x20members: G1\n\
                   \x20\x20\x20\x20waive Structure.deflect on self:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20basis: \"in a structure body\"\n";
        let r = report_at(src, "frame.calx");
        assert!(
            r.ledger.entries().is_empty(),
            "a structure-body waive parses opaque today, so nothing is harvested"
        );
    }

    #[test]
    fn a_matching_claim_waiver_is_recorded_matched() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        basis: \"proto lot\"\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert_eq!(rec.matched.len(), 1, "accepted the yield obligation");
        assert!(r.diagnostics.is_empty(), "a matching waiver is clean");
    }

    #[test]
    fn a_waiver_naming_a_lint_code_is_rejected_not_recorded() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive L0801 on self:\n        basis: \"nope\"\n";
        let r = report(src);
        assert!(
            r.ledger.entries().is_empty(),
            "a waive naming a lint code is never recorded as an acceptance"
        );
        assert_eq!(r.diagnostics.len(), 1);
        assert_eq!(r.diagnostics[0].code, super::codes::WAIVE_NAMES_LINT_CODE);
    }

    #[test]
    fn a_claim_waiver_matching_nothing_is_stale() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.ghost on self:\n        basis: \"typo\"\n";
        let r = report(src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a claim target matching nothing must be a stale diagnostic"
        );
    }

    #[test]
    fn a_rule_pack_waiver_is_deferred_not_stale() {
        // The static core lowers no dfm obligations, so a dfm waiver is
        // recorded (release-gated) but NEVER falsely stale.
        let src = "part p:\n    waive dfm(min_web) on milled.wall:\n        basis: \"qual unit\"\n        by test(vr081)\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::DeferredRulePack);
        assert!(rec.waiver.evidence.is_some(), "the `by` clause is evidence");
        assert!(
            !r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a rule-pack waiver is not stale"
        );
    }

    #[test]
    fn a_basis_less_waiver_is_an_overreach_diagnostic() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        note: \"no basis here\"\n";
        let r = report(src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::WAIVER_MISSING_BASIS),
            "a waiver without basis must be rejected (INV-2 overreach)"
        );
        assert!(
            r.ledger.entries().is_empty(),
            "a rejected waiver is not recorded as an acceptance"
        );
    }

    #[test]
    fn a_waiver_never_changes_the_obligation_set() {
        // INV-2 ladder safety: the obligations are byte-identical with
        // and without the waiver -- the waiver adds only a ledger entry.
        let with = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        basis: \"ok\"\n";
        let without = "part p:\n    require Strength:\n        yield: >= 200\n";
        let files_w = parsed(with);
        let snaps_w = build_entities(&files_w);
        let checks_w = run_checks(&files_w, &snaps_w);
        let graph_w = build_contract_ir(&files_w, &snaps_w);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obl_w = build_obligations(&files_w, &snaps_w, &checks_w, &graph_w, &realized_inputs)
            .obligations;

        let files_n = parsed(without);
        let snaps_n = build_entities(&files_n);
        let checks_n = run_checks(&files_n, &snaps_n);
        let graph_n = build_contract_ir(&files_n, &snaps_n);
        let obl_n = build_obligations(&files_n, &snaps_n, &checks_n, &graph_n, &realized_inputs)
            .obligations;

        assert_eq!(
            obl_w, obl_n,
            "declaring a waiver must not alter any obligation (INV-2)"
        );
    }

    /// WO-28 deliverable 4: the violated-rule -> waive -> release
    /// ladder, end to end through the existing machinery (nothing new
    /// to learn, nothing bypassed).
    const VIOLATED_RULE: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            why: \"press pack minimum inside radius\"\npart p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n";

    fn rule_report(waive_tail: &str) -> (super::WaiverReport, Vec<regolith_oblig::Obligation>) {
        let src = format!("{VIOLATED_RULE}{waive_tail}");
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        (report, obligations)
    }

    #[test]
    fn a_violated_rule_lowers_a_waivable_obligation() {
        let (_, obligations) = rule_report("");
        let rule_obl = obligations
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("dfm(sheet_metal.min_bend_radius)"))
            .expect("violated rule lowered to an obligation");
        assert!(
            rule_obl
                .given
                .refs
                .iter()
                .any(|(origin, detail)| origin == "flange" && detail.starts_with("violated:")),
            "{:?}",
            rule_obl.given.refs
        );
    }

    #[test]
    fn a_basis_less_rule_waiver_is_rejected_not_recorded() {
        let (report, _) = rule_report(
            "part q:\n    waive dfm(sheet_metal.min_bend_radius) on p.flange:\n        note: \"no basis\"\n",
        );
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::WAIVER_MISSING_BASIS));
    }

    #[test]
    fn an_evidence_less_rule_waiver_matches_and_release_gates() {
        // The waive is declared in the SAME decl whose obligation it
        // accepts (subject_ref scoping).
        let src = VIOLATED_RULE.replace(
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n",
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n    waive dfm(sheet_metal.min_bend_radius) on formed.flange:\n        basis: \"prototype lot only, EV-31\"\n",
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        let LedgerEntry::Waived(rec) = &report.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", report.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the rule obligation");
        assert!(
            report.ledger.release_blocked(),
            "an evidence-less waiver is release-gated (regolith/12 rule 3)"
        );
        // The unqualified corpus spelling matches the same obligation.
        let src2 = src.replace(
            "waive dfm(sheet_metal.min_bend_radius)",
            "waive dfm(min_bend_radius)",
        );
        let files2 = parsed(&src2);
        let snaps2 = build_entities(&files2);
        let checks2 = run_checks(&files2, &snaps2);
        let graph2 = build_contract_ir(&files2, &snaps2);
        let obligations2 =
            build_obligations(&files2, &snaps2, &checks2, &graph2, &realized_inputs).obligations;
        let report2 = build_ledger(&files2, &snaps2, &obligations2);
        let LedgerEntry::Waived(rec2) = &report2.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(
            rec2.kind,
            WaiverKind::Matched,
            "unqualified spelling matches"
        );
    }

    #[test]
    fn an_evidence_carrying_rule_waiver_is_a_listed_deviation() {
        let src = VIOLATED_RULE.replace(
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n",
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n    waive dfm(sheet_metal.min_bend_radius) on formed.flange:\n        basis: \"qualified by test, EV-32\"\n        by test(vr090)\n"
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        let LedgerEntry::Waived(rec) = &report.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert!(rec.waiver.evidence.is_some(), "the `by` clause is evidence");
        assert!(
            !report.ledger.release_blocked(),
            "an evidence-carrying waiver is a listed deviation, not a release block"
        );
    }
}
