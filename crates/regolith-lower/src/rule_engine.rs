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
            let forall_var = forall.as_ref().and_then(regolith_syntax::ast::ForallClause::var);
            let query_text = forall.as_ref().map(regolith_syntax::ast::ForallClause::query_text).unwrap_or_default();
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
/// field's first line (the full spelled expression -- a typed value
/// NODE can be both absent for bare literals like `1.6` and PARTIAL
/// for multi-token expressions; the same colon-RHS stance as
/// `claim_scope::field_colon_rhs_text`), falling back to the typed
/// value node's text. `None` when both are empty.
fn field_value_text_or_rhs(field: &regolith_syntax::ast::Field) -> Option<String> {
    let full = field.syntax().text().to_string();
    let first_line = full.lines().next().unwrap_or("");
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
        // Only the stage HEADER line carries `process=`; then:-scope
        // bodies below it never do, so a text scan of the line is safe.
        let text = node.text().to_string();
        let Some(header) = text.lines().next() else {
            continue;
        };
        let Some(after) = header.split_once("process=").map(|(_, a)| a) else {
            continue;
        };
        let head: String = after
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '.')
            .collect();
        if !head.is_empty() {
            out.push(head.clone());
        }
        // Bare identifier args inside the immediate `(...)`.
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
            let Some(open) = after.find('(') else { continue };
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
    let detail = format!(
        "{} {} {}",
        render_qty(&lhs),
        op,
        render_qty(&rhs)
    );
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
        if let Some((head, field)) = path.split_once('.') {
            if self.ctx.var == Some(head) {
                let Some(measures) = self.ctx.measures else {
                    return Err(EvalError::Unbound(path.to_string()));
                };
                let Some(value) = measures.get(field) else {
                    return Err(EvalError::Unbound(path.to_string()));
                };
                return parse_scalar(path, value);
            }
            // A dotted path that is not the bound var and not capability:
            // registry-record dereference etc. -- outside the subset.
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
    let packs = index.attached_to(decl);
    if packs.is_empty() {
        return Vec::new();
    }
    let env = BindingEnv::for_decl(decl);
    let range = decl.syntax().text_range();
    let decl_range = (range.start().into(), range.end().into());

    let mut out = Vec::new();
    for pack in packs {
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
                if rule.has_query_tail {
                    // `.where(...)` filters are not statically
                    // evaluable yet: defer the whole rule (D-E).
                    eval.deferrals.push((
                        "<rule>".to_string(),
                        format!("query filter `{}`", rule.query_text),
                    ));
                    out.push(eval);
                    continue;
                }
                if kind.known_measure_keys().is_none() {
                    // Unmodeled domain (nets, buses, pins...): no
                    // entities are populated for it today -- an
                    // empty match here would be a SILENT SKIP, so
                    // the rule defers naming its domain (INV-29).
                    eval.deferrals.push((
                        "<rule>".to_string(),
                        format!("domain `{}` (unpopulated)", rule.query_text),
                    ));
                    out.push(eval);
                    continue;
                }
                let matched: Vec<&Entity> = entities
                    .map(|db| db.iter().filter(|e| &e.kind == kind).collect())
                    .unwrap_or_default();
                for entity in matched {
                    let ctx = EvalCtx {
                        capability: &pack.capability,
                        env: &env,
                        var: Some(var),
                        measures: Some(&entity.measures),
                    };
                    match eval_demand(expr, &ctx) {
                        Ok(v) if v.holds => {
                            eval.passes.push((entity.origin.clone(), v.detail, v.margin));
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
                };
                match eval_demand(expr, &ctx) {
                    Ok(v) if v.holds => {
                        eval.passes.push((decl_name.to_string(), v.detail, v.margin));
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
        };
        let v = eval_demand(pack.rules[0].demand.as_deref().unwrap(), &ctx).unwrap();
        assert!(v.holds, "{v:?}");

        measures_violation(&pack.capability, &env);
    }

    fn measures_violation(
        capability: &IndexMap<String, String>,
        env: &BindingEnv,
    ) {
        let mut measures = Measures::new();
        measures.insert("radius".to_string(), "1.0mm".to_string());
        let ctx = EvalCtx {
            capability,
            env,
            var: Some("b"),
            measures: Some(&measures),
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
        let src = "part p:\n    material: AISI_304\n    stage cut: process=laser_cut(sheet=1.5mm)\n";
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
        };
        assert!(eval_demand("true", &ctx).unwrap().holds);
        assert!(!eval_demand("false", &ctx).unwrap().holds);
    }
}
