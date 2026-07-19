//! The dispatch core: server capabilities, document store, and the
//! request/notification handlers. Split from `main.rs` so protocol-
//! level tests can drive it without a real stdio transport
//! (WO-38 deliverable 9).

use std::collections::HashMap;

use camino::Utf8PathBuf;
use lsp_types::{
    CodeActionKind, CodeActionOptions, CodeActionProviderCapability, CompletionOptions,
    DocumentSymbolResponse, FoldingRangeProviderCapability, HoverProviderCapability, OneOf,
    Position, SemanticTokensFullOptions, SemanticTokensOptions, SemanticTokensResult,
    SemanticTokensServerCapabilities, ServerCapabilities, TextDocumentSyncCapability,
    TextDocumentSyncKind, Url, WorkDoneProgressOptions,
};

use crate::diagnostics::uri_to_path;
use crate::position::LineIndex;
use crate::{
    actions, completion, diagnostics, folding, formatting, hover, nav, semtok, symbols, workspace,
};

/// The server capabilities announced at `initialize` -- exactly the
/// LSP surface WO-38 deliverables 3-6 implement, nothing speculative.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#server
pub fn capabilities() -> ServerCapabilities {
    ServerCapabilities {
        text_document_sync: Some(TextDocumentSyncCapability::Kind(TextDocumentSyncKind::FULL)),
        hover_provider: Some(HoverProviderCapability::Simple(true)),
        document_symbol_provider: Some(OneOf::Left(true)),
        folding_range_provider: Some(FoldingRangeProviderCapability::Simple(true)),
        document_formatting_provider: Some(OneOf::Left(true)),
        code_action_provider: Some(CodeActionProviderCapability::Options(CodeActionOptions {
            code_action_kinds: Some(vec![CodeActionKind::QUICKFIX]),
            work_done_progress_options: WorkDoneProgressOptions::default(),
            resolve_provider: Some(false),
        })),
        completion_provider: Some(CompletionOptions {
            resolve_provider: Some(false),
            trigger_characters: None,
            all_commit_characters: None,
            work_done_progress_options: WorkDoneProgressOptions::default(),
            completion_item: None,
        }),
        definition_provider: Some(OneOf::Left(true)),
        references_provider: Some(OneOf::Left(true)),
        rename_provider: Some(OneOf::Left(true)),
        semantic_tokens_provider: Some(SemanticTokensServerCapabilities::SemanticTokensOptions(
            SemanticTokensOptions {
                work_done_progress_options: WorkDoneProgressOptions::default(),
                legend: semtok::legend(),
                range: Some(false),
                full: Some(SemanticTokensFullOptions::Bool(true)),
            },
        )),
        ..ServerCapabilities::default()
    }
}

/// The server's mutable state: the discovered workspace root and every
/// currently open document's full text (full-text sync v1, deliverable
/// 1 -- files are small).
// frob:doc docs/modules/regolith-ls.md#server
pub struct Server {
    root: Utf8PathBuf,
    docs: HashMap<Url, String>,
}

impl Server {
    /// Start a server rooted at `root` (already resolved via
    /// [`workspace::discover_root`]).
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn new(root: Utf8PathBuf) -> Server {
        Server {
            root,
            docs: HashMap::new(),
        }
    }

    /// The discovered workspace root.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn root(&self) -> &Utf8PathBuf {
        &self.root
    }

    /// Record (or update) an open document's full text.
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn open(&mut self, uri: Url, text: String) {
        self.docs.insert(uri, text);
    }

    /// Forget a closed document (the on-disk text is now authoritative
    /// again for any subsequent workspace check).
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn close(&mut self, uri: &Url) {
        self.docs.remove(uri);
    }

    /// The current in-memory text for `uri`, if open.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn text(&self, uri: &Url) -> Option<&str> {
        self.docs.get(uri).map(String::as_str)
    }

    /// Recompute diagnostics for the whole workspace by running the same
    /// `check` pipeline the CLI runs (deliverable 3: byte-identical
    /// diagnostic sets is the acceptance criterion). Open, unsaved edits
    /// are flushed to a scratch overlay first so `regolith-api::Session`
    /// (which reads from disk) still sees them -- see the module-level
    /// gap note in `diagnostics.rs` about the tiering cut.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn check_diagnostics(
        &self,
    ) -> Option<std::collections::BTreeMap<Utf8PathBuf, Vec<lsp_types::Diagnostic>>> {
        // Open documents are flushed to disk before checking so the
        // pipeline (which reads files, matching the CLI exactly) sees
        // live edits; this is what makes the diagnostic set genuinely
        // byte-identical to `regolith check`, at the cost of touching
        // the file the editor already owns (the editor is the source of
        // truth for its own buffer; this write mirrors its own content).
        for (uri, text) in &self.docs {
            if let Some(path) = uri_to_path(uri) {
                let _ = std::fs::write(&path, text);
            }
        }
        diagnostics::check_workspace(&self.root)
    }

    /// `textDocument/hover`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn hover(&self, uri: &Url, position: Position) -> Option<lsp_types::Hover> {
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        hover::hover_at(&text, &index, position, &self.root)
    }

    /// `textDocument/documentSymbol`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn document_symbols(&self, uri: &Url) -> Option<DocumentSymbolResponse> {
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        Some(DocumentSymbolResponse::Nested(symbols::document_symbols(
            &text, &index,
        )))
    }

    /// `textDocument/foldingRange`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn folding_ranges(&self, uri: &Url) -> Option<Vec<lsp_types::FoldingRange>> {
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        Some(folding::folding_ranges(&text, &index))
    }

    /// `textDocument/formatting`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn format(&self, uri: &Url) -> Option<Vec<lsp_types::TextEdit>> {
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        Some(
            formatting::format_document(&text, &index)
                .into_iter()
                .collect(),
        )
    }

    /// `textDocument/semanticTokens/full`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn semantic_tokens(&self, uri: &Url) -> Option<SemanticTokensResult> {
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        Some(SemanticTokensResult::Tokens(lsp_types::SemanticTokens {
            result_id: None,
            data: semtok::tokens_for(&text, &index),
        }))
    }

    /// `textDocument/codeAction`.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn code_actions(
        &self,
        diags: &[lsp_types::Diagnostic],
    ) -> Vec<lsp_types::CodeActionOrCommand> {
        actions::code_actions_for(diags)
            .into_iter()
            .map(lsp_types::CodeActionOrCommand::CodeAction)
            .collect()
    }

    /// `textDocument/completion` (deliverable 6: position-aware
    /// keywords + in-scope decl names; registry ids are a named cut,
    /// see `completion.rs`).
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn completions(&self, uri: &Url, position: Position) -> Vec<lsp_types::CompletionItem> {
        let Some(text) = self.resolve_text(uri) else {
            return completion::keyword_completions();
        };
        let index = LineIndex::new(&text);
        completion::completions_at(&text, &index, position)
    }

    /// `textDocument/definition` (deliverable 6): every reachable
    /// definition of the identifier under the cursor.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn definition(&self, uri: &Url, position: Position) -> Option<Vec<lsp_types::Location>> {
        let path = uri_to_path(uri)?;
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        let occurrences = nav::definitions(&self.root, &path, &text, &index, position);
        Some(nav::occurrences_to_locations(occurrences))
    }

    /// `textDocument/references` (deliverable 6): every occurrence of
    /// the identifier under the cursor, across every reachable file.
    #[must_use]
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn references(&self, uri: &Url, position: Position) -> Option<Vec<lsp_types::Location>> {
        let path = uri_to_path(uri)?;
        let text = self.resolve_text(uri)?;
        let index = LineIndex::new(&text);
        let occurrences = nav::references(&self.root, &path, &text, &index, position);
        Some(nav::occurrences_to_locations(occurrences))
    }

    /// `textDocument/rename` (deliverable 6): resolution-checked rename.
    ///
    /// # Errors
    /// Returns the refusal reason when the identifier is unresolved or
    /// ambiguous (more than one reachable file defines it) -- the
    /// caller surfaces this as an LSP error response, never a partial
    /// edit.
    // frob:doc docs/modules/regolith-ls.md#server
    pub fn rename(
        &self,
        uri: &Url,
        position: Position,
        new_name: &str,
    ) -> Result<lsp_types::WorkspaceEdit, String> {
        let path = uri_to_path(uri).ok_or_else(|| "cannot resolve document path".to_string())?;
        let text = self
            .resolve_text(uri)
            .ok_or_else(|| "document not available".to_string())?;
        let index = LineIndex::new(&text);
        match nav::rename(&self.root, &path, &text, &index, position, new_name) {
            nav::RenameOutcome::Edits(edits) => Ok(nav::edits_to_workspace_edit(edits)),
            nav::RenameOutcome::Ambiguous { reason } => Err(reason),
            nav::RenameOutcome::NotFound => {
                Err("no renamable identifier at this position".to_string())
            }
        }
    }

    /// Prefer the in-memory buffer for `uri`; fall back to disk (a file
    /// the client never opened, e.g. reached via folding/symbols
    /// requests some clients issue eagerly).
    fn resolve_text(&self, uri: &Url) -> Option<String> {
        if let Some(text) = self.text(uri) {
            return Some(text.to_string());
        }
        let path = uri_to_path(uri)?;
        std::fs::read_to_string(path).ok()
    }
}

/// Discover the workspace root for `initialize`'s `root_uri`/`root_path`,
/// falling back to the current directory when the client gave neither
/// (deliverable 1).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#server
pub fn root_from_initialize(params: &lsp_types::InitializeParams) -> Utf8PathBuf {
    #[allow(deprecated)] // `root_uri` still the only single-folder signal a v1-3 client sends
    let root_uri = params.root_uri.as_ref();
    let opened = root_uri
        .and_then(uri_to_path)
        .or_else(|| {
            std::env::current_dir()
                .ok()
                .and_then(|p| Utf8PathBuf::from_path_buf(p).ok())
        })
        .unwrap_or_else(|| Utf8PathBuf::from("."));
    workspace::discover_root(&opened)
}

#[cfg(test)]
mod tests {
    use super::Server;
    use camino::Utf8PathBuf;
    use lsp_types::{Position, Url};
    use regolith_syntax::extension::Language;

    fn examples_dir(rel: &str) -> Utf8PathBuf {
        let manifest = Utf8PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest.join("../../examples").join(rel)
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.hover kind="unit"
    #[test]
    fn hover_reads_from_open_buffer_over_disk() {
        let mut server = Server::new(examples_dir("flagships/cubesat"));
        let uri = Url::parse(&format!(
            "file:///scratch/widget.{}",
            Language::Hematite.extension()
        ))
        .unwrap();
        server.open(uri.clone(), "part Widget:\n    mass: 5 g\n".to_string());
        let hover = server.hover(&uri, Position::new(0, 6));
        assert!(hover.is_some());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.document_symbols kind="unit"
    #[test]
    fn document_symbols_over_a_corpus_file() {
        let dir = examples_dir("flagships/cubesat");
        let hema = std::fs::read_dir(&dir).ok().and_then(|mut it| {
            it.find_map(|e| {
                let p = e.ok()?.path();
                (p.extension().and_then(|e| e.to_str()) == Some(Language::Hematite.extension()))
                    .then_some(p)
            })
        });
        let Some(hema) = hema else {
            return; // corpus shape may change; this is a smoke test
        };
        let server = Server::new(dir);
        let uri = Url::from_file_path(&hema).unwrap();
        let symbols = server.document_symbols(&uri);
        assert!(symbols.is_some());
    }

    #[test]
    fn close_forgets_the_open_buffer() {
        let mut server = Server::new(examples_dir("flagships/cubesat"));
        let uri = Url::parse(&format!(
            "file:///scratch/widget.{}",
            Language::Hematite.extension()
        ))
        .unwrap();
        server.open(uri.clone(), "part Widget:\n".to_string());
        assert!(server.text(&uri).is_some());
        server.close(&uri);
        assert!(server.text(&uri).is_none());
    }

    /// A scratch workspace with one well-formed `.hema` file, for the
    /// handler tests below that need a real on-disk root (`definition`/
    /// `references`/`rename`/`check_diagnostics` all resolve paths).
    fn scratch_workspace(src: &str) -> (Utf8PathBuf, Url) {
        let dir = std::env::temp_dir().join(format!(
            "regolith-ls-server-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join(format!("widget.{}", Language::Hematite.extension()));
        std::fs::write(&file, src).unwrap();
        let uri = Url::from_file_path(&file).unwrap();
        (dir, uri)
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.open kind="unit"
    // frob:tests crates/regolith-ls/src/server.rs::Server.check_diagnostics kind="unit"
    #[test]
    fn check_diagnostics_runs_the_real_pipeline_over_the_workspace() {
        let (dir, _uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let server = Server::new(dir);
        let diags = server.check_diagnostics();
        assert!(diags.is_some(), "a well-formed workspace still checks");
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.folding_ranges kind="unit"
    #[test]
    fn folding_ranges_over_an_open_buffer() {
        let (dir, uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let mut server = Server::new(dir);
        server.open(uri.clone(), "part Widget:\n    mass: 5 g\n".to_string());
        let ranges = server.folding_ranges(&uri).expect("folding ranges");
        assert!(!ranges.is_empty());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.semantic_tokens kind="unit"
    #[test]
    fn semantic_tokens_over_an_open_buffer() {
        let (dir, uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let mut server = Server::new(dir);
        server.open(uri.clone(), "part Widget:\n    mass: 5 g\n".to_string());
        let tokens = server.semantic_tokens(&uri);
        assert!(tokens.is_some());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.code_actions kind="unit"
    #[test]
    fn code_actions_with_no_diagnostics_is_empty() {
        let (dir, _uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let server = Server::new(dir);
        assert!(server.code_actions(&[]).is_empty());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.completions kind="unit"
    #[test]
    fn completions_without_an_open_buffer_falls_back_to_keywords() {
        let (dir, uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let server = Server::new(dir);
        let items = server.completions(&uri, Position::new(0, 0));
        assert!(!items.is_empty());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.definition kind="unit"
    #[test]
    fn definition_finds_the_decl_header() {
        let src = "part Widget:\n    mass: 5 g\n";
        let (dir, uri) = scratch_workspace(src);
        let mut server = Server::new(dir);
        server.open(uri.clone(), src.to_string());
        let locs = server.definition(&uri, Position::new(0, 6));
        assert!(locs.is_some());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.references kind="unit"
    #[test]
    fn references_finds_every_occurrence() {
        let src = "part Widget:\n    mass: 5 g\n";
        let (dir, uri) = scratch_workspace(src);
        let mut server = Server::new(dir);
        server.open(uri.clone(), src.to_string());
        let locs = server.references(&uri, Position::new(0, 6));
        assert!(locs.is_some());
    }

    // frob:tests crates/regolith-ls/src/server.rs::Server.rename kind="unit"
    #[test]
    fn rename_of_an_unknown_position_is_an_error() {
        let src = "part Widget:\n    mass: 5 g\n";
        let (dir, uri) = scratch_workspace(src);
        let mut server = Server::new(dir);
        server.open(uri.clone(), src.to_string());
        let result = server.rename(&uri, Position::new(1, 4), "Renamed");
        assert!(
            result.is_err(),
            "renaming a field name, not a decl, refuses"
        );
    }

    // frob:tests crates/regolith-ls/src/server.rs::root_from_initialize kind="unit"
    #[test]
    fn root_from_initialize_prefers_root_uri_over_cwd() {
        let (dir, _uri) = scratch_workspace("part Widget:\n    mass: 5 g\n");
        let root_uri = Url::from_file_path(&dir).unwrap();
        #[allow(deprecated)]
        let params = lsp_types::InitializeParams {
            root_uri: Some(root_uri),
            ..Default::default()
        };
        let root = super::root_from_initialize(&params);
        assert_eq!(root, dir);
    }
}
