//! The hand-written, event-based recursive-descent parser with Pratt
//! expressions and layout-anchored error recovery (AD-3).
//!
//! Regolith reference: `docs/regolith/08`, `docs/hematite/02`,
//! `docs/cuprite/07`, and `examples/` (the concrete target corpus). The
//! parser emits events that a builder folds into a rowan tree; error
//! recovery syncs on INDENT/DEDENT so one bad statement never eats the
//! file (diagnostics stay batch-emitted, regolith/09 sec. 4).
//!
//! Statement grammar (WO-05): declaration bodies, `then` scopes,
//! `require` claim groups, `budget`/`waive`/`policy`/`locked` blocks
//! all share one statement-block grammar
//! ([`Parser::parse_stmt_block`]): each line is classified as a
//! `Field` (`name: value`), a `CtorStmt` (`name = value`), a
//! keyword/contextual TYPED block, or -- only for the genuinely
//! deferred residue -- an [`SyntaxKind::OpaqueIsland`]. The former
//! residual domain constructs are now typed CST nodes: `stage`/`setup`
//! (`StageStmt`/`SetupStmt`), `impl ... for ... [as ...]` (`ImplStmt`),
//! `connect`/`parts`/`zones`/`boundary`/`flows` (`*Block`), `policy`
//! rule lines (`PolicyRule`), decl-header generics (`GenericParams`),
//! and the WO-11 `walk` sub-grammar (`WalkBody`/`WalkStep` +
//! `HoleBlock`/`RegionsBlock`/`ConstraintsBlock`/`ExportsBlock`).
//! WO-28 adds the rule-pack surface (hematite/02 sec. 10, cuprite/04
//! sec. 4): a `process` decl body is parsed with a Process statement
//! context in which `capability:` and `dfm:`/`drc:`/`erc:` are typed
//! blocks, pack bodies hold `RuleDecl`s, and rule bodies promote
//! `forall`/`resolves:`/`expect:` (`ForallClause`/`ResolvesClause`/
//! `ExpectBlock`/`ExpectCase`); `demand:`/`advise:`/`per:`/`why:` are
//! ordinary `Field`s over the claim-expression grammar. The
//! block words are recognized CONTEXTUALLY at statement-start only
//! (they also occur as ordinary path segments in value position, so
//! they are NOT lexer keywords; see [`block_intro_node`]). Bracketed
//! multi-line continuations are implicitly line-joined by the layout
//! pass, so a multi-line call/interval/import argument list is one
//! logical line. A stray closing bracket at statement position is the
//! one genuine in-body malformation: [`MALFORMED_IN_BODY`] (E0193),
//! attributed to the enclosing declaration subject for INV-20
//! per-subject gating. What remains `OpaqueIsland` is only the honest
//! residue (value-tail unit products, operator-led claim
//! continuations, `override`/`plan`/`flip`; WO-05 report note).
//!
//! Value/expression grammar: a Pratt precedence-climbing parser over
//! comparisons (`< > <= >= == =`), `+ -`, `* /`, unary `-`, quantity
//! literals (adjacent `Number` + `Ident`, e.g. `5 mm`), parenthesized
//! expressions, dotted paths, calls, `[a, b]` intervals, `[i .. j]`
//! ranges, `+- N%` tolerance, `default`/`derived`/`free`/`allocated`
//! cause values, `in [...]` value sources, `within [lo, hi]` demanded
//! windows, and a `during <expr>`
//! clause usable both as a trailing claim qualifier and as a call
//! argument (`peak(x, during boundary.launch)`). Any expression shape
//! this grammar cannot classify is swept losslessly into a trailing
//! `OpaqueIsland` rather than erroring (AD-3 fuzz invariant); this
//! degrades gracefully instead of guessing at unspecified syntax.

use camino::Utf8PathBuf;
use regolith_diag::{DiagCode, Diagnostic, Family, LabeledSpan, Span};
use rowan::{Checkpoint, GreenNode, GreenNodeBuilder, Language as _};

use crate::checks;
use crate::cst::{RegolithLanguage, SyntaxNode};
use crate::layout::{apply_layout, LayoutToken};
use crate::syntax_kind::SyntaxKind;
use crate::token::lex;

/// `E01xx`: a token appeared where no statement/declaration could
/// start; recovery skips it and resyncs on the next layout token.
const UNEXPECTED_TOKEN: DiagCode = DiagCode::new(Family::Parse, 92);

/// `E0193`: a statement inside a declaration body could not start any
/// field/statement/nested block (a stray operator or punctuation token
/// at statement position). Unlike [`UNEXPECTED_TOKEN`] this error is
/// ATTRIBUTED to the enclosing declaration subject via a secondary
/// span, so per-subject check gating (INV-20) can exclude exactly that
/// subject rather than treating the whole file as unaffected.
const MALFORMED_IN_BODY: DiagCode = DiagCode::new(Family::Parse, 93);

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
        subjects: Vec::new(),
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
    /// Stack of enclosing declaration subjects (name + header span),
    /// pushed while parsing a declaration body. The innermost entry
    /// attributes any in-body parse error to its subject (INV-20).
    subjects: Vec<(String, Span)>,
}

/// Contextually recognized domain block-introducer words. These are
/// NOT lexer keywords: `stage`, `zones`, `boundary`, and `flows` also
/// appear as ordinary path segments in value position (`boundary.x`,
/// `milled.zones`), so promoting them to hard keywords would break path
/// parsing. They are recognized ONLY at statement-start position (see
/// [`Parser::block_intro_kind`]). Each maps to the typed node wrapping
/// its `header-line + indented stmt-block` body.
fn block_intro_node(text: &str) -> Option<SyntaxKind> {
    Some(match text {
        "stage" => SyntaxKind::StageStmt,
        "setup" => SyntaxKind::SetupStmt,
        "connect" => SyntaxKind::ConnectBlock,
        "parts" => SyntaxKind::PartsBlock,
        "zones" => SyntaxKind::ZonesBlock,
        "boundary" => SyntaxKind::BoundaryBlock,
        "flows" => SyntaxKind::FlowsBlock,
        "walk" => SyntaxKind::WalkBody,
        "regions" => SyntaxKind::RegionsBlock,
        "constraints" => SyntaxKind::ConstraintsBlock,
        "exports" => SyntaxKind::ExportsBlock,
        "hole" => SyntaxKind::HoleBlock,
        // cuprite/05 sec. 1: the computer-track boundary-demand block.
        "workloads" => SyntaxKind::WorkloadsBlock,
        _ => return None,
    })
}

/// Contextually recognized single-line ownership/region/symmetry
/// statement verbs (INV-04/05/23). Like [`block_intro_node`] these are
/// NOT lexer keywords -- `region`, `route`, `pattern` also occur as path
/// segments and field names -- so they are recognized ONLY at
/// statement-start position with an argument follower (see
/// [`Parser::line_stmt_kind`]). Each maps to the typed single-line node
/// whose leading verb token the lowering pass reads back.
fn line_stmt_node(text: &str) -> Option<SyntaxKind> {
    Some(match text {
        // Ownership: borrow / modifying feature (INV-05).
        "bind" | "modify" => SyntaxKind::OwnershipStmt,
        // Regions: owned region / route touching one (INV-23).
        "region" | "keepout" | "route" => SyntaxKind::RegionStmt,
        // Symmetry: orbit contribution / break / extension / neutral
        // mirror promotions (INV-04).
        "pattern" | "break" | "any" | "symmetric" | "mirror" | "flip" => SyntaxKind::SymmetryStmt,
        // Query resolution (INV-06/18): `feature <name>` declares a named
        // entity into the scope snapshot; `refer <name>` resolves a `.only`
        // query against it.
        "feature" | "refer" => SyntaxKind::QueryStmt,
        // cuprite/05 sec. 1a (EOPEN-15): a workload/intent ledger claim.
        // Standalone at statement-start with an `Ident` follower (an
        // intent name); also parsed nested as a `WorkloadStmt` trailing
        // clause via `parse_realizes_stmt` (the corpus shape).
        "realizes" => SyntaxKind::RealizesStmt,
        _ => return None,
    })
}

/// The subset of [`line_stmt_node`] verbs that are recognized even when
/// followed by `(` (a call-like form, `symmetric(a, b)`) rather than a
/// bare identifier argument. The others require an `Ident` follower so a
/// coincidental field (`region: x`) or ctor (`route = y`) is never
/// mis-promoted.
fn line_stmt_word_allows_paren(text: &str) -> bool {
    matches!(text, "symmetric" | "mirror" | "flip" | "break" | "any")
}

/// Top-level declaration keywords (regolith/08; WO-05 scope list).
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
    /// `name <= value`: a non-blocking register assignment inside an
    /// `on <event>:` behavioral body (cuprite/03 sec. 1a; a ZOH delta).
    Reg,
    /// A domain-specific shape this WO defers: swallowed whole as one
    /// [`SyntaxKind::OpaqueIsland`] statement.
    Opaque,
}

/// Which body grammar an indented block parses (see
/// [`Parser::enter_body`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BodyKind {
    /// The shared statement grammar (fields, ctors, keyword blocks).
    Stmt,
    /// A `walk:` sketch body (WO-11 walk steps).
    Walk,
    /// A `workloads:` body (cuprite/05 sec. 1 `WorkloadStmt` lines).
    Workloads,
    /// A `process` decl body: the shared statement grammar plus the
    /// contextual `capability:`/`dfm:`/`drc:`/`erc:` blocks (WO-28;
    /// hematite/02 sec. 10).
    Process,
    /// A `dfm:`/`drc:`/`erc:` pack body: `rule <name>:` declarations
    /// over the shared statement grammar.
    RulePack,
    /// A `rule <name>:` body: `forall`/`resolves:`/`expect:` promoted;
    /// `demand:`/`advise:`/`per:`/`why:` stay ordinary fields.
    Rule,
    /// An `expect:` body: `pass:`/`fail:` fixture cases.
    Expect,
}

/// The context-sensitive statement words each [`BodyKind`] adds on top
/// of the shared statement grammar. Like the block words these are
/// CONTEXTUAL, never lexer keywords (cycle 18 D85): `process=` stage
/// headers, `dfm(rule)` waive targets, and `capability.x` value paths
/// all keep their plain `Ident` tokens, and a coincidental `dfm: 5`
/// field outside a process body is never promoted.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StmtCtx {
    /// No extra words: the shared statement grammar as before.
    Generic,
    /// `capability:` -> [`SyntaxKind::CapabilityBlock`];
    /// `dfm:`/`drc:`/`erc:` -> [`SyntaxKind::RulePackBlock`].
    Process,
    /// `rule <name>:` -> [`SyntaxKind::RuleDecl`].
    RulePack,
    /// `forall <var> in <query>` -> [`SyntaxKind::ForallClause`];
    /// `resolves: <field> from free` -> [`SyntaxKind::ResolvesClause`];
    /// `expect:` -> [`SyntaxKind::ExpectBlock`].
    Rule,
    /// `pass: <fixture>` / `fail: <fixture>` -> [`SyntaxKind::ExpectCase`].
    Expect,
}

/// Whether `kind` can plausibly begin (or continue) a statement inside
/// a declaration body. Only a STRAY CLOSING bracket (`)` / `]`) at
/// statement position is treated as a genuine malformation: it can
/// neither start a statement nor continue a multi-line expression, so
/// there is no legitimate reading. Every other leading token -- names,
/// numbers, keywords, AND leading operators/`.` (which legitimately
/// continue a multi-line claim expression, swept as an opaque
/// continuation per the WO-05 report note) -- stays non-erroring, so
/// the valid corpus is diagnostic-clean. Layout tokens never reach
/// here (the block loop handles them).
fn is_plausible_stmt_start(kind: SyntaxKind) -> bool {
    !matches!(kind, SyntaxKind::RParen | SyntaxKind::RBracket)
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
            .token(RegolithLanguage::kind_to_raw(tok.kind), text);
        self.pos += 1;
    }

    fn start(&mut self, kind: SyntaxKind) {
        self.builder.start_node(RegolithLanguage::kind_to_raw(kind));
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
            .start_node_at(cp, RegolithLanguage::kind_to_raw(kind));
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
                // A top-level `require <Group>:` claim group is the
                // fluorite decl-position form (fluorite/02 sec. 6); the
                // `require` keyword also introduces nested claim blocks
                // inside hema/cupr bodies (handled in `parse_stmt_block`).
                Some(SyntaxKind::RequireKw) => {
                    self.parse_simple_fluid_decl(SyntaxKind::RequireDecl);
                }
                Some(k) if is_decl_start(k) => self.parse_decl(),
                // The fluorite top-level declarators (`medium`, `flownet`)
                // are CONTEXTUAL idents, not lexer keywords (D85 idiom):
                // they also occur as ordinary path segments/field names.
                Some(SyntaxKind::Ident) if self.leading_ident_text() == Some("medium") => {
                    self.parse_simple_fluid_decl(SyntaxKind::MediumDecl);
                }
                Some(SyntaxKind::Ident) if self.leading_ident_text() == Some("flownet") => {
                    self.parse_flownet_decl();
                }
                // Any other identifier-led top-level line is a declaration
                // whose keyword this grammar does not yet model (`bind`,
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
        // A `process` declaration (hematite/04 sec. 2A) is Ident-led --
        // `process` is contextual, never a lexer keyword, because it
        // also appears as `process=<module>` in every stage header
        // (cycle 18 D85). Its body gets the Process statement context
        // so `capability:` and the rule-pack blocks are typed.
        let is_process = self.current() == Some(SyntaxKind::Ident)
            && &self.source[self.toks[self.pos].span.clone()] == "process";
        let subject = self.consume_decl_header();
        if let Some(s) = subject.clone() {
            self.subjects.push(s);
        }
        if is_process {
            self.enter_body(BodyKind::Process);
        } else {
            self.enter_body_block();
        }
        if subject.is_some() {
            self.subjects.pop();
        }
        self.finish();
    }

    /// The text of the leading (statement/decl-start) `Ident` token at
    /// `self.pos`, skipping intra-line whitespace, or `None` if the next
    /// significant token is not an `Ident`. The contextual-word lookahead
    /// for the fluorite top-level declarators (mirrors
    /// [`Parser::block_intro_kind`]'s idiom).
    fn leading_ident_text(&self) -> Option<&str> {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        let tok = self.toks.get(idx)?;
        (tok.kind == SyntaxKind::Ident).then(|| &self.source[tok.span.clone()])
    }

    /// A fluorite declaration whose body is the shared statement block:
    /// `medium <name>: <phase>` (fluorite/02 sec. 1) and the top-level
    /// `require <Group>:` claim group (sec. 6). The header keyword (a
    /// contextual `medium` ident or the `require` keyword) and the name
    /// are lifted out by [`Parser::consume_decl_header`]; the body parses
    /// as ordinary fields/claims (INV-20 subject attribution preserved).
    fn parse_simple_fluid_decl(&mut self, node: SyntaxKind) {
        self.start(node);
        let subject = self.consume_decl_header();
        if let Some(s) = subject.clone() {
            self.subjects.push(s);
        }
        self.enter_body_block();
        if subject.is_some() {
            self.subjects.pop();
        }
        self.finish();
    }

    /// A `flownet <name>(medium=<ref>):` declaration (fluorite/02 sec. 4).
    /// The header (contextual `flownet` ident + name + `(medium=...)`
    /// config) is lifted by [`Parser::consume_decl_header`]; the body is
    /// parsed by [`Parser::parse_flownet_body`], which types the `edges:`
    /// and `states:` blocks and keeps `reference:`/`nodes:` as fields.
    fn parse_flownet_decl(&mut self) {
        self.start(SyntaxKind::FlownetDecl);
        let subject = self.consume_decl_header();
        if let Some(s) = subject.clone() {
            self.subjects.push(s);
        }
        self.parse_flownet_body();
        if subject.is_some() {
            self.subjects.pop();
        }
        self.finish();
    }

    /// The indented body of a flownet: `reference:`/`nodes:` fields, plus
    /// the contextually-typed `edges:` -> [`SyntaxKind::EdgesBlock`] and
    /// `states:` -> [`SyntaxKind::StatesBlock`] blocks. Mirrors
    /// [`Parser::enter_body`]: it looks past blank/comment trivia to the
    /// body `Indent`, consumes it, and consumes the matching `Dedent`.
    fn parse_flownet_body(&mut self) {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
        ) {
            idx += 1;
        }
        if self.toks.get(idx).map(|t| t.kind) != Some(SyntaxKind::Indent) {
            return;
        }
        while self.pos < idx {
            self.bump();
        }
        self.bump(); // Indent
        loop {
            while matches!(
                self.current(),
                Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
            ) {
                self.bump();
            }
            if matches!(self.current(), None | Some(SyntaxKind::Dedent)) {
                break;
            }
            let lead = self.leading_ident_text().map(str::to_string);
            match lead.as_deref() {
                Some("edges") => self.parse_fluid_line_block(SyntaxKind::EdgesBlock),
                Some("states") => self.parse_fluid_line_block(SyntaxKind::StatesBlock),
                // `reference:` / `nodes:` and any other line: the shared
                // statement grammar (fields, ctors, opaque tails).
                _ => self.parse_generic_stmt(),
            }
        }
        if self.current() == Some(SyntaxKind::Dedent) {
            self.bump();
        }
    }

    /// An `edges:`/`states:` block: a typed header line + an indented
    /// body whose every line is one typed member statement
    /// ([`SyntaxKind::EdgeStmt`] for edges, [`SyntaxKind::StateStmt`] for
    /// states). Consumes the block's `Dedent` (mirrors
    /// [`Parser::parse_workloads_block`]).
    fn parse_fluid_line_block(&mut self, block: SyntaxKind) {
        let member = if block == SyntaxKind::EdgesBlock {
            SyntaxKind::EdgeStmt
        } else {
            SyntaxKind::StateStmt
        };
        self.start(block);
        self.consume_header_line();
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
            loop {
                while matches!(
                    self.current(),
                    Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
                ) {
                    self.bump();
                }
                match self.current() {
                    None | Some(SyntaxKind::Dedent) => break,
                    _ => self.parse_fluid_member(member),
                }
            }
            if self.current() == Some(SyntaxKind::Dedent) {
                self.bump();
            }
        }
        self.finish();
    }

    /// One `edges:`/`states:` member line, wrapped in its typed node.
    /// An [`SyntaxKind::EdgeStmt`] is `name`-led and reuses the field
    /// value/tail grammar (its constructor call is a `CallExpr`, the
    /// arrow-shaped sense pair rides as an opaque tail / continuation
    /// body); every other shape (a bare `state ...`/`event ...` line, an
    /// `<edge>.<param> in {...}` domain) is recorded whole as a typed
    /// leaf, preserving byte-lossless round-trip.
    fn parse_fluid_member(&mut self, member: SyntaxKind) {
        self.start(member);
        if member == SyntaxKind::EdgeStmt
            && matches!(self.stmt_shape(), StmtShape::Field | StmtShape::Ctor)
        {
            self.bump_name_path();
            self.skip_ws();
            self.bump(); // Colon / Eq
            self.parse_value_and_tail();
        } else {
            self.consume_header_line();
        }
        self.finish();
    }

    /// Consume a declaration header (`keyword name [<generics>] rest...`),
    /// wrapping any generic-parameter list `<...>` in a typed
    /// [`SyntaxKind::GenericParams`] node, and return the subject
    /// (declaration name + its span) for in-body error attribution.
    ///
    /// The rest of the header (`for <target>`, `as <alias>`, trailing
    /// config) is consumed as tokens without further decomposition
    /// (WO-05 report note); only the name and the generic list are
    /// lifted out.
    fn consume_decl_header(&mut self) -> Option<(String, Span)> {
        self.skip_ws();
        // Declaration keyword (a real Kw, or an Ident for a decl whose
        // keyword this grammar does not yet model).
        if !matches!(self.current(), None | Some(SyntaxKind::Newline)) {
            self.bump();
        }
        self.skip_ws();
        let subject = if self.current() == Some(SyntaxKind::Ident) {
            let tok = &self.toks[self.pos];
            let name = self.source[tok.span.clone()].to_string();
            let span = Span::new(self.file.clone(), tok.span.start, tok.span.end);
            self.bump();
            Some((name, span))
        } else {
            None
        };
        self.skip_ws();
        if self.current() == Some(SyntaxKind::Lt) {
            self.parse_generic_params();
        }
        self.consume_header_line();
        subject
    }

    /// `<...>` on a declaration header: recorded as one typed node with
    /// balanced angle-bracket nesting (`PatternOf<CBore<M8>>`), params
    /// not further decomposed (a structure-recorded partial node, never
    /// a swallowed error).
    fn parse_generic_params(&mut self) {
        self.start(SyntaxKind::GenericParams);
        self.bump(); // Lt
        let mut depth = 1i32;
        while depth > 0 {
            match self.current() {
                None | Some(SyntaxKind::Newline) => break,
                Some(SyntaxKind::Lt) => {
                    depth += 1;
                    self.bump();
                }
                Some(SyntaxKind::Gt) => {
                    depth -= 1;
                    self.bump();
                }
                Some(_) => self.bump(),
            }
        }
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
        self.enter_body(BodyKind::Stmt);
    }

    /// Shared body-opener: look PAST blank/comment/newline trivia to the
    /// body's `Indent` (the layout pass places it after such lines); if
    /// one follows, consume the trivia + `Indent` and parse the body per
    /// `kind`. If no `Indent` follows, consume nothing (the trivia
    /// belongs to a sibling / closing `Dedent`, TRIAGE cycle 11).
    fn enter_body(&mut self, kind: BodyKind) {
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
            match kind {
                BodyKind::Stmt => self.parse_stmt_block(StmtCtx::Generic),
                BodyKind::Walk => self.parse_walk_block(),
                BodyKind::Workloads => self.parse_workloads_block(),
                BodyKind::Process => self.parse_stmt_block(StmtCtx::Process),
                BodyKind::RulePack => self.parse_stmt_block(StmtCtx::RulePack),
                BodyKind::Rule => self.parse_stmt_block(StmtCtx::Rule),
                BodyKind::Expect => self.parse_stmt_block(StmtCtx::Expect),
            }
        }
    }

    /// A contextually-recognized domain block: header line + typed
    /// indented body (a `walk:` body parses walk steps; every other
    /// block parses the shared statement grammar). Promoted from the
    /// WO-05 residual-opaque list; comment-led bodies open correctly
    /// because [`Parser::enter_body`] looks past trivia to the `Indent`.
    fn parse_block_stmt(&mut self, kind: SyntaxKind) {
        self.start(kind);
        self.consume_header_line();
        if kind == SyntaxKind::WalkBody {
            self.enter_body(BodyKind::Walk);
        } else if kind == SyntaxKind::WorkloadsBlock {
            self.enter_body(BodyKind::Workloads);
        } else {
            self.enter_body(BodyKind::Stmt);
        }
        self.finish();
    }

    /// A `walk:` body (WO-11): one [`SyntaxKind::WalkStep`] per line
    /// (`from <datum>`, `line <dir>`, `arc ...`, `close [via axis]`,
    /// tangent/perpendicular joins, `bulge=...`), except a nested
    /// `hole <name>:` sub-profile which opens its own block (one nesting
    /// level). Consumes the closing `Dedent`.
    fn parse_walk_block(&mut self) {
        loop {
            while matches!(
                self.current(),
                Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
            ) {
                self.bump();
            }
            match self.current() {
                None | Some(SyntaxKind::Dedent) => break,
                Some(SyntaxKind::Ident)
                    if self.block_intro_kind() == Some(SyntaxKind::HoleBlock) =>
                {
                    self.parse_block_stmt(SyntaxKind::HoleBlock);
                }
                Some(_) => self.parse_walk_step(),
            }
        }
        if self.current() == Some(SyntaxKind::Dedent) {
            self.bump();
        }
    }

    /// One walk step, recorded as a typed leaf spanning its line (WO-11
    /// records the step; the direction-word / join / bulge semantics are
    /// the ledger half's job, out of the grammar's scope).
    fn parse_walk_step(&mut self) {
        self.start(SyntaxKind::WalkStep);
        self.consume_header_line();
        self.finish();
    }

    /// A `workloads:` body (cuprite/05 sec. 1): one [`SyntaxKind::WorkloadStmt`]
    /// per line until the matching `Dedent`. Consumes that `Dedent`.
    fn parse_workloads_block(&mut self) {
        loop {
            while matches!(
                self.current(),
                Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
            ) {
                self.bump();
            }
            match self.current() {
                None | Some(SyntaxKind::Dedent) => break,
                // A workload line always leads with its name (an
                // `Ident`, per cuprite/05 sec. 1); anything else inside
                // this block is unstructured residue this WO does not
                // model (AD-3: never invented, degrades to
                // `OpaqueIsland` rather than corrupting the tree).
                Some(SyntaxKind::Ident) => self.parse_workload_stmt(),
                Some(_) => self.parse_opaque_stmt(),
            }
        }
        if self.current() == Some(SyntaxKind::Dedent) {
            self.bump();
        }
    }

    /// One `workloads:` line (cuprite/05 sec. 1): `<name>: <kind>(<params>)
    /// [realizes <intent>[, <intent>...]]`, `<kind>` in `{loop, stream,
    /// event, batch}`. The name and kind are lifted out as tokens; the
    /// parameter group is recorded whole as a [`SyntaxKind::WorkloadParams`]
    /// node (structure recorded, not further decomposed -- the params mix
    /// claim/field/ctor shapes the statement value-grammar does not unify,
    /// the same "recorded, not decomposed" idiom as `GenericParams` and the
    /// `parts:` orbit constructors, WO-05 report note). A trailing
    /// `realizes` clause nests as a typed [`SyntaxKind::RealizesStmt`]
    /// (shared with the standalone form, see [`Parser::parse_realizes_stmt`]).
    fn parse_workload_stmt(&mut self) {
        self.start(SyntaxKind::WorkloadStmt);
        if self.current() == Some(SyntaxKind::Ident) {
            self.bump_name_path();
        }
        self.skip_ws();
        if self.current() == Some(SyntaxKind::Colon) {
            self.bump();
        }
        self.skip_ws();
        // The workload kind (`loop`/`stream`/`event`/`batch`): not a
        // lexer keyword (WO-05 idiom -- these are ordinary idents), so
        // just lift the bare name token.
        if self.current() == Some(SyntaxKind::Ident) {
            self.bump();
        }
        self.skip_ws();
        if self.current() == Some(SyntaxKind::LParen) {
            self.parse_workload_params();
        }
        self.skip_ws();
        if self.at_realizes_ident() {
            // Shared with the standalone statement-start dispatch (see
            // `line_stmt_kind`/`parse_stmt_block`): both positions reach
            // `parse_line_stmt` once the `realizes` ident is confirmed
            // current, consuming through the line's `Newline`.
            self.parse_line_stmt(SyntaxKind::RealizesStmt);
        } else {
            self.consume_header_line();
        }
        self.finish();
    }

    /// True when the current position (past whitespace) is the `realizes`
    /// ident, used to recognize the trailing clause on a `WorkloadStmt`
    /// line without a dedicated lexer keyword (mirrors [`block_intro_node`]/
    /// [`line_stmt_node`]'s contextual-word idiom).
    fn at_realizes_ident(&self) -> bool {
        matches!(self.current(), Some(SyntaxKind::Ident))
            && &self.source[self.toks[self.pos].span.clone()] == "realizes"
    }

    /// The balanced `(...)` parameter group of a `WorkloadStmt`, recorded
    /// whole (never decomposed further, matching [`Parser::parse_generic_params`]'s
    /// idiom): bracket depth is tracked so a nested call inside a param
    /// value (`headroom(...)`) stays inside the group.
    fn parse_workload_params(&mut self) {
        self.start(SyntaxKind::WorkloadParams);
        self.bump(); // LParen
        let mut depth = 1i32;
        while depth > 0 {
            match self.current() {
                None | Some(SyntaxKind::Newline) => break,
                Some(SyntaxKind::LParen) => {
                    depth += 1;
                    self.bump();
                }
                Some(SyntaxKind::RParen) => {
                    depth -= 1;
                    self.bump();
                }
                Some(_) => self.bump(),
            }
        }
        self.finish();
    }

    /// A `policy:` rule line (`prefer ... over ...`, `forbid ...`,
    /// `minimize ...`, `maximize ...`, `use ...`): a single-line typed
    /// leaf (no body).
    fn parse_policy_rule(&mut self) {
        self.start(SyntaxKind::PolicyRule);
        self.consume_header_line();
        self.finish();
    }

    /// If the statement starting at `self.pos` is a contextually-
    /// recognized domain block, return its node kind. A block word is
    /// only an introducer when it is a bare leading `Ident` (NOT a
    /// dotted path `boundary.x` and NOT a `name = ...` ctor) followed by
    /// a nested-block shape: `<word>:` or `<word> <ident...>:`.
    fn block_intro_kind(&self) -> Option<SyntaxKind> {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        let tok = self.toks.get(idx)?;
        if tok.kind != SyntaxKind::Ident {
            return None;
        }
        let node = block_intro_node(&self.source[tok.span.clone()])?;
        // The token after the single leading word decides: a `.` (dotted
        // path) or `=` (ctor) means this is an ordinary field/ctor whose
        // name merely coincides with a block word; a `:` or a further
        // `Ident` (`stage cut`, `zones over`) confirms a block header.
        match self.peek_significant_kind_at(idx + 1) {
            Some(SyntaxKind::Colon | SyntaxKind::Ident) => Some(node),
            _ => None,
        }
    }

    /// If the statement starting at `self.pos` is a contextually-
    /// recognized single-line ownership/region/symmetry statement, return
    /// its typed node kind. Recognized only when the leading bare `Ident`
    /// is one of the [`line_stmt_node`] verbs AND its follower is an
    /// argument: an `Ident` for all verbs, plus `(` for the call-like
    /// mirror verbs ([`line_stmt_word_allows_paren`]). A `:`/`=`/`.`
    /// follower means an ordinary field/ctor/path whose name merely
    /// coincides with a verb -- left to the generic dispatch.
    fn line_stmt_kind(&self) -> Option<SyntaxKind> {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        let tok = self.toks.get(idx)?;
        if tok.kind != SyntaxKind::Ident {
            return None;
        }
        let text = &self.source[tok.span.clone()];
        let node = line_stmt_node(text)?;
        match self.peek_significant_kind_at(idx + 1) {
            Some(SyntaxKind::Ident) => Some(node),
            Some(SyntaxKind::LParen) if line_stmt_word_allows_paren(text) => Some(node),
            _ => None,
        }
    }

    /// Parse a contextually-recognized single-line ownership/region/
    /// symmetry statement: a typed node wrapping the header line (no
    /// body). The lowering pass reads the leading verb token and the
    /// argument names back off the node's tokens.
    fn parse_line_stmt(&mut self, kind: SyntaxKind) {
        self.start(kind);
        self.consume_header_line();
        self.finish();
    }

    /// A malformed statement inside a declaration body: emit an
    /// [`MALFORMED_IN_BODY`] diagnostic ATTRIBUTED to the enclosing
    /// declaration subject (a secondary span into the subject's header,
    /// consumable by per-subject INV-20 gating), wrap the offending
    /// token in a [`SyntaxKind::SubjectError`] node, and advance one
    /// token to resync (AD-3 layout-anchored recovery).
    fn parse_subject_error(&mut self) {
        let tok = &self.toks[self.pos];
        let span = Span::new(self.file.clone(), tok.span.start, tok.span.end);
        let subject = self.subjects.last().cloned();
        let msg = match &subject {
            Some((name, _)) => {
                format!("malformed statement in declaration `{name}`")
            }
            None => "malformed statement here".to_string(),
        };
        let mut diag = Diagnostic::error(MALFORMED_IN_BODY, msg).with_span(LabeledSpan::new(
            span,
            "expected a field, statement, or nested block",
        ));
        if let Some((name, subject_span)) = subject {
            diag = diag.with_span(LabeledSpan::new(
                subject_span,
                format!("in declaration `{name}`"),
            ));
        }
        self.diags.push(diag);
        self.start(SyntaxKind::SubjectError);
        self.bump();
        self.finish();
    }

    /// The shared statement-block grammar: one statement per line until
    /// the matching `Dedent`. Consumes that `Dedent`. `ctx` adds the
    /// context-sensitive rule-pack words (WO-28) IN FRONT of the shared
    /// arms; everything unrecognized in every context falls through to
    /// the same generic dispatch, so a malformed rule line degrades per
    /// statement (batch diagnostics, AD-3) and never eats the block.
    fn parse_stmt_block(&mut self, ctx: StmtCtx) {
        loop {
            while matches!(
                self.current(),
                Some(SyntaxKind::Whitespace | SyntaxKind::Comment | SyntaxKind::Newline)
            ) {
                self.bump();
            }
            if !matches!(self.current(), None | Some(SyntaxKind::Dedent))
                && self.try_parse_ctx_stmt(ctx)
            {
                continue;
            }
            match self.current() {
                None | Some(SyntaxKind::Dedent) => break,
                Some(SyntaxKind::RequireKw) => self.parse_keyword_block(SyntaxKind::RequireClaim),
                Some(SyntaxKind::ThenKw) => self.parse_keyword_block(SyntaxKind::ThenScope),
                Some(SyntaxKind::BudgetKw) => self.parse_keyword_block(SyntaxKind::BudgetStmt),
                Some(SyntaxKind::WaiveKw) => self.parse_keyword_block(SyntaxKind::WaiveBlock),
                Some(SyntaxKind::PolicyKw) => self.parse_keyword_block(SyntaxKind::PolicyBlock),
                Some(SyntaxKind::LockedKw) => self.parse_keyword_block(SyntaxKind::LockedBlock),
                // `impl <Trait> for <target> [as <alias>]:` role binding
                // inside a declaration body (a typed block, promoted from
                // the WO-05 residual-opaque list).
                Some(SyntaxKind::ImplKw) => self.parse_block_stmt(SyntaxKind::ImplStmt),
                // `on <event>:` clocked behavioral body (cuprite/03 sec.
                // 1): a header line + nested stmt-block whose `<=` lines
                // are register deltas and `=` lines are combinational,
                // all in the event's clock domain. Feeds the INV-16
                // converter graph (`regolith-lower::converter`). `on` is
                // a lexer keyword (`OnKw`), so unlike the ident-led block
                // words it is dispatched directly here.
                Some(SyntaxKind::OnKw) => self.parse_keyword_block(SyntaxKind::OnBlock),
                // `policy:` rule lines (also legal as free-standing block
                // statements): a single-line typed leaf.
                Some(
                    SyntaxKind::PreferKw
                    | SyntaxKind::ForbidKw
                    | SyntaxKind::MinimizeKw
                    | SyntaxKind::MaximizeKw
                    | SyntaxKind::UseKw,
                ) => self.parse_policy_rule(),
                // A `@hint(...)` annotation (regolith/12 rung 3): the `@`
                // sigil begins a verdict-inert hint statement, swallowed
                // whole as a typed [`SyntaxKind::HintStmt`]. No lowering
                // pass reads it, so it perturbs neither obligations nor
                // resolutions (INV-03 droppability, by construction).
                Some(SyntaxKind::AtTok) => self.parse_line_stmt(SyntaxKind::HintStmt),
                // A contextually-recognized single-line ownership/region/
                // symmetry statement (`bind`/`modify`, `region`/`keepout`/
                // `route`, `pattern`/`break`/`any`/`symmetric`/`mirror`/
                // `flip`): a typed leaf the lowering pass reads back for
                // predicted-delta / region / orbit population (INV-04/05/23).
                Some(SyntaxKind::Ident) if self.line_stmt_kind().is_some() => {
                    let kind = self.line_stmt_kind().expect("checked Some above");
                    self.parse_line_stmt(kind);
                }
                // A contextually-recognized domain block (`stage`, `setup`,
                // `connect`, `parts`, `zones`, `boundary`, `flows`, `walk`,
                // `hole`, `regions`, `constraints`, `exports`): a typed
                // header + stmt-block body.
                Some(SyntaxKind::Ident) if self.block_intro_kind().is_some() => {
                    let kind = self.block_intro_kind().expect("checked Some above");
                    self.parse_block_stmt(kind);
                }
                // A stray operator/punctuation token cannot start any
                // statement inside a body: a genuine malformation,
                // attributed to the enclosing declaration subject (INV-20)
                // rather than silently swallowed.
                Some(k) if !is_plausible_stmt_start(k) => self.parse_subject_error(),
                Some(_) => self.parse_generic_stmt(),
            }
        }
        if self.current() == Some(SyntaxKind::Dedent) {
            self.bump();
        }
    }

    /// Try to parse one context-sensitive rule-pack statement (WO-28;
    /// hematite/02 sec. 10, cuprite/04 sec. 4). Returns `true` if the
    /// statement was recognized and consumed for `ctx`; `false` leaves
    /// the position untouched for the generic dispatch. All words are
    /// contextual idents (cycle 18 D85), recognized only at
    /// statement-start with the follower each shape requires, so
    /// coincidental fields/ctors/paths are never mis-promoted.
    fn try_parse_ctx_stmt(&mut self, ctx: StmtCtx) -> bool {
        let Some((word, follower)) = self.stmt_start_ident_and_follower() else {
            return false;
        };
        match (ctx, word.as_str(), follower) {
            // `capability:` -- the provider-envelope table; its body is
            // ordinary fields (the shared grammar).
            (StmtCtx::Process, "capability", Some(SyntaxKind::Colon)) => {
                self.start(SyntaxKind::CapabilityBlock);
                self.consume_header_line();
                self.enter_body(BodyKind::Stmt);
                self.finish();
                true
            }
            // `dfm:` / `drc:` / `erc:` -- a rule-pack block; the family
            // word is the node's leading token (read back by the AST).
            (StmtCtx::Process, "dfm" | "drc" | "erc", Some(SyntaxKind::Colon)) => {
                self.start(SyntaxKind::RulePackBlock);
                self.consume_header_line();
                self.enter_body(BodyKind::RulePack);
                self.finish();
                true
            }
            // `rule <name>:` -- one named, citable rule.
            (StmtCtx::RulePack, "rule", Some(SyntaxKind::Ident)) => {
                self.start(SyntaxKind::RuleDecl);
                self.consume_header_line();
                self.enter_body(BodyKind::Rule);
                self.finish();
                true
            }
            // `forall <var> in <query>` -- the match domain.
            (StmtCtx::Rule, "forall", Some(SyntaxKind::Ident)) => {
                self.parse_forall_clause();
                true
            }
            // `resolves: <field> from free` -- the eager-resolver marker.
            (StmtCtx::Rule, "resolves", Some(SyntaxKind::Colon)) => {
                self.parse_resolves_clause();
                true
            }
            // `expect:` -- the in-pack fixture block.
            (StmtCtx::Rule, "expect", Some(SyntaxKind::Colon)) => {
                self.start(SyntaxKind::ExpectBlock);
                self.consume_header_line();
                self.enter_body(BodyKind::Expect);
                self.finish();
                true
            }
            // `pass: <fixture>` / `fail: <fixture>` -- one expect case;
            // the fixture parses with the ordinary value grammar (a
            // `CallExpr` entity sketch), tails swept losslessly.
            (StmtCtx::Expect, "pass" | "fail", Some(SyntaxKind::Colon)) => {
                self.start(SyntaxKind::ExpectCase);
                self.skip_ws();
                self.bump(); // verdict word
                self.skip_ws();
                self.bump(); // Colon
                self.parse_value_and_tail();
                self.finish();
                true
            }
            _ => false,
        }
    }

    /// The bare leading `Ident` of the statement at `self.pos` plus its
    /// significant follower kind, without consuming (the shared
    /// lookahead of [`Parser::try_parse_ctx_stmt`]; mirrors
    /// [`Parser::block_intro_kind`]).
    fn stmt_start_ident_and_follower(&self) -> Option<(String, Option<SyntaxKind>)> {
        let mut idx = self.pos;
        while matches!(
            self.toks.get(idx).map(|t| t.kind),
            Some(SyntaxKind::Whitespace)
        ) {
            idx += 1;
        }
        let tok = self.toks.get(idx)?;
        if tok.kind != SyntaxKind::Ident {
            return None;
        }
        Some((
            self.source[tok.span.clone()].to_string(),
            self.peek_significant_kind_at(idx + 1),
        ))
    }

    /// `forall <var> in <query>`: the quantifier word and bound variable
    /// are tokens, the query parses with the expression grammar, and any
    /// unmodeled query tail (boolean connectives inside filters) is
    /// swept losslessly INSIDE the clause as an `OpaqueIsland` (cycle 18
    /// F95) -- structure recorded, never invented.
    fn parse_forall_clause(&mut self) {
        self.start(SyntaxKind::ForallClause);
        self.skip_ws();
        self.bump(); // `forall`
        self.skip_ws();
        if self.current() == Some(SyntaxKind::Ident) {
            self.bump(); // the bound variable
        }
        self.skip_ws();
        if self.current() == Some(SyntaxKind::InKw) {
            self.bump();
            self.skip_ws();
            if !matches!(
                self.current(),
                None | Some(SyntaxKind::Newline | SyntaxKind::Dedent)
            ) {
                self.parse_expr(0);
            }
        }
        self.skip_ws();
        if !matches!(
            self.current(),
            None | Some(SyntaxKind::Newline | SyntaxKind::Dedent)
        ) {
            self.start(SyntaxKind::OpaqueIsland);
            while !matches!(
                self.current(),
                None | Some(SyntaxKind::Newline | SyntaxKind::Dedent)
            ) {
                self.bump();
            }
            self.finish();
        }
        if self.current() == Some(SyntaxKind::Newline) {
            self.bump();
        }
        self.finish();
    }

    /// `resolves: <field> from free`: the target field is a name path;
    /// the `from free` tail rides as tokens (`from` is a contextual
    /// ident, `free` the value-source keyword) the AST reads back.
    fn parse_resolves_clause(&mut self) {
        self.start(SyntaxKind::ResolvesClause);
        self.skip_ws();
        self.bump(); // `resolves`
        self.skip_ws();
        self.bump(); // Colon
        self.skip_ws();
        if self.current() == Some(SyntaxKind::Ident) {
            self.bump_name_path();
        }
        self.consume_header_line(); // `from free` + newline
        self.finish();
    }

    /// `then [label] [on <region>]:`, `require <Group>:`, `budget ...:`,
    /// `waive ...:`, `policy:`, `locked:` -- header keyword + line, then
    /// a nested statement block (shared shape, cycle-3 additions
    /// included; regolith/08 sec. 4, regolith/12).
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
            Some(SyntaxKind::LtEq) => StmtShape::Reg,
            _ => StmtShape::Opaque,
        }
    }

    /// Dispatch a non-keyword-led statement line by its [`StmtShape`].
    fn parse_generic_stmt(&mut self) {
        match self.stmt_shape() {
            StmtShape::Field => self.parse_field(),
            StmtShape::Ctor => self.parse_ctor(),
            StmtShape::Reg => self.parse_reg_assign(),
            StmtShape::Opaque => self.parse_opaque_stmt(),
        }
    }

    /// `name <= value`: a non-blocking register assignment (cuprite/03
    /// sec. 1a). Same shape as a ctor but with the `<=` operator; the
    /// lowering pass reads the LHS name and RHS signal references back
    /// off the typed node to build a `ConverterGraph` register edge
    /// (INV-16). The commit is a ZOH delta, so it cannot close a
    /// zero-delay cycle.
    fn parse_reg_assign(&mut self) {
        self.start(SyntaxKind::RegAssign);
        self.bump_name_path();
        self.skip_ws();
        self.bump(); // LtEq
        self.parse_value_and_tail();
        self.finish();
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
    /// (regolith/03 value sources).
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
            // `within [lo, hi]`: a two-sided demanded window (regolith/03;
            // `Window` value type). Recognized ONLY when a `[` follows, so
            // the unrelated temporal `within <dur> after <event>` claim
            // form (which has no bracket) still degrades to an opaque tail
            // as before (FE-10). The `[lo, hi]` bracket parses as an
            // `IntervalExpr` wrapped in a typed `WindowExpr`.
            Some(SyntaxKind::WithinKw)
                if self.peek_significant_kind_at(self.pos + 1) == Some(SyntaxKind::LBracket) =>
            {
                let cp = self.checkpoint();
                self.bump(); // within
                self.skip_ws();
                self.parse_expr(0);
                self.start_node_at(cp, SyntaxKind::WindowExpr);
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
    /// (`..` -> [`SyntaxKind::RangeExpr`]) per regolith/02 sec. 3.
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

    /// A dotted `Path`/`NameRef`, optionally instantiated
    /// (`Foo<Bar>`) and/or called (`Ident(args)`).
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
        // Use-site generic instantiation: `Foo<...>` glued to the head
        // name (INV-11). Recognized ONLY when `<` immediately follows the
        // name (no intervening `Whitespace` token) AND the angle group
        // scans as a balanced, type-like argument list terminated by an
        // acceptable follower -- so a whitespace-separated claim
        // comparison (`a < b`) stays a `BinExpr` (it never reaches here
        // glued, and would fail the scan anyway). See `scan_generic_args`.
        if self.current() == Some(SyntaxKind::Lt) && self.scan_generic_args(self.pos).is_some() {
            self.parse_generic_args();
            self.start_node_at(cp, SyntaxKind::InstExpr);
            self.finish();
        }
        if self.current() == Some(SyntaxKind::LParen) {
            self.start_node_at(cp, SyntaxKind::CallExpr);
            self.parse_arg_list();
            self.finish();
        }
    }

    /// Non-consuming disambiguation for a use-site generic instantiation:
    /// starting at the glued `Lt` token index `start`, scan the balanced
    /// `<...>` angle group. Returns the token index just past the closing
    /// `>` when the group looks like a type-argument list, else `None`
    /// (in which case the `<` is a comparison operator and is left to the
    /// Pratt expression parser).
    ///
    /// A group qualifies only when: it closes on the same logical line
    /// (no `Newline`/`Indent`/`Dedent` inside); every inner token is
    /// type-argument-plausible (identifiers, numbers, commas, dots,
    /// colons, whitespace, nested `<`/`>`) -- any operator/bracket/paren
    /// disqualifies it; it has content; and the token after the closing
    /// `>` (past whitespace) is an acceptable follower (`(`, `,`, `>`,
    /// `)`, `]`, a line end, or EOF). This excludes `a < b and c > d`
    /// (an `Ident` follows the close) and `mass < 5kg` (a `Newline`
    /// closes the scan before any `>`).
    fn scan_generic_args(&self, start: usize) -> Option<usize> {
        let mut i = start + 1; // past the opening `<`
        let mut depth = 1i32;
        let mut saw_content = false;
        while depth > 0 {
            match self.toks.get(i).map(|t| t.kind) {
                None | Some(SyntaxKind::Newline | SyntaxKind::Indent | SyntaxKind::Dedent) => {
                    return None;
                }
                Some(SyntaxKind::Lt) => {
                    depth += 1;
                    i += 1;
                }
                Some(SyntaxKind::Gt) => {
                    depth -= 1;
                    i += 1;
                }
                Some(
                    SyntaxKind::Ident
                    | SyntaxKind::Number
                    | SyntaxKind::Comma
                    | SyntaxKind::Dot
                    | SyntaxKind::Colon,
                ) => {
                    saw_content = true;
                    i += 1;
                }
                Some(SyntaxKind::Whitespace) => i += 1,
                // Any other token (operators, brackets, parens, `..`)
                // is not a type argument: this is a comparison, not an
                // instantiation.
                Some(_) => return None,
            }
        }
        if !saw_content {
            return None;
        }
        let mut j = i;
        while self.toks.get(j).map(|t| t.kind) == Some(SyntaxKind::Whitespace) {
            j += 1;
        }
        match self.toks.get(j).map(|t| t.kind) {
            None
            | Some(
                SyntaxKind::LParen
                | SyntaxKind::Comma
                | SyntaxKind::Gt
                | SyntaxKind::RParen
                | SyntaxKind::RBracket
                | SyntaxKind::Newline
                | SyntaxKind::Indent
                | SyntaxKind::Dedent,
            ) => Some(i),
            _ => None,
        }
    }

    /// Parse a use-site generic-argument list `<...>` into a typed
    /// [`SyntaxKind::GenericArgs`] node (the caller has confirmed via
    /// [`Parser::scan_generic_args`] that it is one). Each `Ident`-led
    /// argument is parsed via [`Parser::parse_path_or_call`], so a nested
    /// instantiation (`PatternOf<TappedHole<M3>>`) becomes a nested
    /// [`SyntaxKind::InstExpr`]; numbers become quantity/const args;
    /// commas separate. Balanced nesting is guaranteed by the scan.
    fn parse_generic_args(&mut self) {
        self.start(SyntaxKind::GenericArgs);
        self.bump(); // Lt
        loop {
            self.skip_ws();
            match self.current() {
                Some(SyntaxKind::Gt) => {
                    self.bump();
                    break;
                }
                None | Some(SyntaxKind::Newline | SyntaxKind::Indent | SyntaxKind::Dedent) => break,
                Some(SyntaxKind::Ident) => self.parse_path_or_call(),
                Some(SyntaxKind::Number) => {
                    let cp = self.checkpoint();
                    self.bump();
                    if self.current() == Some(SyntaxKind::Ident) {
                        self.bump(); // adjacent unit (`6mm`)
                        self.start_node_at(cp, SyntaxKind::QuantityLit);
                        self.finish();
                    }
                }
                // Separators/colons and any other token (const args,
                // stray punctuation) are consumed verbatim -- the scan
                // guaranteed the group is balanced and type-like.
                Some(_) => self.bump(),
            }
        }
        self.finish();
    }

    /// `(arg, arg, ...)`. Each argument is either a full positional
    /// expression (including `during <expr>`, handled as an atom) or a
    /// keyword argument `name: <value-expr>` -- the latter promoted to a
    /// typed [`SyntaxKind::KeywordArg`] so a comparison-bearing bound
    /// (`promises: >= 20Mops f32 sustained`, cuprite/05 sec. 2
    /// architecture-resource block contracts) is structured rather than
    /// bailing to an `OpaqueIsland` tail.
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
            self.parse_arg();
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

    /// One argument inside an [`SyntaxKind::ArgList`]: a keyword argument
    /// `name: <value>` when a bare `Ident` is immediately followed (past
    /// intra-line whitespace) by a `Colon`, else a positional expression.
    /// The keyword form structures a comparison-bearing promise bound
    /// (`promises: >= 20Mops f32 sustained`) into a typed
    /// [`SyntaxKind::KeywordArg`] carrying the name [`SyntaxKind::NameRef`]
    /// and the value grammar; any trailing qualifier residue (`f32
    /// sustained`) is swept losslessly to a bounded `OpaqueIsland` so the
    /// arg list stays balanced and closes its `RParen` (AD-3: never
    /// invent structure, never leak a tail out of the call).
    fn parse_arg(&mut self) {
        if self.current() == Some(SyntaxKind::Ident)
            && self.peek_significant_kind_at(self.pos + 1) == Some(SyntaxKind::Colon)
        {
            self.start(SyntaxKind::KeywordArg);
            let cp = self.checkpoint();
            self.bump(); // name Ident
            self.start_node_at(cp, SyntaxKind::NameRef);
            self.finish();
            self.skip_ws();
            self.bump(); // Colon
            self.skip_ws();
            if !matches!(
                self.current(),
                Some(
                    SyntaxKind::Comma
                        | SyntaxKind::RParen
                        | SyntaxKind::Newline
                        | SyntaxKind::Dedent
                ) | None
            ) {
                self.parse_value();
            }
            self.skip_ws();
            // Sweep trailing qualifier tokens up to the argument delimiter
            // (paren-balanced) into a lossless residue.
            if !matches!(
                self.current(),
                Some(
                    SyntaxKind::Comma
                        | SyntaxKind::RParen
                        | SyntaxKind::Newline
                        | SyntaxKind::Dedent
                ) | None
            ) {
                self.start(SyntaxKind::OpaqueIsland);
                let mut depth = 0i32;
                loop {
                    match self.current() {
                        None | Some(SyntaxKind::Newline | SyntaxKind::Dedent) => break,
                        Some(SyntaxKind::Comma | SyntaxKind::RParen) if depth == 0 => break,
                        Some(SyntaxKind::LParen) => {
                            depth += 1;
                            self.bump();
                        }
                        Some(SyntaxKind::RParen) => {
                            depth -= 1;
                            self.bump();
                        }
                        Some(_) => self.bump(),
                    }
                }
                self.finish();
            }
            self.finish();
        } else {
            self.parse_expr(0);
        }
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
        // Look PAST blank/comment/newline trivia to the body `Indent`
        // (the layout pass places it after such lines, so a comment-led
        // opaque body still opens instead of desyncing the `Dedent`
        // accounting -- the same trivia class as the TRIAGE cycle-11
        // fix, applied here to the deferred-opaque path).
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
    use crate::syntax_kind::SyntaxKind;
    use camino::Utf8PathBuf;

    fn workspace_root() -> std::path::PathBuf {
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(std::path::Path::parent)
            .expect("crates/regolith-syntax is two levels under the workspace root")
            .to_path_buf()
    }

    #[test]
    fn empty_file_parses() {
        let file = Utf8PathBuf::from("empty.hema");
        let p = parse("", &file);
        assert_eq!(p.syntax().text().to_string(), "");
    }

    #[test]
    fn only_comments_file_parses_with_no_diagnostics() {
        let file = Utf8PathBuf::from("comments.hema");
        let src = "# just a comment\n# another one\n";
        let p = parse(src, &file);
        assert!(p.diagnostics().is_empty());
        assert_eq!(p.syntax().text().to_string(), src);
    }

    #[test]
    fn broken_statement_does_not_eat_the_file() {
        let file = Utf8PathBuf::from("broken.hema");
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
            let file = Utf8PathBuf::from("t.hema");
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
            let file = Utf8PathBuf::from("prop.hema");
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
            if regolith_syntax_extensions().iter().all(|e| *e != ext) {
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
        let file = Utf8PathBuf::from("t.hema");
        let src = "part wall:\n    thickness: 4mm\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("Field"));
        assert!(dump.contains("QuantityLit"));
    }

    #[test]
    fn ctor_stmt_and_call_expr_parse_structurally() {
        let file = Utf8PathBuf::from("t.hema");
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
        let file = Utf8PathBuf::from("t.hema");
        let src = "part p:\n    require Structural:\n        trust: >= certified\n        stress: mech.stress(all) < sigma_y / 2\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("RequireClaim"));
        assert!(dump.contains("Field"));
    }

    #[test]
    fn interval_and_range_are_distinguished() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part p:\n    a: [1mm, 2mm]\n    b: [0 .. 3]\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let dump = format!("{:#?}", p.syntax());
        assert!(dump.contains("IntervalExpr"));
        assert!(dump.contains("RangeExpr"));
    }

    /// FE-10: `within [lo, hi]` in a value position produces a typed
    /// `WindowExpr` (a demanded two-sided window) wrapping the `[lo, hi]`
    /// `IntervalExpr`, with no diagnostics.
    #[test]
    fn within_window_is_a_typed_node() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part p:\n    stiffness: within [0.8, 1.6]\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(
            kinds.iter().any(|x| x == "WindowExpr"),
            "expected a WindowExpr node: {kinds:?}"
        );
        assert!(
            kinds.iter().any(|x| x == "IntervalExpr"),
            "the window wraps the [lo, hi] interval: {kinds:?}"
        );
        // No OpaqueIsland: `within [..]` is now fully structured.
        assert!(!kinds.iter().any(|x| x == "OpaqueIsland"), "{kinds:?}");
    }

    /// A `promises:` keyword argument inside a call (cuprite/05 sec. 2
    /// architecture-resource block contracts) structures into a typed
    /// `KeywordArg` carrying the name and a comparison-bearing bound, the
    /// call closes its `RParen` (the `ArgList` stays balanced), and there
    /// is no escaping tail island -- only the bounded qualifier residue
    /// (`f32 sustained`) inside the `KeywordArg`. No diagnostics.
    #[test]
    fn call_keyword_arg_structures_a_promise_bound() {
        let file = Utf8PathBuf::from("t.cupr");
        let src = "architecture for A:\n    resources:\n        cpu0: executor(promises: >= 20Mops f32 sustained)\n        dma: mover(promises: >= 40MB/s, independent of cpu0)\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(
            kinds.iter().filter(|x| *x == "KeywordArg").count() >= 2,
            "each promises: is a KeywordArg: {kinds:?}"
        );
        // The comparison bound is structured (UnaryExpr `>= ...`), not
        // swept whole.
        assert!(
            kinds.iter().any(|x| x == "UnaryExpr"),
            "the >= bound is a UnaryExpr: {kinds:?}"
        );
    }

    /// FE-10 guard: the temporal `within <dur> after <event>` claim form
    /// (no bracket) is NOT a window; it must stay unrecognized (opaque)
    /// and, crucially, must not be mis-parsed as a `WindowExpr`.
    #[test]
    fn temporal_within_is_not_a_window() {
        let file = Utf8PathBuf::from("t.cupr");
        let src = "board b:\n    settle: within 50ms after load_step\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(
            !kinds.iter().any(|x| x == "WindowExpr"),
            "temporal within must not be a window: {kinds:?}"
        );
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
        let path = workspace_root().join("examples/systems/cubesat/kestrel.cupr");
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

    /// The whole `examples/` corpus parses with ZERO parse diagnostics
    /// (WO-05 residual promotion + bracket-aware layout): every former
    /// residual opaque-construct desync is gone. A standing regression
    /// guard that the residual count stays at zero.
    ///
    /// DELIBERATE NEGATIVE FIXTURES are exempt (cycle 23, D119/D123:
    /// a diagnostic-bearing corpus file is rot UNLESS it is a
    /// deliberate negative fixture): any source file under a
    /// `negative/` directory -- the D123 rule-breaking corpus at
    /// `examples/negative/` and per-project negatives like
    /// `examples/systems/sdr_transceiver/negative/db_illegal.cupr` --
    /// is EXPECTED to carry diagnostics; those are driven by
    /// `tests/golden/test_negative_corpus.py` and excluded from the
    /// golden corpus paths instead.
    #[test]
    fn examples_have_no_parse_diagnostics() {
        let root = workspace_root().join("examples");
        let negative_dir = root.join("negative");
        for entry in walk(&root) {
            if entry.starts_with(&negative_dir) {
                continue;
            }
            let Some(ext) = entry.extension().and_then(|e| e.to_str()) else {
                continue;
            };
            if regolith_syntax_extensions().iter().all(|e| *e != ext) {
                continue;
            }
            if entry.components().any(|c| c.as_os_str() == "negative") {
                continue;
            }
            let src = std::fs::read_to_string(&entry).unwrap();
            let file = Utf8PathBuf::from_path_buf(entry.clone()).unwrap();
            let p = parse(&src, &file);
            assert!(
                p.diagnostics().is_empty(),
                "{entry:?} must parse with no diagnostics: {:?}",
                p.diagnostics()
            );
        }
    }

    /// Every promoted domain construct becomes a typed CST node (not an
    /// `OpaqueIsland`): `stage`/`setup`/`impl`/`connect`/`parts`/`zones`/
    /// `boundary`/`flows`/`walk`/`hole`/`regions`/`constraints`/`exports`,
    /// policy rules, and decl-header generics.
    #[test]
    fn promoted_constructs_are_typed_nodes() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "assembly A:\n\
                   \x20\x20\x20\x20parts:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20p: Foo\n\
                   \x20\x20\x20\x20boundary:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20t: [0, 1]\n\
                   \x20\x20\x20\x20connect:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20m: Mesh(a=x, b=y)\n\
                   \x20\x20\x20\x20policy:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20prefer vendor(a) over vendor(b)\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20minimize total_cost\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        for k in [
            "PartsBlock",
            "BoundaryBlock",
            "ConnectBlock",
            "PolicyBlock",
            "PolicyRule",
        ] {
            assert!(kinds.iter().any(|x| x == k), "missing {k} in {kinds:?}");
        }
        // The block HEADERS are all typed (no block degraded to an
        // opaque island); value-expression tails may still be opaque
        // where the value grammar defers (WO-05 report note).
        assert!(!kinds.iter().any(|x| x == "OpaqueIsland"));
    }

    /// `stage`/`setup`/`impl` inside a part body are typed nodes, and a
    /// comment-led machining body (the sheet_bracket desync shape) opens
    /// correctly rather than ejecting its siblings.
    #[test]
    fn stage_impl_and_comment_led_body_are_structured() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part P:\n\
                   \x20\x20\x20\x20stage formed: process=press_brake\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20# a comment before the first body line\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20flange = Bend(radius=free)\n\
                   \x20\x20\x20\x20impl Pad for self:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20pad = formed.face\n\
                   \x20\x20\x20\x20require Structural:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20ok: manufacturable(formed)\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let root = p.syntax();
        let kinds: Vec<String> = root
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(kinds.iter().any(|x| x == "StageStmt"));
        assert!(kinds.iter().any(|x| x == "ImplStmt"));
        // The `require` block is NOT ejected to the file top level: it is
        // a descendant of the enclosing part decl.
        let require = root
            .descendants()
            .find(|n| n.kind() == SyntaxKind::RequireClaim)
            .expect("require present");
        assert_ne!(
            require.parent().map(|n| n.kind()),
            Some(SyntaxKind::File),
            "require ejected to file level"
        );
    }

    /// A `walk:` body promotes to a `WalkBody` node whose lines are typed
    /// `WalkStep`s, with a nested `hole <name>:` as its own block (WO-11).
    #[test]
    fn walk_body_and_generics_are_typed() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "interface PivotBore<d: length>:\n\
                   \x20\x20\x20\x20x: 1\n\
                   profile Q:\n\
                   \x20\x20\x20\x20walk:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20close via axis\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(kinds.iter().any(|x| x == "GenericParams"));
        assert!(kinds.iter().any(|x| x == "WalkBody"));
        assert_eq!(kinds.iter().filter(|x| *x == "WalkStep").count(), 3);
    }

    /// Use-site generic instantiations (`Foo<Bar>`, nested, in a ctor)
    /// promote to typed `InstExpr`/`GenericArgs` nodes (INV-11), while a
    /// whitespace-separated claim comparison (`mass < 5kg`) stays a
    /// `BinExpr` -- the `<`/`>` disambiguation the monomorphization pass
    /// depends on.
    #[test]
    fn use_site_generic_instantiation_is_typed() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part P:\n\
                   \x20\x20\x20\x20ends = PatternOf<TappedHole<M3>>(n=2)\n\
                   \x20\x20\x20\x20require R:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20mass: < 5kg\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        // Two instantiations: outer `PatternOf<...>` and nested
        // `TappedHole<M3>`.
        assert_eq!(kinds.iter().filter(|x| *x == "InstExpr").count(), 2);
        assert_eq!(kinds.iter().filter(|x| *x == "GenericArgs").count(), 2);
        // The comparison in the claim did NOT become an instantiation.
        assert!(kinds.iter().any(|x| x == "UnaryExpr" || x == "BinExpr"));
    }

    /// A `@hint(...)` annotation (regolith/12 rung 3, INV-03) parses as a
    /// typed `HintStmt` swallowed whole, produces NO diagnostic and NO
    /// opaque island, and -- crucially -- leaves the sibling `require`
    /// claim intact (the hint is verdict-inert: it perturbs nothing the
    /// lowering passes read).
    #[test]
    fn hint_annotation_is_a_typed_inert_node() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part flange:\n\
                   \x20\x20\x20\x20@hint(regime=small_deflection)\n\
                   \x20\x20\x20\x20require R:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20s: <= 1\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(
            kinds.iter().any(|x| x == "HintStmt"),
            "missing HintStmt in {kinds:?}"
        );
        // The hint did not eject or swallow the sibling claim.
        assert!(kinds.iter().any(|x| x == "RequireClaim"));
        assert!(!kinds.iter().any(|x| x == "OpaqueIsland"));
    }

    /// Subject-attributed recovery: a malformed in-body statement (a
    /// stray closing bracket at statement position) produces a
    /// `MALFORMED_IN_BODY` diagnostic ATTRIBUTED to its enclosing
    /// declaration subject (a secondary span into the subject header),
    /// NOT a bare top-level `UNEXPECTED_TOKEN`, and a following valid
    /// statement still parses.
    #[test]
    fn malformed_in_body_stmt_is_attributed_to_subject() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part Widget:\n    )\n    x: 1\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        let diags = p.diagnostics();
        assert_eq!(diags.len(), 1, "exactly one diagnostic: {diags:?}");
        let d = &diags[0];
        assert_eq!(d.code, super::MALFORMED_IN_BODY);
        assert_ne!(d.code, super::UNEXPECTED_TOKEN);
        assert!(
            d.message.contains("Widget"),
            "message names the subject: {}",
            d.message
        );
        // The attribution is a secondary span pointing into the subject's
        // declaration header (consumable by per-subject INV-20 gating).
        assert!(
            d.spans.iter().any(|s| s.label.contains("Widget")),
            "a span attributes to `Widget`: {:?}",
            d.spans
        );
        // A `SubjectError` node carries the malformation in the tree, and
        // the following `x: 1` field still parses.
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(kinds.iter().any(|x| x == "SubjectError"));
        assert!(kinds.iter().any(|x| x == "Field"));
    }

    /// A `workloads:` block promotes to a typed `WorkloadsBlock` node whose
    /// lines are typed `WorkloadStmt`s, and a trailing `realizes` clause
    /// nests as a typed `RealizesStmt` -- neither degrades to
    /// `OpaqueIsland` (cuprite/05 sec. 1; EOPEN-15).
    #[test]
    fn workloads_block_and_realizes_are_typed() {
        use crate::ast::{AstNode, WorkloadsBlock};

        let file = Utf8PathBuf::from("t.cupr");
        let src = "computer FlightCore:\n\
                   \x20\x20\x20\x20workloads:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20att:  loop(rate=4Hz, work=40kops f32, jitter <= 10ms) realizes decide\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20hk:   loop(rate=1Hz, work=5kops i32)\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        assert!(kinds.iter().any(|x| x == "WorkloadsBlock"));
        assert_eq!(kinds.iter().filter(|x| *x == "WorkloadStmt").count(), 2);
        assert!(kinds.iter().any(|x| x == "WorkloadParams"));
        assert_eq!(kinds.iter().filter(|x| *x == "RealizesStmt").count(), 1);
        assert!(!kinds.iter().any(|x| x == "OpaqueIsland"));

        // Typed-AST accessors round-trip the parsed structure.
        let block = p
            .syntax()
            .descendants()
            .find_map(WorkloadsBlock::cast)
            .expect("WorkloadsBlock present");
        let workloads = block.workloads();
        assert_eq!(workloads.len(), 2);
        assert_eq!(workloads[0].name(), "att");
        assert_eq!(workloads[0].kind_word().as_deref(), Some("loop"));
        assert!(workloads[0].params().is_some());
        let realizes = workloads[0].realizes().expect("att realizes decide");
        assert_eq!(realizes.intents(), vec!["decide".to_string()]);
        assert_eq!(workloads[1].name(), "hk");
        assert!(workloads[1].realizes().is_none());
    }

    /// A standalone `realizes <intent>, <intent2>` statement (not
    /// trailing a workload line) also promotes to a typed `RealizesStmt`
    /// carrying every referenced intent name.
    #[test]
    fn standalone_realizes_stmt_is_typed_with_intent_list() {
        use crate::ast::{AstNode, RealizesStmt};

        let file = Utf8PathBuf::from("t.cupr");
        let src = "computer C:\n    realizes decide, crunch\n";
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let stmt = p
            .syntax()
            .descendants()
            .find_map(RealizesStmt::cast)
            .expect("RealizesStmt present");
        assert_eq!(
            stmt.intents(),
            vec!["decide".to_string(), "crunch".to_string()]
        );
    }

    /// WO-28: a full process pack parses TYPED end-to-end with zero
    /// diagnostics -- capability table, dfm block, rules, forall,
    /// resolves-from-free, per/why fields, and expect cases -- and the
    /// AST accessors round-trip every promoted shape.
    #[test]
    fn process_pack_parses_typed() {
        use crate::ast::{AstNode, File};

        let path = workspace_root().join("crates/regolith-syntax/tests/fixtures/process_pack.hema");
        let src = std::fs::read_to_string(&path).expect("read process_pack fixture");
        let file = Utf8PathBuf::from_path_buf(path).expect("utf8 path");
        let p = parse(&src, &file);
        assert_eq!(p.syntax().text().to_string(), src, "lossless");
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());

        let root = File::cast(p.syntax()).expect("root is File");
        let decl = root.decls().into_iter().next().expect("one decl");
        assert!(decl.is_process(), "leading word is `process`");
        assert_eq!(decl.process_name().as_deref(), Some("press_brake_shop"));

        let capability = decl.capability().expect("capability table typed");
        assert_eq!(capability.entries().len(), 2);
        assert_eq!(capability.entries()[0].name(), "thickness");

        let packs = decl.rule_packs();
        assert_eq!(packs.len(), 1);
        assert_eq!(packs[0].family().as_deref(), Some("dfm"));
        let rules = packs[0].rules();
        assert_eq!(rules.len(), 2);

        let r = &rules[0];
        assert_eq!(r.name().as_deref(), Some("min_bend_radius"));
        let forall = r.forall().expect("forall clause typed");
        assert_eq!(forall.var().as_deref(), Some("b"));
        assert_eq!(forall.query_text(), "bends");
        assert!(r.demand().is_some(), "demand field present");
        assert!(r.advise().is_none());
        let resolves = r.resolves().expect("resolves clause typed");
        assert_eq!(resolves.target(), "b.radius");
        assert!(resolves.from_free());
        assert_eq!(
            r.per().as_deref(),
            Some("press pack table, 300-series stainless")
        );
        assert_eq!(
            r.why().as_deref(),
            Some("tighter radii crack the outer grain")
        );
        let expect = r.expect().expect("expect block typed");
        let verdicts: Vec<_> = expect
            .cases()
            .iter()
            .filter_map(crate::ast::ExpectCase::verdict)
            .collect();
        assert_eq!(verdicts, vec!["pass".to_string(), "fail".to_string()]);
        assert!(
            expect.cases()[0].fixture().is_some(),
            "fixture is a value node"
        );
        assert_eq!(rules[1].name().as_deref(), Some("bend_relief"));
    }

    /// Cycle 18 F94: the owner-corrected current-driven demand
    /// (`sum(n.loads.i_input) <= n.driver.i_drive`) is FULLY structured
    /// by the existing claim-expression grammar -- a `BinExpr` whose lhs
    /// is a `CallExpr` (aggregate over a query path) and whose rhs is a
    /// dotted `Path` (record dereference). No grammar widening needed.
    #[test]
    fn rule_demand_parses_aggregate_and_record_dereference() {
        use crate::ast::{AstNode, BinExpr, File};

        let path = workspace_root().join("crates/regolith-syntax/tests/fixtures/process_pack.cupr");
        let src = std::fs::read_to_string(&path).expect("read process_pack fixture");
        let file = Utf8PathBuf::from_path_buf(path).expect("utf8 path");
        let p = parse(&src, &file);
        assert_eq!(p.syntax().text().to_string(), src, "lossless");
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());

        let root = File::cast(p.syntax()).expect("root is File");
        let decl = root.decls().into_iter().next().expect("one decl");
        let packs = decl.rule_packs();
        let families: Vec<_> = packs
            .iter()
            .filter_map(crate::ast::RulePackBlock::family)
            .collect();
        assert_eq!(families, vec!["erc".to_string(), "drc".to_string()]);

        let fanout = &packs[0].rules()[0];
        assert_eq!(fanout.name().as_deref(), Some("fanout_drive"));
        let demand = fanout.demand().expect("demand present");
        let value = demand.value().expect("demand value structured");
        let cmp = BinExpr::cast(value).expect("comparison is a BinExpr");
        assert_eq!(
            cmp.lhs().map(|n| n.kind()),
            Some(SyntaxKind::CallExpr),
            "lhs is the aggregate call"
        );
        assert_eq!(
            cmp.rhs().map(|n| n.kind()),
            Some(SyntaxKind::Path),
            "rhs is the record dereference path"
        );
    }

    /// Cycle 18 F95: a query filter the value grammar does not model
    /// (`bends.where(not b.at_free_edge)`) stays lossless INSIDE the
    /// forall clause -- structure recorded, nothing invented, no
    /// diagnostic.
    #[test]
    fn forall_query_residue_stays_inside_the_clause() {
        use crate::ast::{AstNode, ForallClause};

        let src = "process p:\n\
                   \x20\x20\x20\x20dfm:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20rule bend_relief:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20forall b in bends.where(not b.at_free_edge)\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20demand: b.relief_cuts.count >= 1\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20why: \"unrelieved interior bends tear\"\n";
        let file = Utf8PathBuf::from("t.hema");
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src, "lossless");
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let clause = p
            .syntax()
            .descendants()
            .find_map(ForallClause::cast)
            .expect("forall clause typed");
        assert_eq!(clause.var().as_deref(), Some("b"));
        assert_eq!(clause.query_text(), "bends.where(not b.at_free_edge)");
        // Any opaque residue lives INSIDE the clause, not beside it.
        for n in p.syntax().descendants() {
            if n.kind() == SyntaxKind::OpaqueIsland {
                assert!(
                    n.ancestors().any(|a| a.kind() == SyntaxKind::ForallClause),
                    "opaque residue escaped the forall clause"
                );
            }
        }
    }

    /// AD-3 recovery: a malformed line inside a rule body is attributed
    /// to the enclosing subject and consumes one token -- the rest of
    /// the rule, the NEXT rule, and the next declaration all still
    /// parse. A bad rule never eats the file; diagnostics stay batch.
    #[test]
    fn malformed_rule_line_does_not_eat_the_pack() {
        use crate::ast::{AstNode, File};

        let src = "process p:\n\
                   \x20\x20\x20\x20dfm:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20rule broken:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20)\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20why: \"still parses\"\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20rule intact:\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20forall h in holes\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20demand: h.diameter >= 1mm\n\
                   part after:\n\
                   \x20\x20\x20\x20x: 1\n";
        let file = Utf8PathBuf::from("t.hema");
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src, "lossless");
        assert_eq!(p.diagnostics().len(), 1, "{:?}", p.diagnostics());
        assert_eq!(p.diagnostics()[0].code, super::MALFORMED_IN_BODY);

        let root = File::cast(p.syntax()).expect("root is File");
        assert_eq!(root.decls().len(), 2, "the part after the pack parses");
        let pack = &root.decls()[0].rule_packs()[0];
        let names: Vec<_> = pack
            .rules()
            .iter()
            .filter_map(crate::ast::RuleDecl::name)
            .collect();
        assert_eq!(names, vec!["broken".to_string(), "intact".to_string()]);
        assert!(
            pack.rules()[0].why().is_some(),
            "the broken rule's later fields still parse"
        );
        assert!(pack.rules()[1].forall().is_some());
    }

    /// Cycle 18 D85: the rule words are CONTEXTUAL. Outside a process
    /// body, `dfm:`/`capability:` stay ordinary fields, `rule = x` stays
    /// a ctor, and `process=` in a stage header keeps its Ident tokens
    /// -- nothing is promoted, nothing errors.
    #[test]
    fn rule_words_are_not_promoted_outside_process_bodies() {
        let src = "part P:\n\
                   \x20\x20\x20\x20stage formed: process=press_brake\n\
                   \x20\x20\x20\x20\x20\x20\x20\x20flange = Bend(radius=free)\n\
                   \x20\x20\x20\x20dfm: 5\n\
                   \x20\x20\x20\x20capability: high\n\
                   \x20\x20\x20\x20rule = 3\n";
        let file = Utf8PathBuf::from("t.hema");
        let p = parse(src, &file);
        assert_eq!(p.syntax().text().to_string(), src);
        assert!(p.diagnostics().is_empty(), "{:?}", p.diagnostics());
        let kinds: Vec<String> = p
            .syntax()
            .descendants()
            .map(|n| format!("{:?}", n.kind()))
            .collect();
        for absent in [
            "RulePackBlock",
            "RuleDecl",
            "CapabilityBlock",
            "ForallClause",
            "ResolvesClause",
            "ExpectBlock",
        ] {
            assert!(
                !kinds.iter().any(|x| x == absent),
                "{absent} must not appear outside a process body: {kinds:?}"
            );
        }
        assert!(kinds.iter().any(|x| x == "StageStmt"));
    }

    fn regolith_syntax_extensions() -> Vec<&'static str> {
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
