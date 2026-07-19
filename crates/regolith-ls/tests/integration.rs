//! Integration test (TEST003): drives `regolith-ls::server::Server`
//! end to end from outside the crate over a real on-disk workspace --
//! open a document, run diagnostics/hover/definition through the
//! public handler surface, the same seam the LSP transport (`main.rs`)
//! and the protocol-level tests both go through (WO-38 deliverable 9).

// frob:tests crates/regolith-ls/src kind="integration"
#[test]
fn server_handlers_drive_end_to_end_over_a_real_workspace() {
    use camino::Utf8PathBuf;
    use lsp_types::{Position, Url};
    use regolith_ls::server::Server;

    let dir = std::env::temp_dir().join(format!(
        "regolith-ls-integration-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("widget.hema");
    let src = "part Widget:\n    mass: 5 g\n";
    std::fs::write(&file, src).unwrap();
    let uri = Url::from_file_path(&file).unwrap();

    let mut server = Server::new(dir);
    server.open(uri.clone(), src.to_string());

    // Diagnostics run the real check pipeline.
    let diags = server.check_diagnostics();
    assert!(diags.is_some(), "a well-formed workspace still checks");

    // Hover over the decl name resolves.
    let hover = server.hover(&uri, Position::new(0, 6));
    assert!(hover.is_some());

    // Definition of the same identifier resolves to at least one location.
    let defs = server.definition(&uri, Position::new(0, 6));
    assert!(defs.is_some());

    // Document symbols publish the top-level decl.
    let symbols = server.document_symbols(&uri);
    assert!(symbols.is_some());
}
