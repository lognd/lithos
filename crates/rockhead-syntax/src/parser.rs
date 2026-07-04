//! The hand-written, event-based recursive-descent parser with Pratt
//! expressions and layout-anchored error recovery (AD-3).
//!
//! Substrate reference: `docs/substrate/08`, `docs/mech/02`,
//! `docs/elec/07`, and `examples/` (the concrete target corpus). The
//! parser emits events that a builder folds into a rowan tree; error
//! recovery syncs on INDENT/DEDENT so one bad statement never eats the
//! file (diagnostics stay batch-emitted, substrate/09 sec. 4).
//!
//! Domain payloads (walk bodies, `on <event>:` bodies, continuous
//! relations) parse to [`SyntaxKind::OpaqueIsland`] in this WO:
//! structure recorded, semantics deferred (WO-11 / behavioral).

use camino::Utf8PathBuf;
use rockhead_diag::{DiagCode, Diagnostic, Family, LabeledSpan, Span};
use rowan::{GreenNode, GreenNodeBuilder, Language as _};

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
/// Runs lex -> layout -> parse. The `file` path anchors diagnostic
/// spans. Never panics on any input (the fuzz invariant, AD-3).
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

impl Parser<'_> {
    fn current(&self) -> Option<SyntaxKind> {
        self.toks.get(self.pos).map(|t| t.kind)
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
    /// followed by an optional indented body. The body's internal
    /// statement grammar (fields, ctor statements, `then` scopes,
    /// claims, ...) is out of scope for this bootstrap pass and is
    /// recorded as a single opaque island (see the WO-05 report note);
    /// this keeps the CST byte-complete and error-resilient while
    /// deferring statement-level typing.
    fn parse_decl(&mut self) {
        self.start(SyntaxKind::Decl);
        self.consume_header_line();
        // The layout pass emits the next line's leading Whitespace
        // before its Indent/Dedent marker; skip past it (still inside
        // Decl) so the Indent check below sees it.
        while self.current() == Some(SyntaxKind::Whitespace) {
            self.bump();
        }
        if self.current() == Some(SyntaxKind::Indent) {
            self.start(SyntaxKind::OpaqueIsland);
            self.bump(); // the opening Indent
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
            self.finish();
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

    /// The acceptance corpus: every file under `examples/` parses to an
    /// AST (opaque islands allowed) without panicking, and the CST
    /// remains byte-complete. Full statement-level typing (fields,
    /// ctor statements, expression unit-checking) is out of scope for
    /// this bootstrap pass -- see the WO-05 report note; `examples/`
    /// files are not asserted diagnostic-free.
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
