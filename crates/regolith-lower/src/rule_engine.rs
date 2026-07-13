//! The WO-28 rule-pack engine core: pack index, attachment resolution,
//! the binding environment, and the deliberately-narrow demand
//! evaluator shared by every consumer -- `resolves:` eager resolution
//! (`entities.rs`), static-rule evaluation (`rules.rs`, E0601/E0604),
//! rule-obligation lowering (`claims.rs`), and the `rules test|try`
//! CLI runners (`regolith-api`). One evaluator, many callers (NO
//! DUPLICATION): a demand means the same thing at check time, at
//! resolve time, and in an `expect:` fixture.
//!
//! Regolith reference: `docs/implementation/design/21-rule-packs.md`
//! (D-B quantified claim templates, D-C attachment/union, D-E derived
//! discharge level), hematite/02 sec. 10 (the settled grammar), AD-21.
//!
//! ## What the evaluator models (and what it defers)
//!
//! The expression grammar is the quantity-core comparison subset:
//! `<expr> <cmp> <expr>` with `+ - * /`, parentheses, unit-suffixed
//! literals (`2.4mm`, dimension-checked through `regolith-qty`),
//! `<var>.<field>` entity-measure references, `capability.<key>` pack
//! table references, bare-identifier design facts, and the `true` /
//! `false` literals. Anything OUTSIDE that subset -- aggregate calls
//! (`sum(...)`, `spread(...)`), registry-record dereference chains,
//! `.where(...)` query filters, range-valued capability entries -- is
//! an [`EvalError`], which the caller turns into an HONEST DEFERRAL
//! (an obligation naming the unevaluable term, D-E), never a silent
//! pass and never an invented verdict.
//!
//! ## Bare-identifier binding order (engine semantics, this WO)
//!
//! A bare identifier in a demand (`thickness`, `sheet`) binds to the
//! CONSUMING declaration's facts, searched in this order:
//!
//! 1. the declaration's own direct fields (`material: AISI_304`);
//! 2. its stage process-call keyword arguments, in stage source order
//!    (`stage cut: process=laser_cut(sheet=1.5mm)` binds `sheet`);
//! 3. the owning pack's SCALAR `capability:` entries (a range-valued
//!    entry is an envelope, not a design fact -- it never binds).
//!
//! Unresolvable terms defer the rule for that entity. The order is
//! documented in `docs/guide/03-writing-dfm-rules.md` sec. 2a.

use camino::Utf8PathBuf;
use regolith_qty::{Qty, Unit};
use regolith_sem::{Entity, EntityKind, Measures};
use regolith_syntax::ast::{AstNode, Decl, File};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_util::IndexMap;

use crate::output::ParsedFile;

/// One rule lifted off the typed `RuleDecl` CST into plain data the
/// engine and the CLI runners evaluate without re-walking the tree.
#[derive(Debug, Clone)]
pub struct RuleDef {
    /// The owning pack's (possibly dotted) name.
    pub pack: String,
    /// The rule's own name.
    pub name: String,
    /// The pack-block family word: `dfm`, `drc`, or `erc`.
    pub family: String,
    /// The `forall` bound variable, when quantified.
    pub forall_var: Option<String>,
    /// The `forall` query text (verbatim; empty when unquantified).
    pub query_text: String,
    /// The query's base-word domain kind, when quantified.
    pub domain_kind: Option<EntityKind>,
    /// True when the query carries a tail beyond the base word
    /// (`.where(...)` etc.) -- statically unevaluable, defers (D-E).
    pub has_query_tail: bool,
    /// The `demand:` expression text (error severity), if present.
    pub demand: Option<String>,
    /// The `advise:` expression text (warning severity), if present.
    pub advise: Option<String>,
    /// The `per:` citation, if present.
    pub per: Option<String>,
    /// The `why:` explanation, if present.
    pub why: Option<String>,
    /// The `resolves: <var>.<field> from free` target, split at the
    /// first dot, when the rule is an eager resolver.
    pub resolves: Option<(String, String)>,
    /// The `expect:` fixtures: (verdict word, fixture text).
    pub expect: Vec<(String, String)>,
    /// The declaring file (for diagnostics).
    pub file: Utf8PathBuf,
    /// The rule decl's byte range in `file`.
    pub range: (usize, usize),
}

impl RuleDef {
    /// The citable qualified name (`pack.rule`) waives, causes, and
    /// E06xx provenance all use.
    #[must_use]
    pub fn qualified(&self) -> String {
        format!("{}.{}", self.pack, self.name)
    }

    /// The waive-target spelling of this rule (`dfm(pack.rule)`), also
    /// used as the lowered obligation's claim name so the waive ladder
    /// matches rule obligations with zero new machinery (D-D).
    #[must_use]
    pub fn claim_name(&self) -> String {
        format!("{}({})", self.family, self.qualified())
    }
}

/// One `process` pack: its capability table and rules.
#[derive(Debug, Clone)]
pub struct PackDef {
    /// The pack's declared name (dotted names supported).
    pub name: String,
    /// The `capability:` table entries (name -> value text).
    pub capability: IndexMap<String, String>,
    /// The pack's rules, in source order across its rule blocks.
    pub rules: Vec<RuleDef>,
    /// The declaring file.
    pub file: Utf8PathBuf,
}

/// Every `process` pack in the session, by name, in file-then-source
/// order (AD-6). Collisions of whole PACK names keep the first decl
/// (rule-level E0602 collisions are `rules.rs`'s check).
#[derive(Debug, Clone, Default)]
pub struct PackIndex {
    packs: IndexMap<String, PackDef>,
}

impl PackIndex {
    /// Build the index from every parsed file's `process` decls.
    /// Poisoned decls are skipped (INV-20 gating, as everywhere).
    #[must_use]
    pub fn build(files: &[ParsedFile]) -> PackIndex {
        let mut packs: IndexMap<String, PackDef> = IndexMap::new();
        for pf in files {
            let Some(file) = File::cast(pf.parse.syntax()) else {
                continue;
            };
            for decl in file.decls() {
                if crate::entities::decl_is_poisoned(&decl) {
                    continue;
                }
                let Some(pack_name) = decl.process_name() else {
                    continue;
                };
                let def = pack_def_from_decl(&decl, &pack_name, &pf.path);
                if packs.contains_key(&pack_name) {
                    tracing::debug!(
                        pack = %pack_name,
                        file = %pf.path,
                        "duplicate process pack name; keeping the first decl \
                         (rule-level collisions are E0602's check)"
                    );
                    continue;
                }
                tracing::debug!(
                    pack = %pack_name,
                    rules = def.rules.len(),
                    capability_entries = def.capability.len(),
                    "indexed process pack"
                );
                packs.insert(pack_name, def);
            }
        }
        PackIndex { packs }
    }

    /// Look up a pack by name.
    #[must_use]
    pub fn get(&self, name: &str) -> Option<&PackDef> {
        self.packs.get(name)
    }

    /// Every indexed pack, in index (file-then-source) order.
    pub fn iter(&self) -> impl Iterator<Item = &PackDef> {
        self.packs.values()
    }

    /// True when no packs were declared.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.packs.is_empty()
    }

    /// The packs a consuming declaration attaches, in stage source
    /// order, deduplicated (D-C level 1: `process=<head>(args)` on a
    /// stage attaches the pack named by the HEAD or by any bare
    /// dotted-identifier ARGUMENT -- `process=pcb_fab(jlc_2l)` attaches
    /// `jlc_2l`; `process=sheet_metal` attaches `sheet_metal`).
    #[must_use]
    pub fn attached_to<'a>(&'a self, decl: &Decl) -> Vec<&'a PackDef> {
        let mut seen: Vec<String> = Vec::new();
        let mut out = Vec::new();
        for candidate in process_ref_candidates(decl) {
            if seen.contains(&candidate) {
                continue;
            }
            if let Some(def) = self.packs.get(&candidate) {
                tracing::debug!(
                    decl = %decl.name().unwrap_or_default(),
                    pack = %candidate,
                    "attached rule pack via stage process= reference"
                );
                seen.push(candidate);
                out.push(def);
            }
        }
        out
    }
}

/// Lift a `process` decl into a [`PackDef`].
fn pack_def_from_decl(decl: &Decl, pack_name: &str, path: &Utf8PathBuf) -> PackDef {
    let mut capability = IndexMap::new();
    if let Some(cap) = decl.capability() {
        for entry in cap.entries() {
            if let Some(value) = field_value_text_or_rhs(&entry) {
                capability.insert(entry.name(), value);
            }
        }
    }

    let mut rules = Vec::new();
    for pack in decl.rule_packs() {
        let family = pack.family().unwrap_or_default();
        for rule in pack.rules() {
            let Some(name) = rule.name() else {
                tracing::debug!(pack = %pack_name, "unnamed rule skipped by the engine");
                continue;
            };
            let forall = rule.forall();
            let forall_var = forall
                .as_ref()
                .and_then(regolith_syntax::ast::ForallClause::var);
            let query_text = forall
                .as_ref()
                .map(regolith_syntax::ast::ForallClause::query_text)
                .unwrap_or_default();
            let (base_word, has_query_tail) = split_query_base(&query_text);
            let domain_kind = forall
                .is_some()
                .then(|| EntityKind::from_kind_word(&base_word));
            let resolves = rule.resolves().map(|r| {
                let target = r.target();
                match target.split_once('.') {
                    Some((var, field)) => (var.to_string(), field.to_string()),
                    None => (String::new(), target),
                }
            });
            let expect = rule
                .expect()
                .map(|block| {
                    block
                        .cases()
                        .iter()
                        .map(|case| {
                            (
                                case.verdict().unwrap_or_default(),
                                case.fixture()
                                    .map(|f| f.text().to_string())
                                    .unwrap_or_default(),
                            )
                        })
                        .collect()
                })
                .unwrap_or_default();
            let range = rule.syntax().text_range();
            rules.push(RuleDef {
                pack: pack_name.to_string(),
                name,
                family: family.clone(),
                forall_var,
                query_text,
                domain_kind,
                has_query_tail,
                demand: rule.demand().and_then(|f| field_value_text_or_rhs(&f)),
                advise: rule.advise().and_then(|f| field_value_text_or_rhs(&f)),
                per: rule.per(),
                why: rule.why(),
                resolves,
                expect,
                file: path.clone(),
                range: (range.start().into(), range.end().into()),
            });
        }
    }

    PackDef {
        name: pack_name.to_string(),
        capability,
        rules,
        file: path.clone(),
    }
}

/// A `Field`'s value text: the raw text after the first `:` on the
/// field's first line, with any trailing `#` comment stripped (the
/// full spelled expression -- a typed value
/// NODE can be both absent for bare literals like `1.6` and PARTIAL
/// for multi-token expressions; the same colon-RHS stance as
/// `claim_scope::field_colon_rhs_text`), falling back to the typed
/// value node's text. `None` when both are empty.
fn field_value_text_or_rhs(field: &regolith_syntax::ast::Field) -> Option<String> {
    let full = field.syntax().text().to_string();
    let first_line = full.lines().next().unwrap_or("");
    let first_line = first_line.split('#').next().unwrap_or("");
    if let Some((_, rhs)) = first_line.split_once(':') {
        let rhs = rhs.trim();
        if !rhs.is_empty() {
            return Some(rhs.to_string());
        }
    }
    field
        .value()
        .map(|v| v.text().to_string().trim().to_string())
        .filter(|t| !t.is_empty())
}

/// WO-112 Class 5: is this domain kind populated only by a REALIZED
/// input (never by declared topology)? An empty match on one of these
/// means "not yet realized", so the rule defers instead of vacuously
/// passing (see `evaluate_pack_for_decl_with_registry`). ONE home for
/// the set; grows as further realized-tier domains land (vias, buses
/// -- WO112-F4/F5 escalations).
fn is_realized_tier_domain(kind: &EntityKind) -> bool {
    matches!(kind, EntityKind::Other(word) if word == "traces")
}

/// Resolve one quantified rule's domain to the entities it evaluates
/// over, or `None` after recording why evaluation stops (the caller
/// then commits the evaluation as-is). Deferral cases, each recorded
/// on `eval` by name (INV-29: never a silent skip):
///
/// - an UNMODELED domain word (no measure vocabulary) defers whole;
/// - a REALIZED-tier domain (`traces`) with no entities defers whole
///   -- "not yet realized at this tier" is not a vacuous pass (WO-112
///   Class 5), unlike a declared domain's genuinely-empty match (a
///   part with no bends has nothing to relieve);
/// - a `.where(<field>=<word>)` equality tail filters by measure
///   equality (WO-112 Class 5), deferring any entity that does not
///   carry the filter field (excluding it silently could skip a
///   violation); any OTHER tail shape keeps the pre-existing honest
///   whole-rule deferral, but only where the base domain has entities
///   at all.
fn select_domain_entities<'a>(
    rule: &RuleDef,
    kind: &EntityKind,
    entities: Option<&'a regolith_sem::EntityDb>,
    eval: &mut RuleEvaluation,
) -> Option<Vec<&'a Entity>> {
    if kind.known_measure_keys().is_none() {
        eval.deferrals.push((
            "<rule>".to_string(),
            format!("domain `{}` (unpopulated)", rule.query_text),
        ));
        return None;
    }
    let matched: Vec<&Entity> = entities
        .map(|db| db.iter().filter(|e| &e.kind == kind).collect())
        .unwrap_or_default();
    if matched.is_empty() && is_realized_tier_domain(kind) {
        eval.deferrals.push((
            "<rule>".to_string(),
            format!(
                "domain `{}` awaits a realized layout \
                 (no layout.realized input at this tier)",
                rule.query_text
            ),
        ));
        return None;
    }
    if !rule.has_query_tail {
        return Some(matched);
    }
    let Some((field, want)) = parse_where_equality(&rule.query_text) else {
        if !matched.is_empty() {
            eval.deferrals.push((
                "<rule>".to_string(),
                format!("query filter `{}`", rule.query_text),
            ));
        }
        return None;
    };
    let mut kept: Vec<&Entity> = Vec::new();
    for entity in matched {
        match entity.measures.get(&field) {
            Some(value) if *value == want => kept.push(entity),
            Some(_) => {}
            None => {
                eval.deferrals.push((
                    entity.origin.clone(),
                    format!("filter field `{field}` unpopulated on this entity"),
                ));
            }
        }
    }
    Some(kept)
}

/// WO-112 Class 5: parse a simple `.where(<field>=<word>)` equality
/// tail off a `forall` query (`exposed_connectors.where(class=power)`
/// -> `("class", "power")`). Returns `None` for any other tail shape
/// (chained filters, comparators, quoted values) -- those keep the
/// pre-existing honest whole-rule deferral, never a guessed filter.
fn parse_where_equality(query: &str) -> Option<(String, String)> {
    let (base, has_tail) = split_query_base(query);
    if !has_tail {
        return None;
    }
    let tail = query[base.len()..].trim();
    let inner = tail.strip_prefix(".where(")?.strip_suffix(')')?;
    let (field, value) = inner.split_once('=')?;
    let is_word =
        |s: &str| !s.is_empty() && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
    let (field, value) = (field.trim(), value.trim());
    if !is_word(field) || !is_word(value) {
        return None;
    }
    Some((field.to_string(), value.to_string()))
}

/// Split a query text into its leading base word and whether anything
/// follows it (`bends.where(...)` -> (`bends`, true); `holes` ->
/// (`holes`, false)).
fn split_query_base(query: &str) -> (String, bool) {
    let base: String = query
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect();
    let tail = query[base.len()..].trim();
    (base, !tail.is_empty())
}

/// Every `process=<head>(args)` reference candidate in a declaration's
/// stage statements: the head name plus every bare dotted-identifier
/// argument, in source order.
fn process_ref_candidates(decl: &Decl) -> Vec<String> {
    let mut out = Vec::new();
    for node in decl.syntax().descendants() {
        if node.kind() != SyntaxKind::StageStmt {
            continue;
        }
        // Only the stage HEADER carries `process=`; then:-scope bodies
        // below it never do. The header's argument list may WRAP over
        // continuation lines (the board_correctness attachment shape:
        // `process=board_correctness(\n    pdn_decoupling, ...)`) --
        // the parser ends the `StageStmt` at the newline and sweeps the
        // continuation into sibling `OpaqueIsland` nodes, so when the
        // header's paren is unclosed the scan appends following opaque
        // siblings until it closes (WO-87: the hazard/fixed corpus
        // boards spell exactly this).
        let mut text = node.text().to_string();
        if text.contains("process=") && text.contains('(') && !text.contains(')') {
            let mut sibling = node.next_sibling();
            while let Some(sib) = sibling {
                if sib.kind() != SyntaxKind::OpaqueIsland {
                    break;
                }
                text.push_str(&sib.text().to_string());
                if text.contains(')') {
                    break;
                }
                sibling = sib.next_sibling();
            }
        }
        let Some(after) = text.split_once("process=").map(|(_, a)| a) else {
            continue;
        };
        let head: String = after
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '.')
            .collect();
        if !head.is_empty() {
            out.push(head.clone());
        }
        // Bare identifier args inside the immediate `(...)`, spanning
        // continuation lines up to the close paren.
        let rest = &after[head.len()..];
        if let Some(args) = rest.strip_prefix('(') {
            let inner = args.split(')').next().unwrap_or("");
            for arg in inner.split(',') {
                let arg = arg.trim();
                if arg.is_empty() || arg.contains('=') {
                    continue;
                }
                if arg
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
                {
                    out.push(arg.to_string());
                }
            }
        }
    }
    out
}

/// The bare-identifier binding environment of one consuming
/// declaration (see the module doc's binding order: decl fields first,
/// then stage process kwargs).
#[derive(Debug, Clone, Default)]
pub struct BindingEnv {
    bindings: IndexMap<String, String>,
}

impl BindingEnv {
    /// Build the environment for `decl` (without the pack capability
    /// tier -- that is per-pack, applied at lookup time by the caller
    /// passing the owning pack's table to [`EvalCtx`]).
    #[must_use]
    pub fn for_decl(decl: &Decl) -> BindingEnv {
        let mut bindings = IndexMap::new();
        // Tier 1: the decl's own direct fields.
        for field in decl.fields() {
            if let Some(value) = field.value() {
                bindings
                    .entry(field.name())
                    .or_insert_with(|| value.text().to_string());
            }
        }
        // Tier 2: stage process-call kwargs, stage source order.
        for node in decl.syntax().descendants() {
            if node.kind() != SyntaxKind::StageStmt {
                continue;
            }
            let text = node.text().to_string();
            let Some(header) = text.lines().next() else {
                continue;
            };
            let Some(after) = header.split_once("process=").map(|(_, a)| a) else {
                continue;
            };
            let Some(open) = after.find('(') else {
                continue;
            };
            let inner = after[open + 1..].split(')').next().unwrap_or("");
            for arg in inner.split(',') {
                if let Some((key, value)) = arg.split_once('=') {
                    let key = key.trim().to_string();
                    let value = value.trim().to_string();
                    if !key.is_empty() && !value.is_empty() {
                        bindings.entry(key).or_insert(value);
                    }
                }
            }
        }
        BindingEnv { bindings }
    }

    /// Build an environment directly from `name=value` pairs (the
    /// `expect:` fixture runner's synthetic facts).
    #[must_use]
    pub fn from_pairs(pairs: &[(String, String)]) -> BindingEnv {
        let mut bindings = IndexMap::new();
        for (k, v) in pairs {
            bindings.entry(k.clone()).or_insert_with(|| v.clone());
        }
        BindingEnv { bindings }
    }

    /// Look up a bare identifier's bound value text.
    #[must_use]
    pub fn get(&self, name: &str) -> Option<&str> {
        self.bindings.get(name).map(String::as_str)
    }
}

/// Why an expression could not be evaluated -- the honest-deferral
/// reasons (D-E). These are DATA the caller lowers into a deferred
/// obligation naming the term, never a panic.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EvalError {
    /// A term is not bound by any layer (entity measure absent, bare
    /// ident unbound, capability key missing) -- a realized/unavailable
    /// fact. Carries the term's spelling.
    Unbound(String),
    /// A term is bound but its value text is not a parseable scalar
    /// quantity (a range, `free`, prose). Carries term and value.
    Unparseable(String, String),
    /// The expression uses a shape outside the modeled subset
    /// (aggregate call, `==`, query tail). Carries the shape.
    Unsupported(String),
    /// Dimension mismatch in comparison or additive arithmetic.
    Dimension(String),
}

impl EvalError {
    /// The missing/blocking fact this error names, for `given.refs`.
    #[must_use]
    pub fn fact(&self) -> String {
        match self {
            EvalError::Unbound(t)
            | EvalError::Unparseable(t, _)
            | EvalError::Unsupported(t)
            | EvalError::Dimension(t) => t.clone(),
        }
    }
}

/// A demand's evaluated verdict.
#[derive(Debug, Clone, PartialEq)]
pub struct Verdict {
    /// Whether the demand holds.
    pub holds: bool,
    /// Relative margin `|lhs - rhs| / |rhs|` (in rhs units), when the
    /// demand was a comparison over nonzero rhs; drives the `rules try`
    /// near-miss report (within 20% = near miss, guide sec. 3).
    pub margin: Option<f64>,
    /// Rendered `lhs op rhs` values (SI magnitudes) for diagnostics.
    pub detail: String,
}

/// The evaluation context: the owning pack's capability table, the
/// consuming decl's binding environment, and (when quantified) the
/// bound variable + the matched entity's measures.
pub struct EvalCtx<'a> {
    /// The owning pack's `capability:` table.
    pub capability: &'a IndexMap<String, String>,
    /// The consuming decl's bare-identifier bindings.
    pub env: &'a BindingEnv,
    /// The `forall` variable, when evaluating against an entity.
    pub var: Option<&'a str>,
    /// The matched entity's measures, when evaluating against one.
    pub measures: Option<&'a Measures>,
    /// The registry-records payload (WO-87/D198) -- the ONE rule-eval
    /// record-dereference seam: a `<var>.<field>` term whose field is
    /// not an entity measure resolves through the entity's `record`
    /// measure into the loaded record's fields (`x.cl` on a crystal
    /// entity -> its record's `cl_pf`), and an absolute
    /// `registry.<key>.<field>` path reads a named record directly.
    /// `None` outside a build with a records payload (`expect:`
    /// fixtures, the `resolves:` solver) -- those terms then defer
    /// honestly as before.
    pub registry: Option<&'a crate::registry::RegistryRecords>,
}

/// Evaluate a demand/advise expression to a [`Verdict`].
///
/// # Errors
/// [`EvalError`] when a term is unbound/unparseable or the expression
/// uses an unmodeled shape -- the caller's honest-deferral signal.
pub fn eval_demand(text: &str, ctx: &EvalCtx<'_>) -> Result<Verdict, EvalError> {
    let trimmed = text.trim();
    match trimmed {
        "true" => {
            return Ok(Verdict {
                holds: true,
                margin: None,
                detail: "true".to_string(),
            })
        }
        "false" => {
            return Ok(Verdict {
                holds: false,
                margin: None,
                detail: "false".to_string(),
            })
        }
        _ => {}
    }

    let (lhs_text, op, rhs_text) =
        split_comparison(trimmed).ok_or_else(|| EvalError::Unsupported(trimmed.to_string()))?;
    if op == "==" {
        // INV-17: exact equality on continuous quantities is banned
        // language-wide; a rule spelling it is outside the subset.
        return Err(EvalError::Unsupported(format!("`==` in `{trimmed}`")));
    }
    let lhs = eval_expr(lhs_text, ctx)?;
    let rhs = eval_expr(rhs_text, ctx)?;

    let diff = lhs
        .sub(&rhs)
        .map_err(|e| EvalError::Dimension(format!("`{trimmed}`: {e}")))?;
    // Relative tolerance absorbs float noise from unit-scale round
    // trips (1.6 * 1.5mm vs a resolved 2.4mm differs in the last ulp):
    // inclusive comparators hold AT the bound; strict ones do not.
    let tol = 1e-9 * lhs.magnitude().abs().max(rhs.magnitude().abs());
    let holds = match op {
        ">=" => diff.magnitude() >= -tol,
        ">" => diff.magnitude() > tol,
        "<=" => diff.magnitude() <= tol,
        "<" => diff.magnitude() < -tol,
        _ => return Err(EvalError::Unsupported(format!("`{op}`"))),
    };
    let margin = (rhs.magnitude() != 0.0).then(|| (diff.magnitude() / rhs.magnitude()).abs());
    let detail = format!("{} {} {}", render_qty(&lhs), op, render_qty(&rhs));
    Ok(Verdict {
        holds,
        margin,
        detail,
    })
}

/// Solve a `resolves:` demand for its target term: for a demand of the
/// shape `<var>.<field> <cmp> <expr>` (the target alone on one side),
/// the cheapest legal value is the evaluated other side (a `>=`/`>`
/// lower bound resolves AT the bound -- regolith/03's "process-rule
/// minimum"; `<=`/`<` symmetrically at the upper bound).
///
/// # Errors
/// [`EvalError`] when the demand is not in the solvable shape or its
/// bound side does not evaluate.
pub fn solve_resolves(
    demand: &str,
    target_var: &str,
    target_field: &str,
    ctx: &EvalCtx<'_>,
) -> Result<Qty, EvalError> {
    let (lhs_text, op, rhs_text) = split_comparison(demand.trim())
        .ok_or_else(|| EvalError::Unsupported(demand.trim().to_string()))?;
    let target = format!("{target_var}.{target_field}");
    let bound_side = if lhs_text.trim() == target {
        rhs_text
    } else if rhs_text.trim() == target {
        lhs_text
    } else {
        return Err(EvalError::Unsupported(format!(
            "resolves target `{target}` is not alone on one side of `{demand}`"
        )));
    };
    if op == "==" {
        return Err(EvalError::Unsupported(format!("`==` in `{demand}`")));
    }
    eval_expr(bound_side, ctx)
}

/// Render a `Qty` compactly (`2.4mm`), normalizing composed
/// dimensionless symbol factors (`1.mm` -> `mm`) so a resolved measure
/// re-parses through the same literal grammar that produced it.
#[must_use]
pub fn render_qty(q: &Qty) -> String {
    let symbol = normalize_symbol(&q.unit().symbol);
    let mut s = format!("{:.9}", q.magnitude());
    if s.contains('.') {
        while s.ends_with('0') {
            s.pop();
        }
        if s.ends_with('.') {
            s.pop();
        }
    }
    if symbol == "1" {
        s
    } else {
        format!("{s}{symbol}")
    }
}

/// Round-trip a computed quantity through its rendered text
/// ([`render_qty`]) so arithmetic float noise and composed unit
/// symbols (`1.mm`) normalize to the clean literal form (`2.4mm`) the
/// lockfile and rewritten measures store. Falls back to the input when
/// the render is not re-lexable (never invents a value).
#[must_use]
pub fn normalize_qty(q: &Qty) -> Qty {
    let rendered = render_qty(q);
    match lex_qty_literal(&rendered) {
        Some((clean, consumed)) if rendered[consumed..].is_empty() => clean,
        _ => q.clone(),
    }
}

/// Drop dimensionless `1` factors from a `.`-composed unit symbol
/// (`1.mm` -> `mm`). Symbols containing `/` are left untouched (their
/// factors are not simply droppable).
fn normalize_symbol(symbol: &str) -> String {
    if symbol.contains('/') {
        return symbol.to_string();
    }
    let kept: Vec<&str> = symbol.split('.').filter(|s| *s != "1").collect();
    if kept.is_empty() {
        "1".to_string()
    } else {
        kept.join(".")
    }
}

/// Split a comparison expression at its top-level comparator.
#[must_use]
pub fn split_comparison(text: &str) -> Option<(&str, &str, &str)> {
    let mut depth = 0usize;
    let bytes = text.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        match bytes[i] {
            b'(' | b'[' => depth += 1,
            b')' | b']' => depth = depth.saturating_sub(1),
            b'<' | b'>' if depth == 0 => {
                let (op_len, op) = if bytes.get(i + 1) == Some(&b'=') {
                    (2, &text[i..i + 2])
                } else {
                    (1, &text[i..=i])
                };
                return Some((&text[..i], op, &text[i + op_len..]));
            }
            b'=' if depth == 0 && bytes.get(i + 1) == Some(&b'=') => {
                return Some((&text[..i], "==", &text[i + 2..]));
            }
            _ => {}
        }
        i += 1;
    }
    None
}

/// Evaluate an arithmetic expression (sum of products of atoms) to a
/// quantity.
fn eval_expr(text: &str, ctx: &EvalCtx<'_>) -> Result<Qty, EvalError> {
    let mut parser = ExprParser {
        text: text.trim(),
        pos: 0,
        ctx,
    };
    let value = parser.parse_sum()?;
    parser.skip_ws();
    if parser.pos < parser.text.len() {
        return Err(EvalError::Unsupported(format!(
            "trailing `{}` in `{}`",
            &parser.text[parser.pos..],
            text.trim()
        )));
    }
    Ok(value)
}

/// A tiny recursive-descent parser over the modeled expression subset.
struct ExprParser<'a> {
    text: &'a str,
    pos: usize,
    ctx: &'a EvalCtx<'a>,
}

impl ExprParser<'_> {
    fn skip_ws(&mut self) {
        while self.text[self.pos..].starts_with(' ') {
            self.pos += 1;
        }
    }

    fn peek(&self) -> Option<char> {
        self.text[self.pos..].chars().next()
    }

    fn parse_sum(&mut self) -> Result<Qty, EvalError> {
        let mut acc = self.parse_prod()?;
        loop {
            self.skip_ws();
            match self.peek() {
                Some('+') => {
                    self.pos += 1;
                    let rhs = self.parse_prod()?;
                    acc = acc
                        .add(&rhs)
                        .map_err(|e| EvalError::Dimension(e.to_string()))?;
                }
                Some('-') => {
                    self.pos += 1;
                    let rhs = self.parse_prod()?;
                    acc = acc
                        .sub(&rhs)
                        .map_err(|e| EvalError::Dimension(e.to_string()))?;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn parse_prod(&mut self) -> Result<Qty, EvalError> {
        let mut acc = self.parse_atom()?;
        loop {
            self.skip_ws();
            match self.peek() {
                Some('*') => {
                    self.pos += 1;
                    let rhs = self.parse_atom()?;
                    acc = acc
                        .mul(&rhs)
                        .map_err(|e| EvalError::Dimension(e.to_string()))?;
                }
                Some('/') => {
                    self.pos += 1;
                    let rhs = self.parse_atom()?;
                    acc = acc
                        .div(&rhs)
                        .map_err(|e| EvalError::Dimension(e.to_string()))?;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn parse_atom(&mut self) -> Result<Qty, EvalError> {
        self.skip_ws();
        match self.peek() {
            Some('(') => {
                self.pos += 1;
                let inner = self.parse_sum()?;
                self.skip_ws();
                if self.peek() == Some(')') {
                    self.pos += 1;
                    Ok(inner)
                } else {
                    Err(EvalError::Unsupported(format!(
                        "unbalanced parenthesis in `{}`",
                        self.text
                    )))
                }
            }
            Some(c) if c.is_ascii_digit() => self.parse_literal(),
            Some(c) if c.is_ascii_alphabetic() || c == '_' => self.parse_reference(),
            _ => Err(EvalError::Unsupported(format!(
                "unexpected `{}` in `{}`",
                &self.text[self.pos..],
                self.text
            ))),
        }
    }

    /// A number with an optional unit suffix (`2.4mm`, `1.6`, `2 mm`).
    fn parse_literal(&mut self) -> Result<Qty, EvalError> {
        let (qty, consumed) = lex_qty_literal(&self.text[self.pos..]).ok_or_else(|| {
            EvalError::Unparseable(
                self.text[self.pos..].to_string(),
                self.text[self.pos..].to_string(),
            )
        })?;
        self.pos += consumed;
        Ok(qty)
    }

    /// A dotted reference or bare identifier atom.
    fn parse_reference(&mut self) -> Result<Qty, EvalError> {
        let start = self.pos;
        let bytes = self.text.as_bytes();
        let mut i = self.pos;
        while i < bytes.len()
            && (bytes[i].is_ascii_alphanumeric() || bytes[i] == b'_' || bytes[i] == b'.')
        {
            i += 1;
        }
        let path = &self.text[start..i];
        // A call shape (aggregate/function) is outside the subset.
        let after = self.text[i..].trim_start();
        if after.starts_with('(') {
            return Err(EvalError::Unsupported(format!("call `{path}(...)`")));
        }
        self.pos = i;
        self.resolve_path(path)
    }

    /// Resolve a reference path against the context (module-doc binding
    /// order).
    fn resolve_path(&self, path: &str) -> Result<Qty, EvalError> {
        if let Some(key) = path.strip_prefix("capability.") {
            let Some(value) = self.ctx.capability.get(key) else {
                return Err(EvalError::Unbound(path.to_string()));
            };
            return parse_scalar(path, value);
        }
        // WO-87 (D198): absolute registry-record dereference,
        // `registry.<record key>.<field>` -- the field name resolves
        // through the loaded records' unit-suffix convention
        // (`registry.abracon_abm8_16mhz_18pf.cl` -> `cl_pf` -> `18pF`).
        if let Some(rest) = path.strip_prefix("registry.") {
            let Some(registry) = self.ctx.registry else {
                return Err(EvalError::Unbound(path.to_string()));
            };
            let Some((key, field)) = rest.rsplit_once('.') else {
                return Err(EvalError::Unbound(path.to_string()));
            };
            let Some(value) = registry.field(key, field) else {
                return Err(EvalError::Unbound(path.to_string()));
            };
            return parse_scalar(path, &value);
        }
        if let Some((head, field)) = path.split_once('.') {
            if self.ctx.var == Some(head) {
                let Some(measures) = self.ctx.measures else {
                    return Err(EvalError::Unbound(path.to_string()));
                };
                if let Some(value) = measures.get(field) {
                    return parse_scalar(path, value);
                }
                // WO-87 (D198): the bound entity's record indirection --
                // a field the entity does not carry as a measure
                // resolves through its `record` measure into the loaded
                // record's fields (`x.cl` on a crystal entity whose
                // record states CL). One seam, no second record loader:
                // the payload arrived through the realized-input
                // channel and Python's RecordStore is the only loader.
                if let (Some(registry), Some(record_key)) =
                    (self.ctx.registry, measures.get("record"))
                {
                    if let Some(value) = registry.field(record_key, field) {
                        tracing::debug!(
                            term = %path,
                            record = %record_key,
                            value = %value,
                            "rule term resolved through the registry-record dereference seam"
                        );
                        return parse_scalar(path, &value);
                    }
                }
                return Err(EvalError::Unbound(path.to_string()));
            }
            // A dotted path that is not the bound var, not capability,
            // and not a registry.<key> dereference -- outside the subset.
            return Err(EvalError::Unbound(path.to_string()));
        }
        // Bare identifier: env (decl fields, stage kwargs), then scalar
        // capability entries.
        if let Some(value) = self.ctx.env.get(path) {
            return parse_scalar(path, value);
        }
        if let Some(value) = self.ctx.capability.get(path) {
            return parse_scalar(path, value);
        }
        Err(EvalError::Unbound(path.to_string()))
    }
}

/// Parse a bound value text as a scalar quantity. `free` and
/// range-valued (`[a, b]`) texts are honestly non-scalar: `free` is an
/// unresolved slot ([`EvalError::Unbound`], defers until resolution)
/// and a range is an envelope, not a value.
fn parse_scalar(term: &str, value: &str) -> Result<Qty, EvalError> {
    let trimmed = value.trim();
    if trimmed == "free" {
        return Err(EvalError::Unbound(format!("{term} (free)")));
    }
    if trimmed.starts_with('[') {
        return Err(EvalError::Unparseable(
            term.to_string(),
            trimmed.to_string(),
        ));
    }
    match lex_qty_literal(trimmed) {
        Some((q, consumed)) if trimmed[consumed..].trim().is_empty() => Ok(q),
        _ => Err(EvalError::Unparseable(
            term.to_string(),
            trimmed.to_string(),
        )),
    }
}

/// Lex a quantity literal (`2.4mm`, `1.6`, `6800 N`) at the head of
/// `text`: returns the quantity and the byte length consumed. `None`
/// when `text` does not start with a number. An unrecognized suffix is
/// NOT consumed (the number parses bare and the caller's grammar
/// rejects the leftover).
fn lex_qty_literal(text: &str) -> Option<(Qty, usize)> {
    let bytes = text.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() && (bytes[i].is_ascii_digit() || bytes[i] == b'.') {
        i += 1;
    }
    if i == 0 {
        return None;
    }
    let magnitude: f64 = text[..i].parse().ok()?;
    // Optional single space before the unit.
    let unit_start = if i < bytes.len()
        && bytes[i] == b' '
        && bytes.get(i + 1).is_some_and(u8::is_ascii_alphabetic)
    {
        i + 1
    } else {
        i
    };
    let mut j = unit_start;
    while j < bytes.len() && (bytes[j].is_ascii_alphanumeric() || bytes[j] == b'/') {
        j += 1;
    }
    let suffix = &text[unit_start..j];
    if suffix.is_empty() {
        return Some((Qty::new(magnitude, Unit::dimensionless()), i));
    }
    match Unit::parse_expr(suffix) {
        Ok(unit) => Some((Qty::new(magnitude, unit), j)),
        Err(_) => Some((Qty::new(magnitude, Unit::dimensionless()), i)),
    }
}

/// How one rule evaluated over one consuming declaration -- the
/// aggregated outcome `checks.rs` reports diagnostics from and
/// `claims.rs` lowers obligations from.
#[derive(Debug, Clone)]
pub struct RuleEvaluation {
    /// The evaluated rule (cloned out of the index so downstream passes
    /// need no lifetime tie to the CST).
    pub rule: RuleDef,
    /// The consuming declaration's name.
    pub decl_name: String,
    /// The consuming declaration's file.
    pub decl_file: Utf8PathBuf,
    /// The consuming decl's byte range (diagnostic primary span).
    pub decl_range: (usize, usize),
    /// Violating matches: (entity origin, verdict detail, margin).
    pub violations: Vec<(String, String, Option<f64>)>,
    /// Passing matches: (entity origin, verdict detail, margin).
    pub passes: Vec<(String, String, Option<f64>)>,
    /// Deferred matches: (entity origin or rule-level marker, the
    /// blocking fact).
    pub deferrals: Vec<(String, String)>,
}

impl RuleEvaluation {
    /// True when nothing about this rule needs an obligation or
    /// diagnostic (every match passed, or no matches existed for a
    /// modeled domain -- a part with no holes satisfies hole rules).
    #[must_use]
    pub fn is_clean_pass(&self) -> bool {
        self.violations.is_empty() && self.deferrals.is_empty()
    }
}

/// Evaluate every attached rule of `decl` against its committed entity
/// scope. The static half of D-E: modeled domains (those with a
/// `known_measure_keys` vocabulary) evaluate per entity; unmodeled
/// domains, query tails, and unevaluable terms defer honestly.
#[must_use]
pub fn evaluate_rules_for_decl(
    decl: &Decl,
    decl_name: &str,
    decl_file: &Utf8PathBuf,
    entities: Option<&regolith_sem::EntityDb>,
    index: &PackIndex,
) -> Vec<RuleEvaluation> {
    evaluate_rules_for_decl_with_registry(
        decl,
        decl_name,
        decl_file,
        entities,
        index,
        &crate::registry::RegistryRecords::empty(),
    )
}

/// [`evaluate_rules_for_decl`] plus the registry-records payload
/// (WO-87/D198): record-field terms in rule predicates resolve through
/// `registry` instead of deferring.
#[must_use]
pub fn evaluate_rules_for_decl_with_registry(
    decl: &Decl,
    decl_name: &str,
    decl_file: &Utf8PathBuf,
    entities: Option<&regolith_sem::EntityDb>,
    index: &PackIndex,
    registry: &crate::registry::RegistryRecords,
) -> Vec<RuleEvaluation> {
    let packs = index.attached_to(decl);
    if packs.is_empty() {
        return Vec::new();
    }
    let mut out = Vec::new();
    for pack in packs {
        out.extend(evaluate_pack_for_decl_with_registry(
            pack, decl, decl_name, decl_file, entities, registry,
        ));
    }
    out
}

/// Evaluate ONE pack's rules against one declaration's committed
/// entities, regardless of attachment (the `rules try` runner forces
/// exactly this; `evaluate_rules_for_decl` calls it per attached pack).
#[must_use]
pub fn evaluate_pack_for_decl(
    pack: &PackDef,
    decl: &Decl,
    decl_name: &str,
    decl_file: &Utf8PathBuf,
    entities: Option<&regolith_sem::EntityDb>,
) -> Vec<RuleEvaluation> {
    evaluate_pack_for_decl_with_registry(
        pack,
        decl,
        decl_name,
        decl_file,
        entities,
        &crate::registry::RegistryRecords::empty(),
    )
}

/// [`evaluate_pack_for_decl`] plus the registry-records payload (the
/// WO-87/D198 dereference seam threaded into every [`EvalCtx`]).
#[must_use]
pub fn evaluate_pack_for_decl_with_registry(
    pack: &PackDef,
    decl: &Decl,
    decl_name: &str,
    decl_file: &Utf8PathBuf,
    entities: Option<&regolith_sem::EntityDb>,
    registry: &crate::registry::RegistryRecords,
) -> Vec<RuleEvaluation> {
    let env = BindingEnv::for_decl(decl);
    let range = decl.syntax().text_range();
    let decl_range = (range.start().into(), range.end().into());

    let mut out = Vec::new();
    {
        for rule in &pack.rules {
            let Some(expr) = rule.demand.as_deref().or(rule.advise.as_deref()) else {
                // A rule with neither demand nor advise asserts nothing;
                // logged, not invented around.
                tracing::debug!(rule = %rule.qualified(), "rule has no demand/advise; skipped");
                continue;
            };
            let mut eval = RuleEvaluation {
                rule: rule.clone(),
                decl_name: decl_name.to_string(),
                decl_file: decl_file.clone(),
                decl_range,
                violations: Vec::new(),
                passes: Vec::new(),
                deferrals: Vec::new(),
            };

            if let (Some(var), Some(kind)) = (&rule.forall_var, &rule.domain_kind) {
                let Some(matched) = select_domain_entities(rule, kind, entities, &mut eval) else {
                    out.push(eval);
                    continue;
                };
                for entity in matched {
                    let ctx = EvalCtx {
                        capability: &pack.capability,
                        env: &env,
                        var: Some(var),
                        measures: Some(&entity.measures),
                        registry: Some(registry),
                    };
                    match eval_demand(expr, &ctx) {
                        Ok(v) if v.holds => {
                            eval.passes
                                .push((entity.origin.clone(), v.detail, v.margin));
                        }
                        Ok(v) => {
                            eval.violations
                                .push((entity.origin.clone(), v.detail, v.margin));
                        }
                        Err(e) => {
                            eval.deferrals.push((entity.origin.clone(), e.fact()));
                        }
                    }
                }
            } else {
                // Unquantified rule: evaluated once per consuming
                // decl against the decl's own bindings.
                let ctx = EvalCtx {
                    capability: &pack.capability,
                    env: &env,
                    var: None,
                    measures: None,
                    registry: Some(registry),
                };
                match eval_demand(expr, &ctx) {
                    Ok(v) if v.holds => {
                        eval.passes
                            .push((decl_name.to_string(), v.detail, v.margin));
                    }
                    Ok(v) => {
                        eval.violations
                            .push((decl_name.to_string(), v.detail, v.margin));
                    }
                    Err(e) => {
                        eval.deferrals.push((decl_name.to_string(), e.fact()));
                    }
                }
            }
            tracing::debug!(
                rule = %eval.rule.qualified(),
                decl = %decl_name,
                passes = eval.passes.len(),
                violations = eval.violations.len(),
                deferrals = eval.deferrals.len(),
                "rule evaluated"
            );
            out.push(eval);
        }
    }
    out
}

/// One `expect:` fixture case's run outcome (the `rules test` unit).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CaseOutcome {
    /// The fixture behaved as its verdict word promised.
    Ok,
    /// The demand evaluated, but to the OPPOSITE verdict.
    WrongVerdict {
        /// The evaluated detail (`lhs op rhs`).
        observed: String,
    },
    /// The demand could not be evaluated against the fixture (an
    /// unbound term, an unmodeled shape): the case cannot prove the
    /// rule and FAILS the test run with the reason.
    NotEvaluable {
        /// The blocking term/shape.
        reason: String,
    },
}

/// One run `expect:` case: which rule, which verdict was promised,
/// what happened.
#[derive(Debug, Clone)]
pub struct ExpectCaseRun {
    /// The owning rule's qualified name.
    pub rule: String,
    /// The promised verdict word (`pass`/`fail`).
    pub expected: String,
    /// The fixture text as spelled.
    pub fixture: String,
    /// What the run observed.
    pub outcome: CaseOutcome,
}

/// The `rules test` result for one pack: every case run plus the
/// missing-case lint warnings (a rule without both a pass and a fail
/// case is untested law, D-H).
#[derive(Debug, Clone, Default)]
pub struct ExpectReport {
    /// Every case run, rule/source order.
    pub cases: Vec<ExpectCaseRun>,
    /// Lint warnings (missing pass/fail case; no demand to test).
    pub lints: Vec<String>,
}

impl ExpectReport {
    /// True when every case behaved (lints do not fail the run; they
    /// are warnings by design).
    #[must_use]
    pub fn ok(&self) -> bool {
        self.cases.iter().all(|c| c.outcome == CaseOutcome::Ok)
    }
}

/// Run every rule's `expect:` fixtures for `pack` (the `rules test`
/// engine half). Each fixture (`hole(diameter=3mm, edge_distance=8mm)`)
/// becomes a synthetic entity: its keyword arguments are BOTH the
/// bound variable's measures and the bare-identifier environment (so
/// `bend(radius=2.4mm, sheet=1.5mm)` supplies the design fact the
/// demand names); bare flag words (`interior`) are logged and ignored.
#[must_use]
pub fn run_expect_cases(pack: &PackDef) -> ExpectReport {
    let span = tracing::info_span!("rules.test", pack = %pack.name);
    let _enter = span.enter();

    let mut report = ExpectReport::default();
    for rule in &pack.rules {
        let Some(expr) = rule.demand.as_deref().or(rule.advise.as_deref()) else {
            report.lints.push(format!(
                "rule `{}` has no demand/advise to test",
                rule.qualified()
            ));
            continue;
        };
        let has_pass = rule.expect.iter().any(|(v, _)| v == "pass");
        let has_fail = rule.expect.iter().any(|(v, _)| v == "fail");
        if !has_pass || !has_fail {
            report.lints.push(format!(
                "rule `{}` is missing {} `expect:` case{} (a rule nobody has seen fire is untested law)",
                rule.qualified(),
                match (has_pass, has_fail) {
                    (false, false) => "both a pass and a fail",
                    (false, true) => "a pass",
                    _ => "a fail",
                },
                if has_pass == has_fail { "s" } else { "" },
            ));
        }
        for (expected, fixture) in &rule.expect {
            let pairs = fixture_pairs(fixture);
            let measures: Measures = pairs.iter().cloned().collect();
            let env = BindingEnv::from_pairs(&pairs);
            let ctx = EvalCtx {
                capability: &pack.capability,
                env: &env,
                var: rule.forall_var.as_deref(),
                measures: Some(&measures),
                registry: None,
            };
            let outcome = match eval_demand(expr, &ctx) {
                Ok(v) => {
                    let promised_pass = expected == "pass";
                    if v.holds == promised_pass {
                        CaseOutcome::Ok
                    } else {
                        CaseOutcome::WrongVerdict { observed: v.detail }
                    }
                }
                Err(e) => CaseOutcome::NotEvaluable { reason: e.fact() },
            };
            tracing::debug!(
                rule = %rule.qualified(),
                expected = %expected,
                ?outcome,
                "expect case run"
            );
            report.cases.push(ExpectCaseRun {
                rule: rule.qualified(),
                expected: expected.clone(),
                fixture: fixture.clone(),
                outcome,
            });
        }
    }
    report
}

/// The `key=value` pairs of an entity-sketch fixture
/// (`hole(diameter=3mm, edge_distance=8mm)`), in source order. Bare
/// flag words are ignored (logged).
fn fixture_pairs(fixture: &str) -> Vec<(String, String)> {
    let inner = fixture
        .split_once('(')
        .and_then(|(_, rest)| rest.rsplit_once(')'))
        .map_or("", |(inner, _)| inner);
    let mut out = Vec::new();
    for part in inner.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if let Some((k, v)) = part.split_once('=') {
            out.push((k.trim().to_string(), v.trim().to_string()));
        } else {
            tracing::debug!(flag = %part, "fixture flag word ignored by the evaluator");
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    const PACK: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            resolves: b.radius from free\n            why: \"press pack minimum inside radius\"\n";

    #[test]
    fn pack_index_lifts_capability_and_rules() {
        let files = parsed(PACK);
        let index = PackIndex::build(&files);
        let pack = index.get("sheet_metal").expect("pack indexed");
        assert_eq!(pack.capability.get("min_bend_ratio").unwrap(), "1.6");
        assert_eq!(pack.rules.len(), 1);
        let rule = &pack.rules[0];
        assert_eq!(rule.qualified(), "sheet_metal.min_bend_radius");
        assert_eq!(rule.claim_name(), "dfm(sheet_metal.min_bend_radius)");
        assert_eq!(rule.forall_var.as_deref(), Some("b"));
        assert_eq!(rule.resolves, Some(("b".to_string(), "radius".to_string())));
    }

    #[test]
    fn demand_evaluates_with_units_and_capability() {
        let files = parsed(PACK);
        let index = PackIndex::build(&files);
        let pack = index.get("sheet_metal").unwrap();
        let env = BindingEnv::from_pairs(&[("sheet".to_string(), "1.5mm".to_string())]);
        let mut measures = Measures::new();
        measures.insert("radius".to_string(), "2.4mm".to_string());
        let ctx = EvalCtx {
            capability: &pack.capability,
            env: &env,
            var: Some("b"),
            measures: Some(&measures),
            registry: None,
        };
        let v = eval_demand(pack.rules[0].demand.as_deref().unwrap(), &ctx).unwrap();
        assert!(v.holds, "{v:?}");

        measures_violation(&pack.capability, &env);
    }

    fn measures_violation(capability: &IndexMap<String, String>, env: &BindingEnv) {
        let mut measures = Measures::new();
        measures.insert("radius".to_string(), "1.0mm".to_string());
        let ctx = EvalCtx {
            capability,
            env,
            var: Some("b"),
            measures: Some(&measures),
            registry: None,
        };
        let v = eval_demand("b.radius >= capability.min_bend_ratio * sheet", &ctx).unwrap();
        assert!(!v.holds, "{v:?}");
    }

    #[test]
    fn unbound_term_is_an_eval_error_not_a_verdict() {
        let files = parsed(PACK);
        let index = PackIndex::build(&files);
        let pack = index.get("sheet_metal").unwrap();
        let env = BindingEnv::default();
        let mut measures = Measures::new();
        measures.insert("radius".to_string(), "2.4mm".to_string());
        let ctx = EvalCtx {
            capability: &pack.capability,
            env: &env,
            var: Some("b"),
            measures: Some(&measures),
            registry: None,
        };
        let err = eval_demand(pack.rules[0].demand.as_deref().unwrap(), &ctx).unwrap_err();
        assert_eq!(err, EvalError::Unbound("sheet".to_string()));
    }

    #[test]
    fn aggregate_call_is_unsupported() {
        let env = BindingEnv::default();
        let cap = IndexMap::new();
        let ctx = EvalCtx {
            capability: &cap,
            env: &env,
            var: None,
            measures: None,
            registry: None,
        };
        let err = eval_demand("sum(n.loads.i_input) <= n.driver.i_drive", &ctx).unwrap_err();
        assert!(matches!(err, EvalError::Unsupported(_)), "{err:?}");
    }

    #[test]
    fn dimension_mismatch_is_an_eval_error() {
        let env = BindingEnv::from_pairs(&[("x".to_string(), "1mm".to_string())]);
        let cap = IndexMap::new();
        let ctx = EvalCtx {
            capability: &cap,
            env: &env,
            var: None,
            measures: None,
            registry: None,
        };
        let err = eval_demand("x >= 3A", &ctx).unwrap_err();
        assert!(matches!(err, EvalError::Dimension(_)), "{err:?}");
    }

    #[test]
    fn solve_resolves_yields_the_bound() {
        let files = parsed(PACK);
        let index = PackIndex::build(&files);
        let pack = index.get("sheet_metal").unwrap();
        let env = BindingEnv::from_pairs(&[("sheet".to_string(), "1.5mm".to_string())]);
        let ctx = EvalCtx {
            capability: &pack.capability,
            env: &env,
            var: Some("b"),
            measures: None,
            registry: None,
        };
        let q = solve_resolves(
            pack.rules[0].demand.as_deref().unwrap(),
            "b",
            "radius",
            &ctx,
        )
        .unwrap();
        assert_eq!(render_qty(&q), "2.4mm");
    }

    #[test]
    fn attachment_resolves_head_and_bare_args() {
        let src = format!(
            "{PACK}part p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n"
        );
        let files = parsed(&src);
        let index = PackIndex::build(&files);
        let file = regolith_syntax::ast::File::cast(files[0].parse.syntax()).unwrap();
        let part = file
            .decls()
            .into_iter()
            .find(|d| d.name().as_deref() == Some("p"))
            .unwrap();
        let attached = index.attached_to(&part);
        assert_eq!(attached.len(), 1);
        assert_eq!(attached[0].name, "sheet_metal");
    }

    #[test]
    fn binding_env_reads_decl_fields_and_stage_kwargs() {
        let src =
            "part p:\n    material: AISI_304\n    stage cut: process=laser_cut(sheet=1.5mm)\n";
        let files = parsed(src);
        let file = regolith_syntax::ast::File::cast(files[0].parse.syntax()).unwrap();
        let part = file.decls().into_iter().next().unwrap();
        let env = BindingEnv::for_decl(&part);
        assert_eq!(env.get("material"), Some("AISI_304"));
        assert_eq!(env.get("sheet"), Some("1.5mm"));
    }

    #[test]
    fn true_false_literals_evaluate_directly() {
        let env = BindingEnv::default();
        let cap = IndexMap::new();
        let ctx = EvalCtx {
            capability: &cap,
            env: &env,
            var: None,
            measures: None,
            registry: None,
        };
        assert!(eval_demand("true", &ctx).unwrap().holds);
        assert!(!eval_demand("false", &ctx).unwrap().holds);
    }

    #[test]
    fn registry_deref_resolves_record_fields_through_the_bound_entity() {
        // WO-87/D198: `x.cl` on an entity whose `record` measure names
        // a loaded record resolves through the registry handle (the
        // clock_discipline packs' exact shape); without the handle the
        // same term defers (Unbound), never inventing a value.
        let registry = crate::registry::RegistryRecords::from_pairs(&[(
            "abracon_abm8_16mhz_18pf",
            &[("class", "crystal"), ("cl_pf", "18")],
        )]);
        let env = BindingEnv::default();
        let cap = IndexMap::new();
        let mut measures = Measures::new();
        measures.insert("record".to_string(), "abracon_abm8_16mhz_18pf".to_string());
        measures.insert("c_load_calculated".to_string(), "10pF".to_string());
        let ctx = EvalCtx {
            capability: &cap,
            env: &env,
            var: Some("x"),
            measures: Some(&measures),
            registry: Some(&registry),
        };
        // 10pF >= 18pF - 1pF: the hazard-board firing shape.
        let v = eval_demand("x.c_load_calculated >= x.cl - 1pF", &ctx).unwrap();
        assert!(!v.holds, "{v:?}");

        // Absolute registry path form.
        let v2 = eval_demand("registry.abracon_abm8_16mhz_18pf.cl >= 10pF", &ctx).unwrap();
        assert!(v2.holds, "{v2:?}");

        // No registry handle: the same term is an honest deferral.
        let ctx_none = EvalCtx {
            capability: &cap,
            env: &env,
            var: Some("x"),
            measures: Some(&measures),
            registry: None,
        };
        let err = eval_demand("x.c_load_calculated >= x.cl - 1pF", &ctx_none).unwrap_err();
        assert_eq!(err, EvalError::Unbound("x.cl".to_string()));
    }

    #[test]
    fn multi_line_process_attachment_resolves_wrapped_args() {
        // WO-87: the board_correctness attachment spelling wraps its
        // pack args over continuation lines; attachment must see them.
        let src = format!(
            "{PACK}part p:\n    stage checklist: process=board_correctness(\n        sheet_metal,\n        other_pack)\n"
        );
        let files = parsed(&src);
        let index = PackIndex::build(&files);
        let file = regolith_syntax::ast::File::cast(files[0].parse.syntax()).unwrap();
        let part = file
            .decls()
            .into_iter()
            .find(|d| d.name().as_deref() == Some("p"))
            .unwrap();
        let attached = index.attached_to(&part);
        assert_eq!(attached.len(), 1, "wrapped bare arg resolves the pack");
        assert_eq!(attached[0].name, "sheet_metal");
    }
}

#[cfg(test)]
mod dotted_name_tests {
    use super::PackIndex;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    #[test]
    fn dotted_process_pack_name_indexes_whole() {
        let src = "process std.sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule a:\n            demand: true\n";
        let path = Utf8PathBuf::from("t.hema");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }];
        assert!(
            files[0].parse.diagnostics().is_empty(),
            "dotted process header must parse clean: {:?}",
            files[0].parse.diagnostics()
        );
        let index = PackIndex::build(&files);
        let pack = index.get("std.sheet_metal").expect("dotted name indexed");
        assert_eq!(pack.rules[0].qualified(), "std.sheet_metal.a");
    }
}

#[cfg(test)]
mod expect_tests {
    use super::{run_expect_cases, CaseOutcome, PackIndex};
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn pack_of(src: &str) -> super::PackDef {
        let path = Utf8PathBuf::from("t.hema");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }];
        let index = PackIndex::build(&files);
        let pack = super::PackDef::clone(index.iter().next().expect("one pack"));
        pack
    }

    const PACK: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            why: \"press pack minimum inside radius\"\n            expect:\n                pass: bend(radius=2.4mm, sheet=1.5mm)\n                fail: bend(radius=1.0mm, sheet=1.5mm)\n";

    #[test]
    fn expect_cases_run_green_when_verdicts_hold() {
        let report = run_expect_cases(&pack_of(PACK));
        assert!(report.ok(), "{report:?}");
        assert_eq!(report.cases.len(), 2);
        assert!(report.lints.is_empty(), "{:?}", report.lints);
    }

    #[test]
    fn a_wrong_verdict_fails_the_case() {
        let src = PACK.replace(
            "fail: bend(radius=1.0mm, sheet=1.5mm)",
            "fail: bend(radius=9mm, sheet=1.5mm)",
        );
        let report = run_expect_cases(&pack_of(&src));
        assert!(!report.ok(), "{report:?}");
        assert!(matches!(
            report.cases[1].outcome,
            CaseOutcome::WrongVerdict { .. }
        ));
    }

    #[test]
    fn a_missing_fail_case_is_a_lint_warning() {
        let src = "process p1:\n    dfm:\n        rule r1:\n            forall h in holes\n            demand: h.diameter >= 1mm\n            expect:\n                pass: hole(diameter=3mm)\n";
        let report = run_expect_cases(&pack_of(src));
        assert!(report.ok(), "a lint does not fail the run: {report:?}");
        assert_eq!(report.lints.len(), 1, "{:?}", report.lints);
        assert!(report.lints[0].contains("a fail"), "{:?}", report.lints);
    }

    #[test]
    fn an_unevaluable_fixture_is_not_ok() {
        let src = "process p1:\n    dfm:\n        rule r1:\n            forall h in holes\n            demand: h.diameter >= min_dia\n            expect:\n                pass: hole(diameter=3mm)\n                fail: hole(diameter=0.1mm)\n";
        let report = run_expect_cases(&pack_of(src));
        assert!(!report.ok(), "{report:?}");
        assert!(matches!(
            report.cases[0].outcome,
            CaseOutcome::NotEvaluable { .. }
        ));
    }
}

#[cfg(test)]
mod corpus_shape_tests {
    use super::PackIndex;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_sem::EntityKind;

    /// The real corpus pair: the reference pack + sheet_bracket, read
    /// off disk so the flagship acceptance path (pierced holes defer on
    /// edge_distance; radius=free resolves at 2.4mm) cannot drift from
    /// the files the golden suite checks.
    #[test]
    fn sheet_bracket_pair_resolves_and_defers_as_documented() {
        let root = Utf8PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut files = Vec::new();
        for name in [
            "examples/tracks/hematite/sheet_bracket.hema",
            "examples/tracks/hematite/std_sheet_metal.hema",
        ] {
            let path = root.join(name);
            let text = std::fs::read_to_string(&path).expect("corpus file readable");
            files.push(ParsedFile {
                path: path.clone(),
                parse: regolith_syntax::parse(&text, &path),
            });
        }
        let index = PackIndex::build(&files);
        let pack = index.get("std.sheet_metal").expect("pack indexed");
        assert_eq!(
            pack.capability.get("min_bend_ratio").map(String::as_str),
            Some("1.6"),
            "trailing comment stripped: {:?}",
            pack.capability
        );
        let snaps = build_entities(&files);
        let db = snaps.scopes.get("SensorBracket").expect("bracket scope");
        let holes = db.iter().filter(|e| e.kind == EntityKind::Hole).count();
        assert_eq!(holes, 4, "n=4 pierce orbit materialized");
        let bend = db
            .iter()
            .find(|e| e.kind == EntityKind::Bend)
            .expect("flange bend");
        assert_eq!(
            bend.measures.get("radius").map(String::as_str),
            Some("2.4mm"),
            "radius=free resolved at the pack minimum: {:?}",
            bend.measures
        );
    }
}
