//! The hand-written, event-based recursive-descent parser with Pratt
//! expressions and layout-anchored error recovery (AD-3).
//!
//! Substrate reference: `docs/substrate/08`, `docs/mech/02`,
//! `docs/elec/07`, and `examples/` (the concrete target corpus). The
//! parser emits events that a builder folds into a rowan tree; error
//! recovery syncs on INDENT/DEDENT so one bad statement never eats the
//! file (diagnostics stay batch-emitted, substrate/09 sec. 4).
//!
//! Statement grammar (WO-05 cycle 11): declaration bodies, `then`
//! scopes, `require` claim groups, `budget`/`waive`/`policy`/`locked`
//! blocks all share one statement-block grammar
//! ([`Parser::parse_stmt_block`]): each line is classified as a
//! `Field` (`name: value`), a `CtorStmt` (`name = value`), or -- for
//! domain-specific shapes the spec defers (`stage`, `walk`, `zones`,
//! `impl ... for ...`, `connect`, `boundary`, `parts`, orbit
//! constructors, generic decl headers, ...) -- an
//! [`SyntaxKind::OpaqueIsland`] covering that one statement (header
//! line plus any nested indented body). This keeps every recognized
//! statement byte-complete and error-resilient while giving WO-19 a
//! structured tree for the constructs this WO's scope names explicitly
//! (substrate/08 sec. 2-4; see the WO-05 report note for the exact
//! residual-opaque list).
//!
//! Value/expression grammar: a Pratt precedence-climbing parser over
//! comparisons (`< > <= >= == =`), `+ -`, `* /`, unary `-`, quantity
//! literals (adjacent `Number` + `Ident`, e.g. `5 mm`), parenthesized
//! expressions, dotted paths, calls, `[a, b]` intervals, `[i .. j]`
//! ranges, `+- N%` tolerance, `default`/`derived`/`free`/`allocated`
//! cause values, `in [...]` value sources, and a `during <expr>`
//! clause usable both as a trailing claim qualifier and as a call
//! argument (`peak(x, during boundary.launch)`). Any expression shape
//! this grammar cannot classify is swept losslessly into a trailing
//! `OpaqueIsland` rather than erroring (AD-3 fuzz invariant); this
//! degrades gracefully instead of guessing at unspecified syntax.

use camino::Utf8PathBuf;
use rockhead_diag::{DiagCode, Diagnostic, Family, LabeledSpan, Span};
use rowan::{Checkpoint, GreenNode, GreenNodeBuilder, Language as _};

use crate::checks;
use crate::cst::{RockheadLanguage, SyntaxNode};
use crate::layout::{apply_layout, LayoutToken};
use crate::syntax_kind::SyntaxKind;
use crate::token::lex;

/// `E01xx`: a token appeared where no statement/declaration could
/// start; recovery skips it and resyncs on the next layout token.
const UNEXPECTED_TOKEN: DiagCode = DiagCode::new(Family::Parse, 92);

/// The result of parsing one source file: a lossless green tree plus
/// any diagnostics. A parse ALWAYS produces a tree (error-resilient);
/// diagnostics are data, not failure (AD-7).
#[derive(Debug, Clone)]
pub struct Parse {
    green: GreenNode,
    diagnostics: Vec<Diagnostic>,
}

impl Parse {
    /// The typed root node of the parse.
    #[must_use]
    pub fn syntax(&self) -> SyntaxNode {
        SyntaxNode::new_root(self.green.clone())
    }

    /// Diagnostics collected during parsing (may be non-empty even for a
    /// usable tree).
    #[must_use]
    pub fn diagnostics(&self) -> &[Diagnostic] {
        &self.diagnostics
    }
}

/// Parse a source string belonging to `file` into a [`Parse`].
///
/// Runs lex -> layout -> parse -> L1 static checks (`checks::run`).
/// The `file` path anchors diagnostic spans. Never panics on any input
/// (the fuzz invariant, AD-3).
#[must_use]
pub fn parse(source: &str, file: &Utf8PathBuf) -> Parse {
    let raw = lex(source);
    let (tokens, layout_diags) = apply_layout(&raw, source);
    let mut diags: Vec<Diagnostic> = layout_diags
        .into_iter()
        .map(|d| remap_diagnostic_file(d, file))
        .collect();

    let mut p = Parser {
        toks: &tokens,
        pos: 0,
        source,
        file,
        builder: GreenNodeBuilder::new(),
        diags: Vec::new(),
    };
    p.parse_file();
    diags.append(&mut p.diags);

    let green = p.builder.finish();
    let root = SyntaxNode::new_root(green.clone());
    diags.append(&mut checks::run(&root, file));

    Parse {
        green,
        diagnostics: diags,
    }
}

/// Rewrite every span-bearing field of `d` to point at `file`. Used for
/// diagnostics produced by the (file-agnostic) layout pass.
fn remap_diagnostic_file(mut d: Diagnostic, file: &Utf8PathBuf) -> Diagnostic {
    for s in &mut d.spans {
        s.span.file = file.clone();
    }
    for f in &mut d.fixes {
        if let Some(r) = f.replacement.as_mut() {
            r.span.file = file.clone();
        }
    }
    for r in &mut d.related {
        r.span.file = file.clone();
    }
    d
}

/// The event-emitting recursive-descent driver. Builds the rowan tree
/// directly (a `GreenNodeBuilder` folding is the same shape as the
/// event-list-then-builder split, collapsed for this bootstrap pass;
/// see the WO-05 report note on this simplification).
struct Parser<'a> {
    toks: &'a [LayoutToken],
    pos: usize,
    source: &'a str,
    file: &'a Utf8PathBuf,
    builder: GreenNodeBuilder<'static>,
    diags: Vec<Diagnostic>,
}

/// Top-level declaration keywords (substrate/08; WO-05 scope list).
fn is_decl_start(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::PartKw
            | SyntaxKind::ProfileKw
            | SyntaxKind::InterfaceKw
            | SyntaxKind::MatingKw
            | SyntaxKind::AssemblyKw
            | SyntaxKind::SystemKw
            | SyntaxKind::BlockKw
            | SyntaxKind::ImplKw
            | SyntaxKind::ComponentKw
            | SyntaxKind::ProtocolKw
            | SyntaxKind::ComputerKw
            | SyntaxKind::ImageKw
            | SyntaxKind::BoardKw
            | SyntaxKind::TargetKw
            | SyntaxKind::DatumKw
            | SyntaxKind::EventKw
    )
}

/// The classification of one statement line, decided by a
/// non-consuming lookahead scan ([`Parser::stmt_shape`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StmtShape {
    /// `name: value` (or `dotted.path: value`).
    Field,
    /// `name = value` (or `dotted.path = value`).
    Ctor,
    /// A domain-specific shape this WO defers: swallowed whole as one
    /// [`SyntaxKind::OpaqueIsland`] statement.
    Opaque,
}

/// Binding power (left, right) of a binary operator token, or `None`
/// if `kind` is not a binary operator. Comparisons bind loosest, then
/// `+ -`, then `* /` (standard precedence-climbing table).
fn bin_binding_power(kind: SyntaxKind) -> Option<(u8, u8)> {
    use SyntaxKind::{Eq, EqEqTok, Gt, GtEq, Lt, LtEq, Minus, Plus, Slash, Star};
    match kind {
        Lt | Gt | LtEq | GtEq | EqEqTok | Eq => Some((1, 2)),
        Plus | Minus => Some((3, 4)),
        Star | Slash => Some((5, 6)),
        _ => None,
    }
}

impl Parser<'_> {
    fn current(&self) -> Option<SyntaxKind> {
        self.toks.get(self.pos).map(|t| t.kind)
    }

    /// The kind of the token at `idx`, skipping only `Whitespace`
    /// (used for non-consuming statement-shape lookahead).
    fn peek_significant_kind_at(&self, mut idx: usize) -> Option<SyntaxKind> {
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        self.toks.get(idx).map(|t| t.kind)
    }

    /// Consume the current token into the tree; panics only if called
    /// past EOF (a parser-internal bug, never reachable from source).
    fn bump(&mut self) {
        let tok = &self.toks[self.pos];
        let text = &self.source[tok.span.clone()];
        self.builder
            .token(RockheadLanguage::kind_to_raw(tok.kind), text);
        self.pos += 1;
    }

    fn start(&mut self, kind: SyntaxKind) {
        self.builder.start_node(RockheadLanguage::kind_to_raw(kind));
    }

    fn finish(&mut self) {
        self.builder.finish_node();
    }

    fn checkpoint(&mut self) -> Checkpoint {
        self.builder.checkpoint()
    }

    /// Retroactively wrap every node/token emitted since `cp` in a new
    /// node of `kind` (the standard rowan technique for building
    /// binary-expression trees without lookahead-driven backtracking).
    fn start_node_at(&mut self, cp: Checkpoint, kind: SyntaxKind) {
        self.builder
            .start_node_at(cp, RockheadLanguage::kind_to_raw(kind));
    }

    /// Consume a run of `Whitespace` tokens (intra-line trivia).
    fn skip_ws(&mut self) {
        while self.current() == Some(SyntaxKind::Whitespace) {
            self.bump();
        }
    }

    fn skip_trivia_and_newlines(&mut self) {
        while matches!(
            self.current(),
            Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
        ) {
            self.bump();
        }
    }

    fn parse_file(&mut self) {
        self.start(SyntaxKind::File);
        loop {
            self.skip_trivia_and_newlines();
            match self.current() {
                None => break,
                Some(SyntaxKind::ImportKw) => self.parse_import(),
                Some(k) if is_decl_start(k) => self.parse_decl(),
                // An identifier-led top-level line is a declaration whose
                // keyword this grammar does not yet model (`bind`,
                // `architecture`, ...). It is unstructured, NOT a syntax
                // error: parse it as an opaque declaration (header + body)
                // so a conforming corpus stays diagnostic-clean. Genuine
                // non-identifier garbage still falls through to recovery.
                Some(SyntaxKind::Ident) => self.parse_decl(),
                Some(_) => self.parse_error_recovery(),
            }
        }
        self.finish();
    }

    /// `import` statements: consumed as their header line, no body.
    fn parse_import(&mut self) {
        self.start(SyntaxKind::ImportStmt);
        self.consume_header_line();
        self.finish();
    }

    /// A top-level declaration: keyword + header up to `:`/newline,
    /// followed by an optional indented body parsed as a statement
    /// block (fields, ctor statements, `then`/`require`/`budget`/
    /// `waive`/`policy`/`locked`, and opaque domain statements).
    fn parse_decl(&mut self) {
        self.start(SyntaxKind::Decl);
        self.consume_header_line();
        self.enter_body_block();
        self.finish();
    }

    /// If the next line opens an indented body, bump the `Indent` and
    /// parse it as a statement block.
    ///
    /// The layout pass does not shift the indent stack for blank or
    /// comment lines, so a body's `Indent` can be separated from its
    /// header by `Newline`/`Comment`/`Whitespace` trivia (e.g. a
    /// full-line comment between `intents:` and its first field). We
    /// therefore look PAST that trivia without consuming it: only if an
    /// `Indent` actually follows do we consume the intervening trivia
    /// and open the block. If no `Indent` follows, nothing is consumed --
    /// the trivia belongs to a following sibling or to a closing
    /// `Dedent`, and swallowing it here would eject the body to the
    /// parent level and desync the `Dedent` accounting (the
    /// sibling-ejection cascade, TRIAGE cycle 11).
    fn enter_body_block(&mut self) {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
        ) {
            idx += 1;
        }
        if self.toks.get(idx).map(|t| t.kind) == Some(SyntaxKind::Indent) {
            while self.pos < idx {
                self.bump();
            }
            self.bump(); // Indent
            self.parse_stmt_block();
        }
    }

    /// The shared statement-block grammar: one statement per line until
    /// the matching `Dedent`. Consumes that `Dedent`.
    fn parse_stmt_block(&mut self) {
        loop {
            while matches!(
                self.current(),
                Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
            ) {
                self.bump();
            }
            match self.current() {
                None | Some(SyntaxKind::Dedent) => break,
                Some(SyntaxKind::RequireKw) => self.parse_keyword_block(SyntaxKind::RequireClaim),
                Some(SyntaxKind::ThenKw) => self.parse_keyword_block(SyntaxKind::ThenScope),
                Some(SyntaxKind::BudgetKw) => self.parse_keyword_block(SyntaxKind::BudgetStmt),
                Some(SyntaxKind::WaiveKw) => self.parse_keyword_block(SyntaxKind::WaiveBlock),
                Some(SyntaxKind::PolicyKw) => self.parse_keyword_block(SyntaxKind::PolicyBlock),
                Some(SyntaxKind::LockedKw) => self.parse_keyword_block(SyntaxKind::LockedBlock),
                Some(_) => self.parse_generic_stmt(),
            }
        }
        if self.current() == Some(SyntaxKind::Dedent) {
            self.bump();
        }
    }

    /// `then [label] [on <region>]:`, `require <Group>:`, `budget ...:`,
    /// `waive ...:`, `policy:`, `locked:` -- header keyword + line, then
    /// a nested statement block (shared shape, cycle-3 additions
    /// included; substrate/08 sec. 4, substrate/12).
    fn parse_keyword_block(&mut self, node_kind: SyntaxKind) {
        self.start(node_kind);
        self.consume_header_line();
        self.enter_body_block();
        self.finish();
    }

    /// Look ahead (without consuming) to classify the statement
    /// starting at `self.pos` as [`StmtShape::Field`],
    /// [`StmtShape::Ctor`], or [`StmtShape::Opaque`]. A name is a
    /// single `Ident` optionally continued by `.Ident` (dotted path,
    /// e.g. `a.length = 8.5mm`).
    fn stmt_shape(&self) -> StmtShape {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        if self.toks.get(idx).map(|t| t.kind) != Some(SyntaxKind::Ident) {
            return StmtShape::Opaque;
        }
        idx += 1;
        loop {
            let mut after_ws = idx;
            while matches!(
                self.toks.get(after_ws).map(|t| t.kind),
                Some(SyntaxKind::Whitespace)
            ) {
                after_ws += 1;
            }
            if self.toks.get(after_ws).map(|t| t.kind) == Some(SyntaxKind::Dot) {
                let mut j = after_ws + 1;
                while matches!(
                    self.toks.get(j).map(|t| t.kind),
                    Some(SyntaxKind::Whitespace)
                ) {
                    j += 1;
                }
                if self.toks.get(j).map(|t| t.kind) == Some(SyntaxKind::Ident) {
                    idx = j + 1;
                    continue;
                }
                break;
            }
            break;
        }
        match self.peek_significant_kind_at(idx) {
            Some(SyntaxKind::Colon) => StmtShape::Field,
            Some(SyntaxKind::Eq) => StmtShape::Ctor,
            _ => StmtShape::Opaque,
        }
    }

    /// Dispatch a non-keyword-led statement line by its [`StmtShape`].
    fn parse_generic_stmt(&mut self) {
        match self.stmt_shape() {
            StmtShape::Field => self.parse_field(),
            StmtShape::Ctor => self.parse_ctor(),
            StmtShape::Opaque => self.parse_opaque_stmt(),
        }
    }

    /// `name: value` (name may be a dotted path).
    fn parse_field(&mut self) {
        self.start(SyntaxKind::Field);
        self.bump_name_path();
        self.skip_ws();
        self.bump(); // Colon
        self.parse_value_and_tail();
        self.finish();
    }

    /// `name = value` (name may be a dotted path).
    fn parse_ctor(&mut self) {
        self.start(SyntaxKind::CtorStmt);
        self.bump_name_path();
        self.skip_ws();
        self.bump(); // Eq
        self.parse_value_and_tail();
        self.finish();
    }

    /// Consume the leading `Ident (. Ident)*` name/path already
    /// confirmed present by [`Parser::stmt_shape`].
    fn bump_name_path(&mut self) {
        self.bump(); // Ident
        loop {
            self.skip_ws();
            if self.current() == Some(SyntaxKind::Dot) {
                self.bump();
                self.skip_ws();
                if self.current() == Some(SyntaxKind::Ident) {
                    self.bump();
                    continue;
                }
            }
            break;
        }
    }

    /// The value/expression grammar for a `Field`/`CtorStmt` RHS, plus
    /// an optional trailing `during <expr>` qualifier, then a lossless
    /// sweep of anything left before end-of-line (never invents
    /// structure for a shape the grammar does not recognize; degrades
    /// to an `OpaqueIsland`, AD-3), then any nested indented block
    /// (kept opaque -- see the WO-05 report note).
    fn parse_value_and_tail(&mut self) {
        self.skip_ws();
        if !matches!(
            self.current(),
            Some(SyntaxKind::Newline | SyntaxKind::Dedent) | None
        ) {
            self.parse_value();
            self.skip_ws();
            if self.current() == Some(SyntaxKind::DuringKw) {
                self.parse_value(); // parse_value's atom handles DuringKw directly
                self.skip_ws();
            }
            if !matches!(
                self.current(),
                Some(SyntaxKind::Newline | SyntaxKind::Dedent | SyntaxKind::Indent) | None
            ) {
                self.start(SyntaxKind::OpaqueIsland);
                while !matches!(
                    self.current(),
                    Some(SyntaxKind::Newline | SyntaxKind::Dedent | SyntaxKind::Indent) | None
                ) {
                    self.bump();
                }
                self.finish();
            }
        }
        if self.current() == Some(SyntaxKind::Newline) {
            self.bump();
        }
        // A nested indented body under a Field/CtorStmt is parsed as a
        // nested statement block (recursively), so nested fields and
        // their value-sources are structured -- lowering reaches them
        // for resolutions (INV-21). Shapes the grammar does not
        // recognize still degrade to `OpaqueIsland` per statement inside
        // the block, never inventing structure. `enter_body_block`
        // looks past blank/comment trivia to the body's `Indent` (the
        // layout pass places it after such lines), so a field whose
        // body is preceded by a full-line comment still opens its block
        // instead of ejecting it to the parent (TRIAGE cycle 11).
        self.enter_body_block();
    }

    /// A value: a cause keyword (`default`/`derived`/`free`/
    /// `allocated`), an `in [...]` value source, or a general
    /// expression with an optional `+- N %` tolerance suffix
    /// (substrate/03 value sources).
    fn parse_value(&mut self) {
        self.skip_ws();
        match self.current() {
            Some(
                SyntaxKind::DefaultKw
                | SyntaxKind::DerivedKw
                | SyntaxKind::FreeKw
                | SyntaxKind::AllocatedKw,
            ) => {
                let cp = self.checkpoint();
                self.start(SyntaxKind::CauseValue);
                self.bump();
                self.finish();
                self.start_node_at(cp, SyntaxKind::ValueSource);
                self.finish();
            }
            Some(SyntaxKind::InKw) => {
                let cp = self.checkpoint();
                self.bump();
                self.skip_ws();
                self.parse_expr(0);
                self.start_node_at(cp, SyntaxKind::ValueSource);
                self.finish();
            }
            _ => {
                let cp = self.checkpoint();
                self.parse_expr(0);
                self.skip_ws();
                if self.current() == Some(SyntaxKind::PlusMinus) {
                    self.bump();
                    self.skip_ws();
                    self.parse_expr(0);
                    self.skip_ws();
                    if self.current() == Some(SyntaxKind::Percent) {
                        self.bump();
                    }
                    self.start_node_at(cp, SyntaxKind::ToleranceExpr);
                    self.finish();
                }
            }
        }
    }

    /// Precedence-climbing binary-expression parser (comparisons, then
    /// `+ -`, then `* /`; see [`bin_binding_power`]).
    fn parse_expr(&mut self, min_bp: u8) {
        let cp = self.checkpoint();
        self.parse_prefix();
        loop {
            self.skip_ws();
            let Some(op) = self.current() else { break };
            let Some((lbp, rbp)) = bin_binding_power(op) else {
                break;
            };
            if lbp < min_bp {
                break;
            }
            self.bump();
            self.skip_ws();
            self.parse_expr(rbp);
            self.start_node_at(cp, SyntaxKind::BinExpr);
            self.finish();
        }
    }

    /// Unary `-`, the bound-only claim shorthand (`>= certified`, a
    /// comparator with an implicit subject -- the claim's own field
    /// name), or a plain atom.
    fn parse_prefix(&mut self) {
        match self.current() {
            Some(
                SyntaxKind::Minus
                | SyntaxKind::Lt
                | SyntaxKind::Gt
                | SyntaxKind::LtEq
                | SyntaxKind::GtEq
                | SyntaxKind::EqEqTok,
            ) => {
                let cp = self.checkpoint();
                self.bump();
                self.skip_ws();
                self.parse_expr(7);
                self.start_node_at(cp, SyntaxKind::UnaryExpr);
                self.finish();
            }
            _ => self.parse_atom(),
        }
    }

    /// A leaf expression: quantity/bare number, string, parenthesized
    /// expr, `[...]` interval/range, `during <expr>`, cause keyword, or
    /// a dotted path with an optional call. Any token that cannot start
    /// an atom is left untouched (the caller's lossless sweep handles
    /// it) -- never invented, never panics (AD-3).
    fn parse_atom(&mut self) {
        match self.current() {
            Some(SyntaxKind::Number) => {
                let cp = self.checkpoint();
                self.bump();
                if self.current() == Some(SyntaxKind::Ident) {
                    self.bump(); // adjacent unit, no intervening Whitespace token
                    self.start_node_at(cp, SyntaxKind::QuantityLit);
                    self.finish();
                }
            }
            Some(SyntaxKind::String) => self.bump(),
            Some(SyntaxKind::LParen) => {
                self.start(SyntaxKind::ParenExpr);
                self.bump();
                self.skip_ws();
                if self.current() != Some(SyntaxKind::RParen) {
                    self.parse_expr(0);
                    self.skip_ws();
                }
                if self.current() == Some(SyntaxKind::RParen) {
                    self.bump();
                }
                self.finish();
            }
            Some(SyntaxKind::LBracket) => self.parse_bracket_expr(),
            Some(SyntaxKind::DuringKw) => {
                self.start(SyntaxKind::DuringClause);
                self.bump();
                self.skip_ws();
                self.parse_expr(0);
                self.finish();
            }
            Some(
                SyntaxKind::DefaultKw
                | SyntaxKind::DerivedKw
                | SyntaxKind::FreeKw
                | SyntaxKind::AllocatedKw,
            ) => {
                self.start(SyntaxKind::CauseValue);
                self.bump();
                self.finish();
            }
            Some(SyntaxKind::Ident) => self.parse_path_or_call(),
            _ => {}
        }
    }

    /// `[a, b]` (comma -> [`SyntaxKind::IntervalExpr`]) vs `[i .. j]`
    /// (`..` -> [`SyntaxKind::RangeExpr`]) per substrate/02 sec. 3.
    /// Mixing both separators inside one bracket is a genuine misuse,
    /// left for [`crate::checks`] to flag (E01xx interval/range
    /// confusion) since both tokens are present in the built node.
    fn parse_bracket_expr(&mut self) {
        let cp = self.checkpoint();
        self.bump(); // LBracket
        self.skip_ws();
        let mut is_range = false;
        if self.current() != Some(SyntaxKind::RBracket) {
            self.parse_expr(0);
            self.skip_ws();
            loop {
                match self.current() {
                    Some(SyntaxKind::Comma) => {
                        self.bump();
                        self.skip_ws();
                        self.parse_expr(0);
                        self.skip_ws();
                    }
                    Some(SyntaxKind::DotDot) => {
                        is_range = true;
                        self.bump();
                        self.skip_ws();
                        self.parse_expr(0);
                        self.skip_ws();
                    }
                    _ => break,
                }
            }
        }
        if self.current() == Some(SyntaxKind::RBracket) {
            self.bump();
        }
        let kind = if is_range {
            SyntaxKind::RangeExpr
        } else {
            SyntaxKind::IntervalExpr
        };
        self.start_node_at(cp, kind);
        self.finish();
    }

    /// A dotted `Path`/`NameRef`, optionally called (`Ident(args)`).
    fn parse_path_or_call(&mut self) {
        let cp = self.checkpoint();
        self.bump(); // first Ident
        let mut is_path = false;
        loop {
            if self.current() == Some(SyntaxKind::Dot) {
                self.bump();
                if self.current() == Some(SyntaxKind::Ident) {
                    self.bump();
                    is_path = true;
                    continue;
                }
            }
            break;
        }
        self.start_node_at(
            cp,
            if is_path {
                SyntaxKind::Path
            } else {
                SyntaxKind::NameRef
            },
        );
        self.finish();
        if self.current() == Some(SyntaxKind::LParen) {
            self.start_node_at(cp, SyntaxKind::CallExpr);
            self.parse_arg_list();
            self.finish();
        }
    }

    /// `(arg, arg, ...)`. Each argument is a full expression (including
    /// `during <expr>`, handled as an atom).
    fn parse_arg_list(&mut self) {
        self.start(SyntaxKind::ArgList);
        self.bump(); // LParen
        loop {
            self.skip_ws();
            if matches!(
                self.current(),
                Some(SyntaxKind::RParen | SyntaxKind::Newline | SyntaxKind::Dedent) | None
            ) {
                break;
            }
            self.parse_expr(0);
            self.skip_ws();
            if self.current() == Some(SyntaxKind::Comma) {
                self.bump();
            } else {
                break;
            }
        }
        self.skip_ws();
        if self.current() == Some(SyntaxKind::RParen) {
            self.bump();
        }
        self.finish();
    }

    /// A domain-specific statement this WO defers: the header line plus
    /// any nested indented body, swallowed whole as one
    /// [`SyntaxKind::OpaqueIsland`] (structure recorded at the
    /// statement boundary, payload semantics out of scope; see the
    /// WO-05 report note for the residual list).
    fn parse_opaque_stmt(&mut self) {
        self.start(SyntaxKind::OpaqueIsland);
        while !matches!(self.current(), None | Some(SyntaxKind::Newline)) {
            self.bump();
        }
        if self.current() == Some(SyntaxKind::Newline) {
            self.bump();
        }
        while self.current() == Some(SyntaxKind::Whitespace) {
            self.bump();
        }
        if self.current() == Some(SyntaxKind::Indent) {
            self.bump();
            let mut depth = 1i32;
            while depth > 0 {
                match self.current() {
                    None => break,
                    Some(SyntaxKind::Indent) => {
                        depth += 1;
                        self.bump();
                    }
                    Some(SyntaxKind::Dedent) => {
                        depth -= 1;
                        self.bump();
                    }
                    Some(_) => self.bump(),
                }
            }
        }
        self.finish();
    }

    /// Consume tokens up to and including the line's terminating
    /// `Newline` (header lines never span layout Indent/Dedent).
    fn consume_header_line(&mut self) {
        while !matches!(self.current(), None | Some(SyntaxKind::Newline)) {
            self.bump();
        }
        if self.current() == Some(SyntaxKind::Newline) {
            self.bump();
        }
    }

    /// A token could not start any statement: wrap it as an `Error`
    /// node, emit a diagnostic, and advance by exactly one token so a
    /// broken line never stalls or eats the rest of the file (AD-3).
    fn parse_error_recovery(&mut self) {
        let tok = &self.toks[self.pos];
        let span = Span::new(self.file.clone(), tok.span.start, tok.span.end);
        self.diags.push(
            Diagnostic::error(UNEXPECTED_TOKEN, "unexpected token here")
                .with_span(LabeledSpan::new(span, "expected a declaration or import")),
        );
        self.start(SyntaxKind::Error);
        self.bump();
        self.finish();
    }
}

#[cfg(test)]
mod tests {
    use super::parse;
    use camino::Utf8PathBuf;

    fn workspace_root() -> std::path::PathBuf {
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(std::path::Path::parent)
            .expect("crates/rockhead-syntax is two levels under the workspace root")
            .to_path_buf()
    }

    #[test]
    fn empty_file_parses() {
        let file = Utf8PathBuf::from("empty.hem");
        let p = parse("", &file);
        assert_eq!(p.syntax().text().to_string(), "");
    }

    #[test]
    fn only_comments_file_parses_with_no_diagnostics() {
        let file = Utf8PathBuf::from("comments.hem");
        let src = "# just a comment\n# another one\n";
        let p = parse(src, &file);
        assert!(p.diagnostics().is_empty());
        assert_eq!(p.syntax().text().to_string(), src);
    }

    #[test]
    fn broken_statement_does_not_eat_the_file() {
        let file = Utf8PathBuf::from("broken.hem");
        // `)))` cannot start any statement; a following, well-formed
        // decl must still parse.
        let src = ")))\npart ok:\n    x: 1\n";
        let p = parse(src, &file);
        assert!(!p.diagnostics().is_empty());
        // The whole source is still represented losslessly.
        assert_eq!(p.syntax().text().to_string(), src);
    }

    #[test]
    fn cst_covers_every_source_byte() {
        for src in [
            "import a.b\npart wall:\n    thickness: 4mm\n",
            "profile p:\n    from origin\n    line\n    close\n",
            "\t\n",
            "part a:\r\n    x: 1\r\n",
        ] {
            let file = Utf8PathBuf::from("t.hem");
            let p = parse(src, &file);
            assert_eq!(p.syntax().text().to_string(), src, "lossless for {src:?}");
        }
    }

    // AD-3: extend the byte-coverage property with proptest-generated
    // ASCII input. The CST must be lossless (text length == input
    // length, and the reprinted text equals the input byte-for-byte)
    // for arbitrary ASCII source, not just the hand-picked fixtures
    // above -- the parser is error-resilient by construction, so this
    // must hold even for input that cannot start any statement.
    proptest::proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(256))]

        #[test]
        fn cst_covers_every_byte_for_arbitrary_ascii(src in "[ -~\\n\\t\\r]{0,64}") {
            let file = Utf8PathBuf::from("prop.hem");
            let p = parse(&src, &file);
            let text = p.syntax().text().to_string();
            proptest::prop_assert_eq!(text.len(), src.len(), "byte length mismatch for {:?}", src);
            proptest::prop_assert_eq!(text, src, "lossless reprint required");
        }
    }

    /// The acceptance corpus: every file under `examples/` parses to an
    /// AST (opaque islands allowed for domain-specific statements)
    /// without panicking, and the CST remains byte-complete.
    #[test]
    fn examples_parse() {
        let root = workspace_root().join("examples");
        let mut seen_any = false;
        for entry in walk(&root) {
            let Some(ext) = entry.extension().and_then(|e| e.to_str()) else {
                continue;
            };
            if rockhead_syntax_extensions().iter().all(|e| *e != ext) {
                continue;
            }
            seen_any = true;
            let src = std::fs::read_to_string(&entry)
                .unwrap_or_else(|e| panic!("reading {entry:?}: {e}"));
            let file = Utf8PathBuf::from_path_buf(entry.clone()).expect("utf8 path");
            let p = parse(&src, &file);
            assert_eq!(
                p.syntax().text().to_string(),
                src,
                "CST not byte-complete for {entry:?}"
            );
        }
        assert!(seen_any, "expected to find at least one example file");
    }

    #[test]
    fn field_parses_structurally() {
        let file = Utf8PathBuf::from("t.hem");
        let src = "part wall:\n    thickness: 4mm\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("Field"));
        assert!(dump.contains("QuantityLit"));
    }

    #[test]
    fn ctor_stmt_and_call_expr_parse_structurally() {
        let file = Utf8PathBuf::from("t.hem");
        let src =
            "part p:\n    holes = milled.ends.instances\n    x = peak(a.b, during c.d) < e.f / 2\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("CtorStmt"));
        assert!(dump.contains("CallExpr"));
        assert!(dump.contains("DuringClause"));
    }

    #[test]
    fn require_block_parses_claims() {
        let file = Utf8PathBuf::from("t.hem");
        let src = "part p:\n    require Structural:\n        trust: >= certified\n        stress: mech.stress(all) < sigma_y / 2\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("RequireClaim"));
        assert!(dump.contains("Field"));
    }

    #[test]
    fn interval_and_range_are_distinguished() {
        let file = Utf8PathBuf::from("t.hem");
        let src = "part p:\n    a: [1mm, 2mm]\n    b: [0 .. 3]\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("IntervalExpr"));
        assert!(dump.contains("RangeExpr"));
    }

    // Regression (TRIAGE cycle 11, parser sibling-ejection desync): a
    // field whose indented body is preceded by a full-line comment must
    // still OPEN that body. The layout pass emits the body `Indent`
    // after the (stack-neutral) comment/blank lines, so a parser that
    // only skips `Whitespace` before testing for `Indent` fails to enter
    // the body, ejects it to the parent level, and desyncs the `Dedent`
    // accounting -- cascading UNEXPECTED_TOKEN errors and, worse,
    // dropping the ejected `require` blocks so their obligations never
    // lower. The body (and its nested `require` claims) must be retained
    // as proper children with zero diagnostics.
    #[test]
    fn comment_before_body_does_not_eject_the_block() {
        let file = Utf8PathBuf::from("t.cupr");
        let src = "system s:\n    intents:\n        # a full-line comment before the first body field\n        image: sense(payload) hosted_on p:\n            gsd: <= 30m\n        require Modes:\n            trust: >= certified\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(
            p.diagnostics().is_empty(),
            "comment before body must not desync the parser: {:?}",
            p.diagnostics()
        );
        // The `require` block is a proper descendant, NOT ejected to the
        // File root (which would lose its obligations downstream).
        let root = p.syntax();
        let require = root
            .descendants()
            .find(|n| format!("{:?}", n.kind()).contains("RequireClaim"))
            .expect("require block must be present in the tree");
        let parent_kind = require.parent().map(|n| format!("{:?}", n.kind()));
        assert_ne!(
            parent_kind.as_deref(),
            Some("File"),
            "require block was ejected to the file top level"
        );
    }

    /// Regression: the real cubesat integration file (`kestrel.cupr`,
    /// whose `intents:` body is comment-led -- the exact bisected
    /// desync trigger) parses with zero parse diagnostics, and all nine
    /// `require` claim groups are retained as nested children rather than
    /// ejected to the file level (TRIAGE cycle 11).
    #[test]
    fn kestrel_intents_body_retains_require_blocks() {
        let path = workspace_root().join("examples/cubesat/kestrel.cupr");
        let src = std::fs::read_to_string(&path).expect("read kestrel.cupr");
        let file = Utf8PathBuf::from_path_buf(path).expect("utf8 path");
        let p = parse(&src, &file);
        assert!(
            p.diagnostics().is_empty(),
            "kestrel.cupr must parse with no parse diagnostics: {:?}",
            p.diagnostics()
        );
        let root = p.syntax();
        let mut require = 0usize;
        let mut ejected = 0usize;
        for n in root.descendants() {
            if format!("{:?}", n.kind()).contains("RequireClaim") {
                require += 1;
                if n.parent().map(|par| format!("{:?}", par.kind())).as_deref() == Some("File") {
                    ejected += 1;
                }
            }
        }
        assert_eq!(require, 9, "expected nine require claim groups");
        assert_eq!(
            ejected, 0,
            "no require block may be ejected to the file level"
        );
    }

    fn rockhead_syntax_extensions() -> Vec<&'static str> {
        crate::extension::EXTENSIONS
            .iter()
            .map(|(e, _)| *e)
            .collect()
    }

    fn walk(dir: &std::path::Path) -> Vec<std::path::PathBuf> {
        let mut out = Vec::new();
        let Ok(entries) = std::fs::read_dir(dir) else {
            return out;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                out.extend(walk(&path));
            } else {
                out.push(path);
            }
        }
        out
    }
}
